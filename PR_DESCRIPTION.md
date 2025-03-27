# Fix Jenkins CSRF Crumb Handling and Add API Token Support

## Problem

When using the Jenkins MCP server to trigger builds, users may encounter 403 "Forbidden" errors with the message:
```
No valid crumb was included in the request
```

This happens because Jenkins implements CSRF (Cross-Site Request Forgery) protection using a system called "crumbs".
A crumb is a token that must be included with POST requests to verify they come from an authorized source.

The current implementation doesn't handle these crumbs properly, which leads to build requests failing when:
1. CSRF protection is enabled on the Jenkins server (default setting)
2. Using username/password authentication instead of API tokens
3. When session cookies expire or aren't maintained between requests
4. When crumbs expire during a long-running session

## Solution

This PR implements a robust solution to the CSRF issue with significant improvements:

### 1. Comprehensive CSRF Crumb Handling (Default)

For username/password authentication, the MCP server now:
- Creates and maintains a proper session with Jenkins
- Fetches a CSRF crumb from Jenkins at the beginning of the session
- Includes the crumb in the headers of all POST requests
- Automatically refreshes the crumb when it expires or becomes invalid
- Provides detailed error reporting for authentication failures

### 2. API Token Authentication (Alternative)

Maintained support for API token authentication which is exempt from CSRF protection:
- Configure with `JENKINS_USE_API_TOKEN` environment variable (default: false)
- When enabled, sets `JENKINS_PASSWORD` to the API token value
- Jenkins 2.96+ doesn't require CSRF crumbs for API token authentication
- Simplifies configuration in environments where getting crumbs is problematic

## Implementation Details

1. **Improved CSRF Crumb Handling**:
   - Completely refactored the crumb handling implementation
   - Added a dedicated `make_jenkins_request()` function for all Jenkins API calls
   - Implemented proper session management with request cookies
   - Added automatic crumb refresh when authentication fails
   - Enhanced error handling and reporting

2. **Enhanced Context Management**:
   - Updated the `JenkinsContext` class to store all necessary session information
   - Properly manages session lifecycle including cleanup
   - Maintains consistent authentication state throughout the MCP server lifetime

3. **Reference Implementation**:
   - Added a standalone `scripts/jenkins_api_fix.py` reference implementation
   - Demonstrates the correct approach to Jenkins API communication with CSRF protection
   - Can be used for testing and troubleshooting Jenkins connectivity issues
   - Includes comprehensive documentation in `scripts/README.md`

4. **Testing**:
   - Updated test suite to verify both authentication methods
   - Added specific tests for crumb refresh functionality
   - Improved test mocking for more realistic Jenkins API simulation
   - Ensured high test coverage of all authentication paths

## Testing Done

- Tested with Jenkins 2.426.3 with CSRF protection enabled
- Verified automatic crumb refresh works when authentication fails
- Confirmed both authentication methods work correctly
- Added unit tests with extensive code coverage
- Tested with parameterized builds and various Jenkins configurations

## Configuration

Users can now choose between:

1. **Username/Password with Automatic Crumb Handling**:
```json
"env": {
  "JENKINS_URL": "https://jenkins-server/",
  "JENKINS_USERNAME": "username",
  "JENKINS_PASSWORD": "password",
  "JENKINS_USE_API_TOKEN": "false"
}
```

2. **API Token Authentication**:
```json
"env": {
  "JENKINS_URL": "https://jenkins-server/",
  "JENKINS_USERNAME": "username",
  "JENKINS_PASSWORD": "your-api-token",
  "JENKINS_USE_API_TOKEN": "true"
}
```

## Troubleshooting

If you encounter authentication issues:

1. Verify your Jenkins URL, username, and password are correct
2. Check if your Jenkins server has CSRF protection enabled
3. Verify that the crumbIssuer API is accessible
4. Try using an API token instead of a password
5. Check Jenkins server logs for more details on authentication failures

The reference implementation in `scripts/jenkins_api_fix.py` can be used to test Jenkins connectivity independently of the MCP server.

## References

- [Jenkins Security Documentation](https://www.jenkins.io/doc/book/security/)
- [Jenkins CSRF Protection](https://www.jenkins.io/doc/book/security/csrf-protection/)
- [SECURITY-626 Changes](https://www.jenkins.io/doc/upgrade-guide/2.176/#SECURITY-626)
