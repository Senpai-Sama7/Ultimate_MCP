# Ultimate MCP - AI Tools Configuration Guide

This guide shows you how to configure Ultimate MCP to work with multiple AI development tools.

## Prerequisites

1. **Ultimate MCP must be running**:
   ```bash
   cd /path/to/Ultimate_MCP
   ./deploy.sh
   ```

2. **Verify the backend is accessible**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"service":"ok","neo4j":true,...}
   ```

---

## 🤖 Supported AI Tools

Ultimate MCP works with:
- ✅ **Claude Code** - Anthropic's CLI
- ✅ **Codex CLI** - OpenAI's development tool
- ✅ **Gemini CLI** - Google's command-line assistant
- ✅ **Amazon Q Developer** - AWS's AI assistant

---

## 1. Claude Code Configuration

**Config File**: `~/.config/Claude/claude_desktop_config.json`

### Already Configured!

Your Claude Code is already configured with Ultimate MCP:

```json
{
  "mcpServers": {
    "ultimate-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-fetch",
        "http://localhost:8000/mcp"
      ],
      "env": {
        "AUTH_TOKEN": "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"
      }
    }
  }
}
```

### Usage

1. Restart Claude Code CLI
2. The Ultimate MCP tools will be automatically available:
   - `lint` - Code quality checking
   - `execute` - Safe code execution
   - `test` - Run test suites
   - `generate` - Code generation from templates
   - `graph` - Neo4j knowledge graph operations

---

## 2. Codex CLI Configuration

**Config File**: `~/.codex/config.toml`

### Configuration Added!

Your Codex CLI now has Ultimate MCP configured:

```toml
[mcp.ultimate-mcp]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8000/mcp"]

[mcp.ultimate-mcp.env]
AUTH_TOKEN = "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"
```

### Installation

If you don't have Codex CLI yet:

```bash
npm install -g @openai/codex
```

### Usage

```bash
# List available MCP servers
codex mcp list

# Use Ultimate MCP tools in conversations
codex "use the lint tool to check my code quality"
codex "execute this Python script safely"
codex "query the knowledge graph for related components"
```

### Alternative CLI Command

You can also add servers via command:

```bash
codex mcp add ultimate-mcp -- npx -y @modelcontextprotocol/server-fetch http://localhost:8000/mcp
```

---

## 3. Gemini CLI Configuration

**Config File**: `~/.gemini/settings.json`

### Configuration Added!

Your Gemini CLI now has Ultimate MCP configured:

```json
{
  "mcpServers": {
    "ultimate-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-fetch",
        "http://localhost:8000/mcp"
      ],
      "env": {
        "AUTH_TOKEN": "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"
      }
    }
  }
}
```

### Installation

If you don't have Gemini CLI yet:

```bash
npm install -g @google/gemini-cli@latest
```

### Usage

```bash
# List MCP servers
gemini mcp list

# Use Ultimate MCP tools
gemini "lint my TypeScript files"
gemini "run the test suite and show results"
gemini "store this component relationship in the graph"
```

### Alternative: FastMCP Installation

For Python-based servers:

```bash
pip install fastmcp>=2.12.3
fastmcp install gemini-cli
```

---

## 4. Amazon Q Developer Configuration

**Config File**: `~/.aws/amazonq/mcp.json`

### Configuration Added!

Your Amazon Q Developer now has Ultimate MCP configured:

```json
{
  "mcpServers": {
    "ultimate-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-fetch",
        "http://localhost:8000/mcp"
      ],
      "env": {
        "AUTH_TOKEN": "5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0"
      },
      "timeout": 60000,
      "disabled": false
    }
  }
}
```

### Installation

If you don't have Amazon Q CLI yet:

```bash
# Follow AWS documentation to install Amazon Q Developer
```

### Usage

```bash
# In Amazon Q CLI
q "use the lint tool to analyze code quality"
q "execute this script in a sandboxed environment"
q "query the knowledge graph for dependencies"
```

### IDE Configuration

For Amazon Q in VS Code or JetBrains:

1. Open the Amazon Q settings
2. Click "Configure MCP servers"
3. Add Ultimate MCP with:
   - **Name**: ultimate-mcp
   - **Transport**: stdio
   - **Command**: `npx -y @modelcontextprotocol/server-fetch http://localhost:8000/mcp`
   - **Environment**: `AUTH_TOKEN=5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0`

---

## 🔧 Available Ultimate MCP Tools

All configured AI tools can now access these capabilities:

### 1. **Lint Tool**
```bash
# Check code quality
"Lint my Python files and show issues"
```

