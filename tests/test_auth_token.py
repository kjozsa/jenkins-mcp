import pytest
import os
from unittest.mock import MagicMock, patch
import requests
from jenkins_mcp.server import trigger_build, JenkinsContext
from mcp.server.fastmcp import Context


@pytest.fixture
def mock_env():
    """Set up environment variables for testing with API token"""
    original_env = os.environ.copy()
    os.environ["JENKINS_URL"] = "http://localhost:8080"
    os.environ["JENKINS_USERNAME"] = "testuser"
    os.environ["JENKINS_PASSWORD"] = "api-token-123"  # API token instead of password
    os.environ["JENKINS_USE_API_TOKEN"] = "true"
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_jenkins_client():
    """Mock Jenkins client for API token testing"""
    mock_client = MagicMock()
    mock_client.server = "http://localhost:8080"
    mock_client.auth = ("testuser", "api-token-123")

    # Mock job info
    mock_client.get_job_info.return_value = {
        "name": "test-job",
        "url": "http://localhost:8080/job/test-job/",
        "nextBuildNumber": 42,
    }

    # Mock build job
    mock_client.build_job.return_value = 123  # queue ID

    return mock_client


@pytest.fixture
def mock_session():
    """Mock requests session"""
    return MagicMock(spec=requests.Session)


@pytest.fixture
def mock_jenkins_context(mock_jenkins_client, mock_session):
    """Create a mock JenkinsContext for API token auth"""
    return JenkinsContext(
        client=mock_jenkins_client,
        jenkins_url="http://localhost:8080",
        username="testuser",
        password="api-token-123",
        session=mock_session,
        crumb_data=None,  # No crumb data for API token auth
    )


@pytest.fixture
def mock_context(mock_jenkins_context):
    """Mock MCP context with Jenkins context for API token auth"""

    class MockRequestContext:
        def __init__(self):
            self.lifespan_context = mock_jenkins_context

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context = MockRequestContext()
    return mock_ctx


@patch("jenkins_mcp.server.get_jenkins_crumb")
def test_lifespan_skips_crumb_with_token(mock_get_crumb, mock_env):
    """Test that lifespan skips crumb fetching when using API token"""
    from jenkins_mcp.server import jenkins_lifespan
    import asyncio
    from mcp.server.fastmcp import FastMCP

    # Create a mock FastMCP instance
    mock_server = MagicMock(spec=FastMCP)

    # Run the lifespan context manager
    async def run_lifespan():
        async with jenkins_lifespan(mock_server) as context:
            # Verify context has no crumb data
            assert context.crumb_data is None
            # Verify get_jenkins_crumb was not called
            mock_get_crumb.assert_not_called()

    # Run the async test
    asyncio.run(run_lifespan())


def test_trigger_build_with_token(mock_context):
    """Test triggering a build with API token auth"""
    with patch("jenkins_mcp.server.make_jenkins_request") as mock_request:
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"Location": "http://localhost:8080/queue/item/123/"}
        mock_request.return_value = mock_response

        # Call trigger_build
        result = trigger_build(mock_context, "test-job")

        # Verify result
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123
        assert result["build_number"] == 42

        # Verify make_jenkins_request was called
        mock_request.assert_called_once_with(
            mock_context.request_context.lifespan_context,
            "POST",
            "job/test-job/build",
            params=None,
        )


def test_trigger_build_with_token_and_parameters(mock_context):
    """Test triggering a parameterized build with API token auth"""
    with patch("jenkins_mcp.server.make_jenkins_request") as mock_request:
        # Set up mock response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"Location": "http://localhost:8080/queue/item/123/"}
        mock_request.return_value = mock_response

        # Call trigger_build with parameters
        parameters = {"param1": "value1", "param2": "value2"}
        result = trigger_build(mock_context, "test-job", parameters)

        # Verify result
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123
        assert result["build_number"] == 42

        # Verify make_jenkins_request was called with parameters
        mock_request.assert_called_once_with(
            mock_context.request_context.lifespan_context,
            "POST",
            "job/test-job/buildWithParameters",
            params=parameters,
        )
