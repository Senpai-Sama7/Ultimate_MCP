# Ultimate MCP - Quick Start Guide

## 🚀 30-Second Setup

### 1. Start Ultimate MCP
```bash
cd ~/Documents/projects/Ultimate_MCP
./deploy.sh
```

### 2. Verify It's Running
```bash
curl http://localhost:8000/health
# Should return: {"service":"ok","neo4j":true}
```

### 3. Restart Your AI Tool

**All configurations are already in place!** Just restart your preferred tool:

| Tool | Config Location | Restart Command |
|------|----------------|-----------------|
| **Claude Code** | `~/.config/Claude/claude_desktop_config.json` | Restart Claude CLI |
| **Codex CLI** | `~/.codex/config.toml` | `codex --version` |
| **Gemini CLI** | `~/.gemini/settings.json` | `gemini --version` |
| **Amazon Q** | `~/.aws/amazonq/mcp.json` | Restart Amazon Q CLI |

---

## 🎯 Quick Commands

### Test Connection
```bash
# Claude Code
"List available MCP servers"

# Codex CLI
codex mcp list

# Gemini CLI
gemini mcp list

# Amazon Q
q "show available MCP servers"
```

### Use Tools
```bash
# Lint code
"Use the lint tool to check my Python files"

# Execute safely
"Execute this script: print('Hello')"

# Run tests
"Run all tests and show coverage"

# Query graph
"Query the knowledge graph for all User model dependencies"
```

---

## 📦 Available Tools

| Tool | Purpose | Example |
|------|---------|---------|
| **lint** | Code quality checking | "Lint my TypeScript files" |
| **execute** | Safe code execution | "Execute this Python script" |
| **test** | Run test suites | "Run all tests with coverage" |
| **generate** | Code from templates | "Generate a REST API endpoint" |
| **graph** | Neo4j knowledge graph | "Store component relationships" |

---

## ⚙️ What Was Configured

### Claude Code
```json
// ~/.config/Claude/claude_desktop_config.json
"ultimate-mcp": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8000/mcp"],
  "env": {"AUTH_TOKEN": "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"}
}
```

### Codex CLI
```toml
# ~/.codex/config.toml
[mcp.ultimate-mcp]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8000/mcp"]
[mcp.ultimate-mcp.env]
AUTH_TOKEN = "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"
```

### Gemini CLI
```json
// ~/.gemini/settings.json
"ultimate-mcp": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8000/mcp"],
  "env": {"AUTH_TOKEN": "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"}
}
```

### Amazon Q
```json
// ~/.aws/amazonq/mcp.json
"ultimate-mcp": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8000/mcp"],
  "env": {"AUTH_TOKEN": "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"},
  "timeout": 60000
}
```

---

## 🆘 Troubleshooting

### Server Not Running?
```bash
docker ps | grep ultimate
# Should show: backend, frontend, neo4j containers
```

### Can't Connect?
```bash
# Check backend
curl http://localhost:8000/health

# Check auth token
grep AUTH_TOKEN ~/Documents/projects/Ultimate_MCP/.env.deploy
```

### Tool Can't See Server?
```bash
# Check config files exist
ls -la ~/.codex/config.toml
ls -la ~/.gemini/settings.json
ls -la ~/.aws/amazonq/mcp.json
ls -la ~/.config/Claude/claude_desktop_config.json
```

---

## 📖 Full Documentation

See `AI_TOOLS_SETUP.md` for:
- Detailed installation instructions
- Advanced usage examples
- Security configuration
- Tool-specific guides
- Complete troubleshooting

---

## ✅ Success!

You're all set! Ultimate MCP is now available in:
- ✅ Claude Code
- ✅ Codex CLI
- ✅ Gemini CLI
- ✅ Amazon Q Developer

Start using powerful MCP tools across all your AI development platforms! 🎉