**Features**:
- Linting for Python (pylint, flake8, black)
- JavaScript/TypeScript (eslint, prettier)
- JSON validation
- Shell script checking (shellcheck)

### 2. **Execute Tool**
```bash
# Run code safely
"Execute this Python script: print('Hello')"
```

**Features**:
- Safe sandboxed execution
- Python, Node.js, shell script support
- Timeout protection
- Resource limits

### 3. **Test Tool**
```bash
# Run test suites
"Run all tests and show coverage"
```

**Features**:
- pytest for Python
- jest for JavaScript
- Code coverage reporting
- Test result parsing

### 4. **Generate Tool**
```bash
# Generate code from templates
"Generate a FastAPI CRUD endpoint for User model"
```

**Features**:
- Template-based code generation
- Multiple framework support
- Customizable templates

### 5. **Graph Tool**
```bash
# Knowledge graph operations
"Store this component relationship in the graph"
"Query all dependencies of UserService"
```

**Features**:
- Neo4j graph database integration
- Node and relationship management
- Cypher query execution
- Pattern matching

---

## 🧪 Testing the Configuration

Test each tool to verify Ultimate MCP is working:

### Claude Code
```bash
# In Claude Code CLI
"List available MCP servers"
"Use the lint tool to check my code"
```

### Codex CLI
```bash
codex mcp list
codex "lint my code using ultimate-mcp"
```

### Gemini CLI
```bash
gemini mcp list
gemini "execute this script using ultimate-mcp"
```

### Amazon Q
```bash
q "show available MCP servers"
q "use graph tool to query dependencies"
```

---

## 🔐 Security Notes

### Authentication Token

The auth token `5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0` is:
- ✅ Stored in `.env.deploy` (not committed to git)
- ✅ Required for all MCP requests
- ✅ Configured automatically in all tools

### Changing the Token

To use a different token:

1. Update `~/Documents/projects/Ultimate_MCP/.env.deploy`:
   ```bash
   AUTH_TOKEN=your_new_token_here
   ```

2. Restart Ultimate MCP:
   ```bash
   cd ~/Documents/projects/Ultimate_MCP
   ./deploy.sh
   ```

3. Update all AI tool configurations with the new token

---

## 🐛 Troubleshooting

### "Failed to connect to ultimate-mcp"

**Solution**: Ensure Ultimate MCP is running:
```bash
docker ps | grep ultimate
# Should show 3 containers: backend, frontend, neo4j

curl http://localhost:8000/health
# Should return: {"service":"ok","neo4j":true}
```

### "Authentication failed"

**Solution**: Verify the auth token matches:
```bash
grep AUTH_TOKEN ~/Documents/projects/Ultimate_MCP/.env.deploy
# Should show: AUTH_TOKEN=5023cabb45e57ec1498a2f85b310c17cd295e6dd52c8acb0
```

### "MCP server not found"

**Solution**: Verify configuration files exist:
```bash
# Claude Code
cat ~/.config/Claude/claude_desktop_config.json

# Codex CLI
cat ~/.codex/config.toml

# Gemini CLI
cat ~/.gemini/settings.json

# Amazon Q
cat ~/.aws/amazonq/mcp.json
```

### Tool-Specific Issues

**Codex CLI**:
```bash
# Check MCP status
codex mcp list

# Restart Codex
codex --version
```

**Gemini CLI**:
```bash
# Check MCP status
gemini mcp list

# Clear cache
rm -rf ~/.gemini/tmp/*
```

**Amazon Q**:
```bash
# Check logs
tail -f ~/.aws/amazonq/lspLog.log
```

---

## 📚 Additional Resources

- **Ultimate MCP Documentation**: `README.md` in this project
- **Model Context Protocol Spec**: https://modelcontextprotocol.io/
- **Codex CLI Docs**: https://developers.openai.com/codex/cli
- **Gemini CLI Docs**: https://cloud.google.com/gemini/docs/codeassist/gemini-cli
- **Amazon Q Docs**: https://docs.aws.amazon.com/amazonq/

---

## 🎉 You're All Set!

All four AI tools are now configured to use Ultimate MCP. You can:

✅ Use powerful code quality tools across all platforms
✅ Execute code safely in sandboxed environments
✅ Leverage Neo4j knowledge graphs for relationship tracking
✅ Generate code from templates
✅ Run comprehensive test suites

**Next Steps**:
1. Restart each AI tool to load the new configuration
2. Test Ultimate MCP tools with simple commands
3. Explore advanced features like graph queries
4. Build custom templates for code generation

Happy coding with Ultimate MCP! 🚀
