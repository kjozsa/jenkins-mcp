from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Dict, Tuple
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
    # Store the crumb and session information
    crumb_data: Optional[Dict[str, str]] = None
    session_cookies: Optional[Dict[str, str]] = None


def get_jenkins_crumb(jenkins_url: str, username: str, password: str) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """
    Get a CSRF crumb from Jenkins

    Returns:
        Tuple of (crumb_data, session_cookies) where:
            crumb_data: Dictionary with the crumb field name and value
            session_cookies: Dictionary with any session cookies
    """
    try:
        crumb_url = urljoin(jenkins_url, "crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)")
        session = requests.Session()

        response = session.get(crumb_url, auth=(username, password))
        if response.status_code != 200:
            logging.warning(f"Failed to get Jenkins crumb: HTTP {response.status_code}")
            return None, None

        if ":" not in response.text:
            logging.warning(f"Invalid crumb response format: {response.text}")
            return None, None

        # Extract the crumb data
        field, value = response.text.split(":", 1)
        crumb_data = {field: value}

        # Get any session cookies
        session_cookies = dict(session.cookies)

        logging.info(f"Got Jenkins crumb: {field}=<masked>")
        return crumb_data, session_cookies
    except Exception as e:
        logging.error(f"Error getting Jenkins crumb: {str(e)}")
        return None, None


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

        # If we're not using an API token, get a crumb for CSRF protection
        crumb_data = None
        session_cookies = None
        if not use_token:
            crumb_data, session_cookies = get_jenkins_crumb(jenkins_url, username, password)

        yield JenkinsContext(client=client, crumb_data=crumb_data, session_cookies=session_cookies)
    finally:
        pass  # Jenkins client doesn't need explicit cleanup


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

    client = ctx.request_context.lifespan_context.client
    crumb_data = ctx.request_context.lifespan_context.crumb_data
    session_cookies = ctx.request_context.lifespan_context.session_cookies

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
        next_build_number = job_info['nextBuildNumber']

        # If we have crumb data, use it when triggering the build
        if crumb_data and session_cookies:
            # We need to make a custom request with the crumb and session cookies
            try:
                jenkins_url = client.server
                auth = (client.auth[0], client.auth[1])  # Username and password

                # Prepare the build URL
                build_url = urljoin(jenkins_url, f"job/{job_name}/build")

                # If there are parameters, use the buildWithParameters endpoint
                if parameters:
                    build_url = urljoin(jenkins_url, f"job/{job_name}/buildWithParameters")

                # Create a session to maintain cookies
                session = requests.Session()

                # Add session cookies
                for cookie_name, cookie_value in session_cookies.items():
                    session.cookies.set(cookie_name, cookie_value)

                # Make the request with the crumb in headers
                headers = dict(crumb_data)

                # Make the POST request
                if parameters:
                    response = session.post(build_url, headers=headers, auth=auth, params=parameters)
                else:
                    response = session.post(build_url, headers=headers, auth=auth)

                if response.status_code not in (200, 201):
                    raise ValueError(f"Failed to trigger build: HTTP {response.status_code}")

                queue_id = None
                location = response.headers.get('Location')
                if location:
                    # Extract queue ID from Location header (e.g., .../queue/item/12345/)
                    queue_parts = location.rstrip('/').split('/')
                    if queue_parts and queue_parts[-2] == 'item':
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
                    "build_url": f"{job_info['url']}{next_build_number}/"
                }
            except Exception as e:
                # If the custom request fails, log it and fall back to the original method
                logging.warning(f"Custom build request failed, falling back: {str(e)}")

        # Use the standard method if we don't have crumb data, or if the custom request failed
        queue_id = client.build_job(job_name, parameters=parameters)

        return {
            "status": "triggered",
            "job_name": job_name,
            "queue_id": queue_id,
            "build_number": next_build_number,
            "job_url": job_info["url"],
            "build_url": f"{job_info['url']}{next_build_number}/"
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
