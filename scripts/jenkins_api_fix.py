#!/usr/bin/env python3
"""
Reference implementation for Jenkins API communication with CSRF protection.
This script demonstrates how to properly handle Jenkins authentication and CSRF protection
when making API requests.
"""

import requests
import os
import sys
import logging
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_jenkins_crumb(session, jenkins_url, username, password):
    """
    Get a CSRF crumb from Jenkins

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
            logger.warning(f"Failed to get Jenkins crumb: HTTP {response.status_code}")
            return None

        crumb_data = response.json()
        if (
            not crumb_data
            or "crumbRequestField" not in crumb_data
            or "crumb" not in crumb_data
        ):
            logger.warning(f"Invalid crumb response format: {response.text}")
            return None

        # Create the crumb header data
        crumb_header = {crumb_data["crumbRequestField"]: crumb_data["crumb"]}
        logger.info(f"Got Jenkins crumb: {crumb_data['crumbRequestField']}=<masked>")
        return crumb_header
    except Exception as e:
        logger.error(f"Error getting Jenkins crumb: {str(e)}")
        return None


def make_jenkins_request(
    session,
    jenkins_url,
    username,
    password,
    method,
    path,
    crumb=None,
    params=None,
    data=None,
    retry_on_auth_failure=True,
):
    """
    Make a request to Jenkins with proper CSRF protection

    Args:
        session: The requests Session object
        jenkins_url: Base URL of the Jenkins server
        username: Jenkins username
        password: Jenkins password or API token
        method: HTTP method (GET, POST, etc.)
        path: Path relative to Jenkins base URL
        crumb: Current CSRF crumb data
        params: Query parameters (for GET requests)
        data: Form data (for POST requests)
        retry_on_auth_failure: Whether to retry with a fresh crumb on 403 errors

    Returns:
        Response object from the request
    """
    url = urljoin(jenkins_url, path)
    headers = {}

    # Add crumb to headers if available
    if crumb:
        headers.update(crumb)

    try:
        response = session.request(
            method,
            url,
            auth=(username, password),
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
            logger.info("Crumb expired, refreshing and retrying request")
            # Get a fresh crumb
            new_crumb = get_jenkins_crumb(session, jenkins_url, username, password)
            if new_crumb:
                # Retry without the retry_on_auth_failure flag to prevent infinite loops
                return make_jenkins_request(
                    session,
                    jenkins_url,
                    username,
                    password,
                    method,
                    path,
                    crumb=new_crumb,
                    params=params,
                    data=data,
                    retry_on_auth_failure=False,
                )

        return response
    except Exception as e:
        logger.error(f"Error making Jenkins request: {str(e)}")
        raise


def list_jobs(session, jenkins_url, username, password, crumb=None):
    """
    List all Jenkins jobs

    Returns:
        List of job information dictionaries
    """
    response = make_jenkins_request(
        session,
        jenkins_url,
        username,
        password,
        "GET",
        "api/json?tree=jobs[name,url]",
        crumb=crumb,
    )

    if response.status_code != 200:
        logger.error(f"Failed to list jobs: HTTP {response.status_code}")
        return None

    data = response.json()
    return data.get("jobs", [])


def trigger_build(
    session, jenkins_url, username, password, job_name, parameters=None, crumb=None
):
    """
    Trigger a Jenkins build

    Args:
        session: The requests Session object
        jenkins_url: Base URL of the Jenkins server
        username: Jenkins username
        password: Jenkins password or API token
        job_name: Name of the job to build
        parameters: Optional build parameters as a dictionary
        crumb: Current CSRF crumb data

    Returns:
        Dictionary with build information
    """
    # First get job info to get the next build number
    response = make_jenkins_request(
        session,
        jenkins_url,
        username,
        password,
        "GET",
        f"job/{job_name}/api/json",
        crumb=crumb,
    )

    if response.status_code != 200:
        logger.error(f"Failed to get job info: HTTP {response.status_code}")
        return None

    job_info = response.json()
    next_build_number = job_info.get("nextBuildNumber", 0)

    # Determine the endpoint based on whether parameters are provided
    endpoint = (
        f"job/{job_name}/buildWithParameters" if parameters else f"job/{job_name}/build"
    )

    # Trigger the build
    response = make_jenkins_request(
        session,
        jenkins_url,
        username,
        password,
        "POST",
        endpoint,
        params=parameters,
        crumb=crumb,
    )

    if response.status_code not in (200, 201, 302):
        logger.error(
            f"Failed to trigger build: HTTP {response.status_code}, {response.text}"
        )
        return None

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
        "job_url": job_info.get("url"),
        "build_url": f"{job_info.get('url')}{next_build_number}/",
    }


def main():
    """Main function to demonstrate Jenkins API usage"""
    # Load environment variables
    jenkins_url = os.environ.get("JENKINS_URL")
    username = os.environ.get("JENKINS_USERNAME")
    password = os.environ.get("JENKINS_PASSWORD")

    if not jenkins_url or not username or not password:
        logger.error(
            "Missing required environment variables: JENKINS_URL, JENKINS_USERNAME, JENKINS_PASSWORD"
        )
        return 1

    # Create a session to maintain cookies
    session = requests.Session()

    try:
        # Get a CSRF crumb for authentication
        crumb = get_jenkins_crumb(session, jenkins_url, username, password)
        if not crumb:
            logger.warning("Could not get CSRF crumb, continuing without it")

        # List all jobs
        logger.info("Listing Jenkins jobs:")
        jobs = list_jobs(session, jenkins_url, username, password, crumb)
        if jobs:
            for job in jobs:
                logger.info(f"- {job['name']}: {job['url']}")
        else:
            logger.warning("No jobs found or could not list jobs")

        # Optionally trigger a build if job name is provided as an argument
        if len(sys.argv) > 1:
            job_name = sys.argv[1]
            parameters = {}

            # Check for optional parameters (format: param1=value1 param2=value2)
            if len(sys.argv) > 2:
                for param in sys.argv[2:]:
                    if "=" in param:
                        key, value = param.split("=", 1)
                        parameters[key] = value

            logger.info(f"Triggering build for job: {job_name}")
            if parameters:
                logger.info(f"With parameters: {parameters}")

            result = trigger_build(
                session, jenkins_url, username, password, job_name, parameters, crumb
            )
            if result:
                logger.info(f"Build triggered successfully: {result}")
            else:
                logger.error("Failed to trigger build")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1

    finally:
        # Always close the session
        session.close()


if __name__ == "__main__":
    sys.exit(main())
