import pytest
import os
from unittest.mock import MagicMock, patch
import requests
from jenkins_mcp.server import (
    get_jenkins_crumb,
    trigger_build,
    make_jenkins_request,
    JenkinsContext,
)
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
def mock_session():
    """Mock requests session"""
    mock_session = MagicMock(spec=requests.Session)
    mock_session.cookies = {"JSESSIONID": "test-session-id"}
    return mock_session


@pytest.fixture
def mock_jenkins_context(mock_jenkins_client, mock_session):
    """Create a mock JenkinsContext"""
    return JenkinsContext(
        client=mock_jenkins_client,
        jenkins_url="http://localhost:8080",
        username="testuser",
        password="testpassword",
        session=mock_session,
        crumb_data={"Jenkins-Crumb": "test-crumb-value"},
    )


@pytest.fixture
def mock_context(mock_jenkins_context):
    """Mock MCP context with Jenkins context"""

    class MockRequestContext:
        def __init__(self):
            self.lifespan_context = mock_jenkins_context

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context = MockRequestContext()
    return mock_ctx


def test_get_jenkins_crumb():
    """Test getting CSRF crumb from Jenkins"""
    mock_session = MagicMock(spec=requests.Session)

    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "crumbRequestField": "Jenkins-Crumb",
        "crumb": "test-crumb-value",
    }

    # Configure the mock session to return our mock response
    mock_session.get.return_value = mock_response

    # Call the function
    crumb_data = get_jenkins_crumb(
        mock_session, "http://localhost:8080", "testuser", "testpassword"
    )

    # Verify response
    assert crumb_data == {"Jenkins-Crumb": "test-crumb-value"}

    # Verify the session was used correctly
    mock_session.get.assert_called_once_with(
        "http://localhost:8080/crumbIssuer/api/json", auth=("testuser", "testpassword")
    )


def test_make_jenkins_request(mock_jenkins_context):
    """Test making a request to Jenkins with CSRF protection"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Success"

    # Mock the session.request method
    mock_jenkins_context.session.request.return_value = mock_response

    # Call the function
    response = make_jenkins_request(mock_jenkins_context, "GET", "api/json")

    # Verify the response
    assert response.status_code == 200
    assert response.text == "Success"

    # Verify the request was made with the correct parameters
    mock_jenkins_context.session.request.assert_called_once_with(
        "GET",
        "http://localhost:8080/api/json",
        auth=("testuser", "testpassword"),
        headers={"Jenkins-Crumb": "test-crumb-value"},
        params=None,
        data=None,
    )


def test_make_jenkins_request_with_retry(mock_jenkins_context):
    """Test retrying a request when the crumb expires"""
    # Create mocked responses
    error_response = MagicMock()
    error_response.status_code = 403
    error_response.text = "No valid crumb was included in the request"

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.text = "Success"

    # Mock the session.request method to first return an error, then success
    mock_jenkins_context.session.request.side_effect = [
        error_response,
        success_response,
    ]

    # Mock get_jenkins_crumb to return a new crumb
    with patch("jenkins_mcp.server.get_jenkins_crumb") as mock_get_crumb:
        mock_get_crumb.return_value = {"Jenkins-Crumb": "new-crumb-value"}

        # Call the function
        response = make_jenkins_request(mock_jenkins_context, "POST", "api/json")

        # Verify the response
        assert response.status_code == 200
        assert response.text == "Success"

        # Verify get_jenkins_crumb was called
        mock_get_crumb.assert_called_once()

        # Verify the session.request was called twice
        assert mock_jenkins_context.session.request.call_count == 2


def test_trigger_build(mock_context):
    """Test triggering a build with CSRF crumb"""
    # Setup a mock response for the request
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {"Location": "http://localhost:8080/queue/item/123/"}

    # Mock the make_jenkins_request function
    with patch("jenkins_mcp.server.make_jenkins_request") as mock_request:
        mock_request.return_value = mock_response

        # Call trigger_build
        result = trigger_build(mock_context, "test-job")

        # Verify result
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123
        assert result["build_number"] == 42

        # Check that make_jenkins_request was called correctly
        mock_request.assert_called_once_with(
            mock_context.request_context.lifespan_context,
            "POST",
            "job/test-job/build",
            params=None,
        )


def test_trigger_build_with_parameters(mock_context):
    """Test triggering a parameterized build with CSRF crumb"""
    # Setup a mock response for the request
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.headers = {"Location": "http://localhost:8080/queue/item/123/"}

    # Mock the make_jenkins_request function
    with patch("jenkins_mcp.server.make_jenkins_request") as mock_request:
        mock_request.return_value = mock_response

        # Call trigger_build with parameters
        parameters = {"param1": "value1", "param2": "value2"}
        result = trigger_build(mock_context, "test-job", parameters)

        # Verify result
        assert result["status"] == "triggered"
        assert result["job_name"] == "test-job"
        assert result["queue_id"] == 123
        assert result["build_number"] == 42

        # Check that make_jenkins_request was called correctly
        mock_request.assert_called_once_with(
            mock_context.request_context.lifespan_context,
            "POST",
            "job/test-job/buildWithParameters",
            params=parameters,
        )
