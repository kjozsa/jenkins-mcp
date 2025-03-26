import pytest
import os
from unittest.mock import MagicMock, patch
from jenkins_mcp.server import trigger_build
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
        "nextBuildNumber": 42
    }

    # Mock build job
    mock_client.build_job.return_value = 123  # queue ID

    return mock_client


@pytest.fixture
def mock_context(mock_jenkins_client):
    """Mock MCP context with Jenkins client for API token auth"""
    class MockLifespanContext:
        def __init__(self):
            self.client = mock_jenkins_client
            # No crumb data or session cookies for API token auth
            self.crumb_data = None
            self.session_cookies = None

    class MockRequestContext:
        def __init__(self):
            self.lifespan_context = MockLifespanContext()

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context = MockRequestContext()
    return mock_ctx


@patch('jenkins_mcp.server.get_jenkins_crumb')
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
            assert context.session_cookies is None
            # Verify get_jenkins_crumb was not called
            mock_get_crumb.assert_not_called()

    # Run the async test
    asyncio.run(run_lifespan())


def test_trigger_build_with_token(mock_context, mock_jenkins_client):
    """Test triggering a build with API token auth"""
    # Call trigger_build
    result = trigger_build(mock_context, "test-job")

    # Verify result
    assert result["status"] == "triggered"
    assert result["job_name"] == "test-job"
    assert result["queue_id"] == 123
    assert result["build_number"] == 42

    # Verify the client's build_job method was called directly
    # (No custom request with crumb should happen)
    mock_jenkins_client.build_job.assert_called_once_with("test-job", parameters=None)


def test_trigger_build_with_token_and_parameters(mock_context, mock_jenkins_client):
    """Test triggering a parameterized build with API token auth"""
    # Call trigger_build with parameters
    parameters = {"param1": "value1", "param2": "value2"}
    result = trigger_build(mock_context, "test-job", parameters)

    # Verify result
    assert result["status"] == "triggered"
    assert result["job_name"] == "test-job"
    assert result["queue_id"] == 123
    assert result["build_number"] == 42

    # Verify client's build_job was called with parameters
    mock_jenkins_client.build_job.assert_called_once_with("test-job", parameters=parameters)
