from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP, Context
import jenkins
import requests
from contextlib import asynccontextmanager
import os
import logging
from urllib.parse import urljoin


@dataclass
class JenkinsContext:
    client: jenkins.Jenkins
    jenkins_url: str
    username: str
    password: str
    session: requests.Session
    crumb_data: Optional[Dict[str, str]] = None


def get_jenkins_crumb(
    session: requests.Session, jenkins_url: str, username: str, password: str
) -> Optional[Dict[str, str]]:
    """
    Get a CSRF crumb from Jenkins using the provided session

    Args:
        session: The requests Session object to use
        jenkins_url: Base URL of the Jenkins server
        username: Jenkins username
        password: Jenkins password or API token

    Returns:
        Dictionary with the crumb field name and value or None if unsuccessful
    """
    try:
        crumb_url = urljoin(jenkins_url, "crumbIssuer/api/json")

        response = session.get(crumb_url, auth=(username, password))
        if response.status_code != 200:
            logging.warning(f"Failed to get Jenkins crumb: HTTP {response.status_code}")
            return None

        crumb_data = response.json()
        if (
            not crumb_data
            or "crumbRequestField" not in crumb_data
            or "crumb" not in crumb_data
        ):
            logging.warning(f"Invalid crumb response format: {response.text}")
            return None

        # Create the crumb header data
        crumb_header = {crumb_data["crumbRequestField"]: crumb_data["crumb"]}
        logging.info(f"Got Jenkins crumb: {crumb_data['crumbRequestField']}=<masked>")
        return crumb_header
    except Exception as e:
        logging.error(f"Error getting Jenkins crumb: {str(e)}")
        return None


def make_jenkins_request(
    ctx: JenkinsContext,
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    retry_on_auth_failure: bool = True,
) -> requests.Response:
    """
    Make a request to Jenkins with proper CSRF protection

    Args:
        ctx: Jenkins context with session and auth information
        method: HTTP method (GET, POST, etc.)
        path: Path relative to Jenkins base URL
        params: Query parameters (for GET requests)
        data: Form data (for POST requests)
        retry_on_auth_failure: Whether to retry with a fresh crumb on 403 errors

    Returns:
        Response object from the request
    """
    url = urljoin(ctx.jenkins_url, path)
    headers = {}

    # Add crumb to headers if available
    if ctx.crumb_data:
        headers.update(ctx.crumb_data)

    try:
        response = ctx.session.request(
            method,
            url,
            auth=(ctx.username, ctx.password),
            headers=headers,
            params=params,
            data=data,
        )

        # If we get a 403 and it mentions the crumb, try to refresh the crumb and retry
        if (
            response.status_code == 403
            and retry_on_auth_failure
            and ("No valid crumb" in response.text or "Invalid crumb" in response.text)
        ):
            logging.info("Crumb expired, refreshing and retrying request")
            # Get a fresh crumb
            ctx.crumb_data = get_jenkins_crumb(
                ctx.session, ctx.jenkins_url, ctx.username, ctx.password
            )
            if ctx.crumb_data:
                # Retry without the retry_on_auth_failure flag to prevent infinite loops
                return make_jenkins_request(
                    ctx, method, path, params, data, retry_on_auth_failure=False
                )

        return response
    except Exception as e:
        logging.error(f"Error making Jenkins request: {str(e)}")
        raise


@asynccontextmanager
async def jenkins_lifespan(server: FastMCP) -> AsyncIterator[JenkinsContext]:
    """Manage Jenkins client lifecycle with CSRF crumb handling"""
    # read .env
    import dotenv

    dotenv.load_dotenv()
    jenkins_url = os.environ["JENKINS_URL"]
    username = os.environ["JENKINS_USERNAME"]
    password = os.environ["JENKINS_PASSWORD"]
    use_token = os.environ.get("JENKINS_USE_API_TOKEN", "false").lower() == "true"

    try:
        # Create a Jenkins client
        client = jenkins.Jenkins(jenkins_url, username=username, password=password)

        # Create a session to maintain cookies
        session = requests.Session()

        # Initialize context
        context = JenkinsContext(
            client=client,
            jenkins_url=jenkins_url,
            username=username,
            password=password,
            session=session,
            crumb_data=None,
        )

        # If we're not using an API token, get a crumb for CSRF protection
        if not use_token:
            context.crumb_data = get_jenkins_crumb(
                session, jenkins_url, username, password
            )

        yield context
    finally:
        # Clean up the session
        if "session" in locals():
            session.close()


mcp = FastMCP("jenkins-mcp", lifespan=jenkins_lifespan)


@mcp.tool()
def list_jobs(ctx: Context) -> List[str]:
    """List all Jenkins jobs"""
    client = ctx.request_context.lifespan_context.client
    return client.get_jobs()


@mcp.tool()
def trigger_build(
    ctx: Context, job_name: str, parameters: Optional[dict] = None
) -> dict:
    """Trigger a Jenkins build

    Args:
        job_name: Name of the job to build
        parameters: Optional build parameters as a dictionary (e.g. {"param1": "value1"})

    Returns:
        Dictionary containing build information including the build number
    """
    if not isinstance(job_name, str):
        raise ValueError(f"job_name must be a string, got {type(job_name)}")
    if parameters is not None and not isinstance(parameters, dict):
        raise ValueError(
            f"parameters must be a dictionary or None, got {type(parameters)}"
        )

    jenkins_ctx = ctx.request_context.lifespan_context
    client = jenkins_ctx.client

    # First verify the job exists
    try:
        job_info = client.get_job_info(job_name)
        if not job_info:
            raise ValueError(f"Job {job_name} not found")
    except Exception as e:
        raise ValueError(f"Error checking job {job_name}: {str(e)}")

    # Then try to trigger the build
    try:
        # Get the next build number before triggering
        next_build_number = job_info["nextBuildNumber"]

        # Determine the endpoint based on whether parameters are provided
        endpoint = (
            f"job/{job_name}/buildWithParameters"
            if parameters
            else f"job/{job_name}/build"
        )

        # Make request with proper CSRF protection
        response = make_jenkins_request(
            jenkins_ctx, "POST", endpoint, params=parameters if parameters else None
        )

        if response.status_code not in (200, 201):
            raise ValueError(
                f"Failed to trigger build: HTTP {response.status_code}, {response.text}"
            )

        queue_id = None
        location = response.headers.get("Location")
        if location:
            # Extract queue ID from Location header (e.g., .../queue/item/12345/)
            queue_parts = location.rstrip("/").split("/")
            if queue_parts and queue_parts[-2] == "item":
                try:
                    queue_id = int(queue_parts[-1])
                except ValueError:
                    pass

        return {
            "status": "triggered",
            "job_name": job_name,
            "queue_id": queue_id,
            "build_number": next_build_number,
            "job_url": job_info["url"],
            "build_url": f"{job_info['url']}{next_build_number}/",
        }
    except Exception as e:
        raise ValueError(f"Error triggering build for {job_name}: {str(e)}")


@mcp.tool()
def get_build_status(
    ctx: Context, job_name: str, build_number: Optional[int] = None
) -> dict:
    """Get build status

    Args:
        job_name: Name of the job
        build_number: Build number to check, defaults to latest

    Returns:
        Build information dictionary
    """
    client = ctx.request_context.lifespan_context.client
    if build_number is None:
        build_number = client.get_job_info(job_name)["lastBuild"]["number"]
    return client.get_build_info(job_name, build_number)
