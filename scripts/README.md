# Jenkins CSRF Protection Fix

This directory contains reference implementations and tools for working with Jenkins CSRF protection.

## Background on the Issue

Jenkins servers use CSRF (Cross-Site Request Forgery) protection to prevent unauthorized POST requests. This protection mechanism works by requiring a "crumb" token with each request that modifies Jenkins state.

When making API requests to Jenkins, you need to:

1. Establish an authenticated session
2. Obtain a CSRF crumb from Jenkins
3. Include this crumb in the headers of all subsequent POST requests
4. Maintain session continuity between requests
5. Handle cases where the crumb might expire

## Solution Implementation

We've implemented a proper CSRF protection handling system in the MCP server that:

- Maintains a session for each Jenkins connection
- Obtains a CSRF crumb at the beginning of the session
- Includes the crumb with all requests
- Automatically refreshes the crumb when it expires
- Properly handles authentication with both username/password and API token methods

## Reference Implementation

The `jenkins_api_fix.py` script provides a standalone reference implementation that demonstrates the correct approach to Jenkins API communication with CSRF protection. You can use this script to:

1. Test connectivity to your Jenkins server
2. Understand how CSRF protection works
3. Debug issues with Jenkins authentication
4. Use as a reference for implementing similar functionality in other systems

### Using the Script

1. Set environment variables:
   ```
   export JENKINS_URL=http://your-jenkins-server/
   export JENKINS_USERNAME=your-username
   export JENKINS_PASSWORD=your-password
   ```

2. Run the script to list all jobs:
   ```
   python jenkins_api_fix.py
   ```

3. Run the script to trigger a build:
   ```
   python jenkins_api_fix.py job-name
   ```

4. Run the script with parameters:
   ```
   python jenkins_api_fix.py job-name param1=value1 param2=value2
   ```

## Troubleshooting

If you encounter authentication issues:

1. Verify your Jenkins URL, username, and password are correct
2. Check if your Jenkins server has CSRF protection enabled
3. Verify that the crumbIssuer API is accessible
4. Try using an API token instead of a password
5. Check Jenkins server logs for more details on authentication failures
