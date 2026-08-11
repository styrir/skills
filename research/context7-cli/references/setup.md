# Setup

## ctx7 setup
One-time command to configure Context7 for your AI coding agent.

Modes:
- MCP server
- CLI + Skills

```bash
ctx7 setup
ctx7 setup --mcp
ctx7 setup --cli
ctx7 setup --cli --claude
ctx7 setup --cli --cursor
ctx7 setup --cli --universal
ctx7 setup --project
ctx7 setup --yes
```

Authentication options:
```bash
ctx7 setup --api-key YOUR_KEY
ctx7 setup --oauth
```

CLI + Skills mode installs a `find-docs` skill in the selected agent skills directory.
