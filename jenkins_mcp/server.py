from dataclasses import dataclass
from typing import AsyncIterator, List, Optional
from mcp.server.fastmcp import FastMCP, Context
import jenkins
from contextlib import asynccontextmanager
import os


@dataclass
class JenkinsContext:
    client: jenkins.Jenkins


@asynccontextmanager
async def jenkins_lifespan(server: FastMCP) -> AsyncIterator[JenkinsContext]:
    """Manage Jenkins client lifecycle"""
    # read .env
    import dotenv

    dotenv.load_dotenv()
    jenkins_url = os.environ["JENKINS_URL"]
    username = os.environ["JENKINS_USERNAME"]
    password = os.environ["JENKINS_PASSWORD"]

    try:
        client = jenkins.Jenkins(jenkins_url, username=username, password=password)
        yield JenkinsContext(client=client)
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
        
        # Trigger the build
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
