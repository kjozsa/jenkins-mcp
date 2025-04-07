# Jenkins MCP
[![smithery badge](https://smithery.ai/badge/@kjozsa/jenkins-mcp)](https://smithery.ai/server/@kjozsa/jenkins-mcp)
MCP server for managing Jenkins operations.

<a href="https://glama.ai/mcp/servers/7j3zk84u5p">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/7j3zk84u5p/badge" alt="Jenkins MCP server" />
</a>

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
