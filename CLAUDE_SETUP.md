# Configure Claude Desktop for Ultimate MCP

## Quick Setup

### 1. Deploy Ultimate MCP Server

```bash
cd ~/Documents/projects/Ultimate_MCP
./deploy.sh
```

This starts the MCP server at `http://localhost:8000`

### 2. Get Your Auth Token

```bash
grep '^AUTH_TOKEN=' .env.deploy | cut -d= -f2-
```

Copy this token - you'll need it for the config.

### 3. Configure Claude Desktop

**Location**: `~/.config/Claude/claude_desktop_config.json`

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
        "AUTH_TOKEN": "YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Replace `YOUR_TOKEN_HERE`** with the token from step 2.

### 4. Restart Claude Desktop

Close and reopen Claude Desktop to load the new configuration.

### 5. Verify Connection

In Claude Desktop, you should see the MCP server connected with these tools:
- `enhanced_execute` - Execute code with security
- `lint_code` - Lint Python/JavaScript code
- `execute_code` - Run code in sandbox
- `run_tests` - Execute pytest tests
- `generate_code` - Generate from templates
- `graph_upsert` - Store data in Neo4j
- `graph_query` - Query Neo4j graph

---

## Alternative: Direct Python Server

If you prefer running the server directly:

### 1. Start Server Manually

```bash
cd ~/Documents/projects/Ultimate_MCP/backend
source .venv/bin/activate
export AUTH_TOKEN=$(openssl rand -hex 24)
export NEO4J_PASSWORD=your_neo4j_password
uvicorn mcp_server.server:app --host 0.0.0.0 --port 8000
```

### 2. Configure Claude Desktop

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
        "AUTH_TOKEN": "YOUR_TOKEN_FROM_STEP_1"
      }
    }
  }
}
```

---

## Using stdio Transport (Advanced)

For direct stdio connection without HTTP:

```json
{
  "mcpServers": {
    "ultimate-mcp": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.stdio_server"
      ],
      "cwd": "/home/donovan/Documents/projects/Ultimate_MCP/backend",
      "env": {
        "PYTHONPATH": "/home/donovan/Documents/projects/Ultimate_MCP/backend",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "YOUR_NEO4J_PASSWORD",
        "AUTH_TOKEN": "YOUR_AUTH_TOKEN"
      }
    }
  }
}
```

---

## Troubleshooting

### Server Not Connecting

1. **Check server is running**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check MCP endpoint**:
   ```bash
   curl http://localhost:8000/mcp
   ```

3. **View Claude logs**:
   - macOS: `~/Library/Logs/Claude/`
   - Linux: `~/.config/Claude/logs/`

### Auth Token Issues

If you get 401 errors, regenerate token:
```bash
openssl rand -hex 24
```

Update both `.env.deploy` and Claude config.

### Port Conflicts

If port 8000 is in use, change it:
```bash
# Edit .env.deploy
BACKEND_PORT=8001

# Restart
./deploy.sh

# Update Claude config to http://localhost:8001/mcp
```

---

## Testing the Connection

Once configured, ask Claude:

> "Can you execute this Python code: print('Hello from Ultimate MCP!')"

Claude should use the `enhanced_execute` tool to run the code.

---

## Available Tools

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `enhanced_execute` | Execute code with security | No |
| `lint_code` | Lint Python/JS code | No |
| `execute_code` | Sandboxed execution | Yes |
| `run_tests` | Run pytest tests | Yes |
| `generate_code` | Template generation | Yes |
| `graph_upsert` | Store in Neo4j | Yes |
| `graph_query` | Query Neo4j | No |

---

## Security Notes

- Auth token is required for write operations
- Code execution is sandboxed with resource limits
- All operations are logged to Neo4j
- Rate limiting is enforced (10 req/min for execute)

---

## Full Config Example

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
        "AUTH_TOKEN": "abc123def456..."
      }
    }
  },
  "globalShortcut": "CommandOrControl+Shift+Space"
}
```

Save to: `~/.config/Claude/claude_desktop_config.json`

Then restart Claude Desktop.
