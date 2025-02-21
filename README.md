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
Create a Windsurf MCP configuration in `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "jenkins-mcp": {
      "command": "uvx",
      "args": ["jenkins-mcp"],
      "env": {
        "JENKINS_URL": "https://your-jenkins-server/",
        "JENKINS_USERNAME": "your-username",
        "JENKINS_PASSWORD": "your-password"
      }
    }
  }
}
```

## Features
- List Jenkins jobs
- Trigger builds with optional parameters
- Check build status

## Development
```bash
# Install dependencies
uv pip install -r requirements.txt

# Run in dev mode with Inspector
mcp dev -p jenkins-mcp
