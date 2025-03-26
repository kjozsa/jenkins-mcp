import pytest
import os
from unittest.mock import MagicMock
import responses
from jenkins_mcp.server import get_jenkins_crumb, trigger_build
from mcp.server.fastmcp import Context


@pytest.fixture
def mock_env():
    """Set up environment variables for testing"""
    original_env = os.environ.copy()
    os.environ["JENKINS_URL"] = "http://localhost:8080"
    os.environ["JENKINS_USERNAME"] = "testuser"
    os.environ["JENKINS_PASSWORD"] = "testpassword"
    os.environ["JENKINS_USE_API_TOKEN"] = "false"
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_jenkins_client():
    """Mock Jenkins client"""
    mock_client = MagicMock()
    mock_client.server = "http://localhost:8080"
    mock_client.auth = ("testuser", "testpassword")

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
def mock_context(mock_jenkins_client):
    """Mock MCP context with Jenkins client"""

    class MockLifespanContext:
        def __init__(self):
            self.client = mock_jenkins_client
            self.crumb_data = {"Jenkins-Crumb": "test-crumb-value"}
            self.session_cookies = {"JSESSIONID": "test-session-id"}

    class MockRequestContext:
        def __init__(self):
            self.lifespan_context = MockLifespanContext()

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context = MockRequestContext()
    return mock_ctx


def test_get_jenkins_crumb():
    """Test getting CSRF crumb from Jenkins"""
    with responses.RequestsMock() as rsps:
        # Mock the crumb API response
        rsps.add(
            responses.GET,
            'http://localhost:8080/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,":",//crumb)',
            body="Jenkins-Crumb:test-crumb-value",
            status=200,
            cookies={"JSESSIONID": "test-session-id"},
        )

        # Call the function
        crumb_data, session_cookies = get_jenkins_crumb(
            "http://localhost:8080", "testuser", "testpassword"
        )

        # Verify response
        assert crumb_data == {"Jenkins-Crumb": "test-crumb-value"}
        assert "JSESSIONID" in session_cookies
        assert session_cookies["JSESSIONID"] == "test-session-id"


def test_trigger_build_with_crumb(mock_context):
    """Test triggering a build with CSRF crumb"""
    with responses.RequestsMock() as rsps:
        # Mock the build job endpoint
        rsps.add(
            responses.POST,
            "http://localhost:8080/job/test-job/build",
            status=201,
            headers={"Location": "http://localhost:8080/queue/item/123/"},
        )

        # Call trigger_build
        result = trigger_build(mock_context, "test-job")

        # Verify result
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123
        assert result["build_number"] == 42

        # Check that the request was made with the crumb
        request = rsps.calls[0].request
        assert "Jenkins-Crumb" in request.headers
        assert request.headers["Jenkins-Crumb"] == "test-crumb-value"

        # Check that the session cookie was included
        assert "Cookie" in request.headers
        assert "JSESSIONID=test-session-id" in request.headers["Cookie"]


def test_trigger_build_with_parameters(mock_context):
    """Test triggering a parameterized build with CSRF crumb"""
    with responses.RequestsMock() as rsps:
        # Mock the build with parameters endpoint
        rsps.add(
            responses.POST,
            "http://localhost:8080/job/test-job/buildWithParameters",
            status=201,
            headers={"Location": "http://localhost:8080/queue/item/123/"},
        )

        # Call trigger_build with parameters
        parameters = {"param1": "value1", "param2": "value2"}
        result = trigger_build(mock_context, "test-job", parameters)

        # Verify result
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123
        assert result["build_number"] == 42

        # Check that parameters were included in the request
        request = rsps.calls[0].request
        assert "param1=value1" in request.url
        assert "param2=value2" in request.url


def test_fallback_to_standard_method(mock_context, mock_jenkins_client):
    """Test fallback to standard method when custom request fails"""
    # Make the custom request fail
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "http://localhost:8080/job/test-job/build",
            status=500,  # Error status to trigger fallback
        )

        # Call trigger_build
        result = trigger_build(mock_context, "test-job")

        # Verify result - should use the fallback method
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123  # From the mock client

        # Verify the client's build_job method was called
        mock_jenkins_client.build_job.assert_called_once_with(
            "test-job", parameters=None
        )
