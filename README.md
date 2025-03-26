# Jenkins MCP
[![smithery badge](https://smithery.ai/badge/@kjozsa/jenkins-mcp)](https://smithery.ai/server/@kjozsa/jenkins-mcp)
MCP server for managing Jenkins operations.

## Installation
### Installing via Smithery

To install Jenkins MCP for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@kjozsa/jenkins-mcp):

```bash
npx -y @smithery/cli install @kjozsa/jenkins-mcp --client claude
```

### Installing Manually
```bash
uvx install jenkins-mcp
```

## Configuration
Add the MCP server using the following JSON configuration snippet:

```json
{
  "mcpServers": {
    "jenkins-mcp": {
      "command": "uvx",
      "args": ["jenkins-mcp"],
      "env": {
        "JENKINS_URL": "https://your-jenkins-server/",
        "JENKINS_USERNAME": "your-username",
        "JENKINS_PASSWORD": "your-password",
        "JENKINS_USE_API_TOKEN": "false"
      }
    }
  }
}
```

## CSRF Crumb Handling

Jenkins implements CSRF protection using "crumbs" - tokens that must be included with POST requests. This MCP server handles CSRF crumbs in two ways:

1. **Default Mode**: Automatically fetches and includes CSRF crumbs with build requests
   - Uses session cookies to maintain the web session
   - Handles all the CSRF protection behind the scenes

2. **API Token Mode**: Uses Jenkins API tokens which are exempt from CSRF protection
   - Set `JENKINS_USE_API_TOKEN=true`
   - Set `JENKINS_PASSWORD` to your API token instead of password
   - Works with Jenkins 2.96+ which doesn't require crumbs for API token auth

You can generate an API token in Jenkins at: User → Configure → API Token → Add new Token

## Features
- List Jenkins jobs
- Trigger builds with optional parameters
- Check build status
- CSRF crumb handling for secure API access

## Development
```bash
# Install dependencies
uv pip install -r requirements.txt

# Run in dev mode with Inspector
mcp dev jenkins_mcp/server.py
```

## Testing

The MCP server includes tests for both authentication methods:

### Setup Test Environment

Use the provided setup script to create a test environment:

```bash
# Set up the test environment (creates a virtual environment and installs dependencies)
./setup_test_env.sh
```

### Running Tests

```bash
# Run all tests
./run_tests.sh

# Run specific test file
./run_tests.sh tests/test_auth_password.py
./run_tests.sh tests/test_auth_token.py

# Run tests with coverage reporting
./run_tests.sh --coverage

# Run specific tests with coverage reporting
./run_tests.sh tests/test_auth_password.py --coverage

# Generate HTML coverage report
./run_tests.sh --coverage --html
```

### Cleanup

When you're done with testing or need to clean up:

```bash
# Clean up test artifacts and caches
./clean_test_env.sh
```

### Test Coverage

The tests cover:

1. **Username/Password Authentication with CSRF Crumb**:
   - Getting a crumb from the Jenkins server
   - Triggering a build with the crumb and session cookies
   - Handling parameterized builds
   - Fallback behavior when crumb requests fail

2. **API Token Authentication**:
   - Verifying that crumb fetching is skipped
   - Using the Python Jenkins client directly for build requests
   - Handling parameterized builds

These tests ensure that both authentication methods work correctly and that the CSRF crumb handling is robust.

## Troubleshooting

If you encounter a "No valid crumb was included in the request" error:

1. Verify your Jenkins server has CSRF protection enabled
2. Try using API token authentication by setting `JENKINS_USE_API_TOKEN=true`
3. Check that your Jenkins session isn't expiring (newer Jenkins versions tie crumbs to sessions)
4. Ensure network connectivity between the MCP server and Jenkins is stable
