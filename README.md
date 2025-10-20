# 🚀 Ultimate MCP Platform

**A complete AI development toolkit that lets you write, test, and execute code safely—even if you've never coded before.**

Think of this as your AI coding assistant's brain: it can check code for errors, run tests, execute programs safely, store knowledge in a graph database, and generate new code from templates. Perfect for AI agents, developers, and anyone building with Claude or other AI tools.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.23-008CC1.svg)](https://neo4j.com)

---

## 📋 Table of Contents

- [What Is This?](#-what-is-this)
- [Quick Start (3 Steps)](#-quick-start-3-steps)
- [What Can It Do?](#-what-can-it-do)
- [All Available Tools](#-all-available-tools)
- [Built-in AI Prompts](#-built-in-ai-prompts)
- [Real-World Examples](#-real-world-examples)
- [Accessing Your Services](#-accessing-your-services)
- [Troubleshooting](#-troubleshooting)
- [Advanced Usage](#-advanced-usage)

---

## 🎯 What Is This?

**Ultimate MCP** is a complete development platform that gives AI assistants (like Claude) powerful tools to:

- ✅ **Check code for errors** (linting)
- ✅ **Run code safely** in isolated containers
- ✅ **Execute tests** automatically
- ✅ **Generate new code** from templates
- ✅ **Store and query knowledge** in a graph database
- ✅ **Track relationships** between code, services, and data

**Who is this for?**
- 🤖 AI developers building agents with Claude, ChatGPT, or custom LLMs
- 👨‍💻 Software developers who want automated code quality tools
- 🎓 Students learning to code with AI assistance
- 🏢 Teams building internal developer tools

**What makes it special?**
- 🔒 **Secure by default** - Code runs in sandboxes, can't harm your system
- 🧠 **Memory included** - Neo4j graph database remembers everything
- 🔌 **MCP compatible** - Works with Claude Desktop and any MCP client
- 📦 **One-click deploy** - Everything runs in Docker containers

---

## ⚡ Quick Start (3 Steps)

### Prerequisites

You need these installed on your computer:
- **Docker Desktop** ([Download here](https://www.docker.com/products/docker-desktop))
- **Git** ([Download here](https://git-scm.com/downloads))

That's it! No Python, Node.js, or other tools needed.

### Step 1: Download the Project

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
git clone https://github.com/Senpai-Sama7/Ultimate_MCP.git
cd Ultimate_MCP
```

### Step 2: Start Everything

```bash
./deploy.sh
```

This single command will:
- ✅ Build all Docker containers
- ✅ Start Neo4j database
- ✅ Launch the backend API
- ✅ Start the web interface
- ✅ Generate secure passwords automatically

**Wait 1-2 minutes** for everything to start up.

### Step 3: Verify It's Working

Open your browser and visit:
- **Web Interface**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

If you see a green "OK" status, you're ready to go! 🎉

---

## 🛠️ What Can It Do?

### 1. **Code Quality Checking (Linting)**
Automatically finds bugs, style issues, and potential problems in your code.

**Example Use Case**: Before deploying code, check if it follows best practices.

### 2. **Safe Code Execution**
Runs Python code in an isolated sandbox that can't access your files or network.

**Example Use Case**: Test a code snippet from the internet without risking your computer.

### 3. **Automated Testing**
Runs your test suite and reports which tests pass or fail.

**Example Use Case**: Verify your changes didn't break existing functionality.

### 4. **Code Generation**
Creates new code from templates by filling in variables.

**Example Use Case**: Generate boilerplate code for new API endpoints.

### 5. **Knowledge Graph Storage**
Stores information about your code, services, and their relationships in a graph database.

**Example Use Case**: Track which microservices call each other and their dependencies.

### 6. **Graph Queries**
Search and analyze your stored knowledge using Cypher query language.

**Example Use Case**: Find all services written in Python that call the authentication service.

---

## 🔧 All Available Tools

### Tool 1: `lint_code` - Check Code Quality

**What it does**: Analyzes code for errors, style issues, and complexity.

**When to use it**: Before committing code, during code reviews, or when learning.

**Example Request**:
```bash
curl http://localhost:8000/lint_code \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def calculate_total(items):\n    total = 0\n    for item in items:\n        total += item.price\n    return total",
    "language": "python"
  }'
```

**Example Response**:
```json
{
  "id": "abc123",
  "code_hash": "e788cd4a...",
  "functions": ["calculate_total"],
  "classes": [],
  "imports": [],
  "complexity": 2.0,
  "linter_exit_code": 0,
  "linter_output": ""
}
```

**What the response means**:
- `functions`: List of function names found
- `complexity`: How complex the code is (lower is better)
- `linter_exit_code`: 0 means no errors found
- `linter_output`: Any warnings or errors

---

### Tool 2: `execute_code` - Run Code Safely

**What it does**: Executes Python code in a secure sandbox with resource limits.

**When to use it**: Testing code snippets, running calculations, or prototyping.

**Example Request**:
```bash
curl http://localhost:8000/execute_code \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import math\nresult = math.sqrt(144)\nprint(f\"Square root: {result}\")",
    "language": "python"
  }'
```

**Example Response**:
```json
{
  "id": "xyz789",
  "return_code": 0,
  "stdout": "Square root: 12.0\n",
  "stderr": "",
  "duration_seconds": 0.023
}
```

**What the response means**:
- `return_code`: 0 = success, non-zero = error
- `stdout`: What the program printed
- `stderr`: Any error messages
- `duration_seconds`: How long it took to run

**⚠️ Security Note**: Requires authentication token (found in `.env.deploy` file).

---

### Tool 3: `run_tests` - Execute Test Suites

**What it does**: Runs pytest tests and reports results.

**When to use it**: Continuous integration, before deployments, or during development.

**Example Request**:
```bash
curl http://localhost:8000/run_tests \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def add(a, b):\n    return a + b\n\ndef test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0",
    "language": "python"
  }'
```

**Example Response**:
```json
{
  "id": "test456",
  "return_code": 0,
  "stdout": "===== test session starts =====\ncollected 1 item\n\ntest_add PASSED [100%]\n\n===== 1 passed in 0.02s =====",
  "stderr": "",
  "duration_seconds": 0.156
}
```

**What the response means**:
- `return_code`: 0 = all tests passed
- `stdout`: Test results and summary
- Look for "PASSED" or "FAILED" in the output

---

### Tool 4: `generate_code` - Create Code from Templates

**What it does**: Fills in template variables to generate new code.

**When to use it**: Creating boilerplate, generating similar functions, or scaffolding.

**Example Request**:
```bash
curl http://localhost:8000/generate_code \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "def {{ function_name }}({{ params }}):\n    \"\"\"{{ docstring }}\"\"\"\n    return {{ return_value }}",
    "context": {
      "function_name": "get_user_age",
      "params": "user_id: int",
      "docstring": "Retrieve user age from database",
      "return_value": "database.query(user_id).age"
    }
  }'
```

**Example Response**:
```json
{
  "generated_code": "def get_user_age(user_id: int):\n    \"\"\"Retrieve user age from database\"\"\"\n    return database.query(user_id).age"
}
```

---

### Tool 5: `graph_upsert` - Store Knowledge

**What it does**: Saves nodes and relationships to the Neo4j graph database.

**When to use it**: Tracking services, storing code metadata, or building knowledge graphs.

**Example Request**:
```bash
curl http://localhost:8000/graph_upsert \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "nodes": [
      {
        "id": "auth_service",
        "labels": ["Service", "Microservice"],
        "properties": {
          "name": "Authentication Service",
          "language": "python",
          "version": "2.1.0",
          "port": 8080
        }
      },
      {
        "id": "user_db",
        "labels": ["Database"],
        "properties": {
          "name": "User Database",
          "type": "PostgreSQL",
          "host": "db.example.com"
        }
      }
    ],
    "relationships": [
      {
        "from": "auth_service",
        "to": "user_db",
        "type": "CONNECTS_TO",
        "properties": {
          "connection_pool_size": 20,
          "timeout_seconds": 30
        }
      }
    ]
  }'
```

**Example Response**:
```json
{
  "nodes_created": 2,
  "relationships_created": 1,
  "properties_set": 9
}
```

**Real-World Use Case**: Track your microservices architecture:
- Which services exist
- What languages they use
- How they connect to each other
- Performance metrics for each connection

---

### Tool 6: `graph_query` - Search Knowledge

**What it does**: Queries the graph database using Cypher language.

**When to use it**: Finding patterns, analyzing relationships, or generating reports.

**Example Request**:
```bash
curl http://localhost:8000/graph_query \
  -H "Content-Type: application/json" \
  -d '{
    "cypher": "MATCH (s:Service)-[r:CONNECTS_TO]->(d:Database) RETURN s.name AS service, d.name AS database, r.timeout_seconds AS timeout",
    "parameters": {}
  }'
```

**Example Response**:
```json
{
  "results": [
    {
      "service": "Authentication Service",
      "database": "User Database",
      "timeout": 30
    }
  ],
  "count": 1
}
```

**Common Query Examples**:

1. **Find all Python services**:
```cypher
MATCH (s:Service {language: "python"}) 
RETURN s.name, s.version
```

2. **Find services with high complexity**:
```cypher
MATCH (s:Service) 
WHERE s.complexity > 10 
RETURN s.name, s.complexity 
ORDER BY s.complexity DESC
```

3. **Find connection chains**:
```cypher
MATCH path = (s1:Service)-[:CONNECTS_TO*1..3]->(s2:Service) 
RETURN s1.name, s2.name, length(path) AS hops
```

---

## 🎭 Built-in AI Prompts

The platform includes 7 pre-configured AI assistant prompts for different tasks:

### 1. **proceed** - Senior Pair-Programmer
**Use when**: You need help writing or debugging code
**What it does**: Acts as an experienced developer helping you code
**Example**: "Help me implement a user authentication system"

### 2. **evaluate** - Comprehensive Audit
**Use when**: You need a thorough code review
**What it does**: Analyzes code quality, security, and best practices
**Example**: "Review this API endpoint for security issues"

### 3. **real-a** - Production Delivery
**Use when**: Preparing code for production deployment
**What it does**: Ensures code is production-ready with proper error handling
**Example**: "Make this code production-ready"

### 4. **test-a** - CI Quality Runner
**Use when**: Setting up automated testing
**What it does**: Creates comprehensive test suites
**Example**: "Generate tests for this function"

### 5. **improve** - Holistic Refactor
**Use when**: Code works but needs improvement
**What it does**: Refactors code for better performance and maintainability
**Example**: "Optimize this database query function"

### 6. **clean** - Repo Janitor
**Use when**: Codebase needs cleanup
**What it does**: Removes dead code, fixes formatting, updates dependencies
**Example**: "Clean up unused imports and format this file"

### 7. **synthesize** - Systems Integration
**Use when**: Connecting multiple services or systems
**What it does**: Helps integrate different components
**Example**: "Connect this API to the payment gateway"

**How to use prompts**:
```bash
# List all prompts
curl http://localhost:8000/prompts

# Get specific prompt
curl http://localhost:8000/prompts/proceed
```

---

## 💡 Real-World Examples

### Example 1: Building a REST API

**Scenario**: You're building a user management API and want to ensure quality.

**Step 1 - Generate the code**:
```bash
curl http://localhost:8000/generate_code \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "template": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.{{ method }}(\"/{{ endpoint }}\")\ndef {{ function_name }}():\n    return {{ response }}",
    "context": {
      "method": "get",
      "endpoint": "users",
      "function_name": "list_users",
      "response": "{\"users\": []}"
    }
  }'
```

**Step 2 - Check code quality**:
```bash
curl http://localhost:8000/lint_code \
  -d '{"code": "YOUR_GENERATED_CODE", "language": "python"}'
```

**Step 3 - Test it**:
```bash
curl http://localhost:8000/execute_code \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"code": "YOUR_GENERATED_CODE\nprint(list_users())", "language": "python"}'
```

**Step 4 - Store in knowledge graph**:
```bash
curl http://localhost:8000/graph_upsert \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "nodes": [{
      "id": "user_api",
      "labels": ["API", "Service"],
      "properties": {"name": "User API", "endpoint": "/users"}
    }]
  }'
```

---

### Example 2: Analyzing Your Microservices

**Scenario**: You have 10 microservices and want to understand their dependencies.

**Step 1 - Store all services**:
```bash
# Store each service (repeat for all services)
curl http://localhost:8000/graph_upsert \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "nodes": [
      {"id": "frontend", "labels": ["Service"], "properties": {"name": "Frontend", "language": "typescript"}},
      {"id": "auth", "labels": ["Service"], "properties": {"name": "Auth Service", "language": "python"}},
      {"id": "api", "labels": ["Service"], "properties": {"name": "API Gateway", "language": "go"}}
    ],
    "relationships": [
      {"from": "frontend", "to": "api", "type": "CALLS"},
      {"from": "api", "to": "auth", "type": "CALLS"}
    ]
  }'
```

**Step 2 - Find all dependencies**:
```bash
curl http://localhost:8000/graph_query \
  -d '{
    "cypher": "MATCH (s1:Service)-[:CALLS]->(s2:Service) RETURN s1.name AS caller, s2.name AS called",
    "parameters": {}
  }'
```

**Step 3 - Find critical services** (most dependencies):
```bash
curl http://localhost:8000/graph_query \
  -d '{
    "cypher": "MATCH (s:Service)<-[:CALLS]-(caller) RETURN s.name, count(caller) AS dependents ORDER BY dependents DESC",
    "parameters": {}
  }'
```

---

### Example 3: Learning Python with AI

**Scenario**: You're learning Python and want to practice with immediate feedback.

**Step 1 - Write code**:
```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))
```

**Step 2 - Check for issues**:
```bash
curl http://localhost:8000/lint_code \
  -d '{"code": "YOUR_CODE_HERE", "language": "python"}'
```

**Step 3 - Run it safely**:
```bash
curl http://localhost:8000/execute_code \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"code": "YOUR_CODE_HERE", "language": "python"}'
```

**Step 4 - Add tests**:
```bash
curl http://localhost:8000/run_tests \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "code": "YOUR_CODE_HERE\n\ndef test_fibonacci():\n    assert fibonacci(0) == 0\n    assert fibonacci(1) == 1\n    assert fibonacci(10) == 55",
    "language": "python"
  }'
```

---

## 🌐 Accessing Your Services

Once deployed, you can access:

| Service | URL | Purpose |
|---------|-----|---------|
| **Web Interface** | http://localhost:3000 | Visual dashboard for all tools |
| **API Documentation** | http://localhost:8000/docs | Interactive API testing (Swagger UI) |
| **Health Check** | http://localhost:8000/health | System status |
| **Metrics** | http://localhost:8000/metrics | Performance metrics |
| **Neo4j Browser** | http://localhost:7474 | Graph database interface |
| **Neo4j Bolt** | bolt://localhost:7687 | Direct database connection |

### Finding Your Authentication Token

Your secure token is in the `.env.deploy` file:

```bash
# View your token
cat .env.deploy | grep AUTH_TOKEN
```

Copy the value after `AUTH_TOKEN=` and use it in your requests:

```bash
curl http://localhost:8000/execute_code \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{"code": "print(\"Hello\")", "language": "python"}'
```

### Neo4j Database Access

**Username**: `neo4j`  
**Password**: Found in `.env.deploy` under `NEO4J_PASSWORD`

```bash
# View Neo4j password
cat .env.deploy | grep NEO4J_PASSWORD
```

---

## 🔧 Troubleshooting

### Problem: "Port already in use"

**Solution**: Another service is using the same port.

```bash
# Find what's using port 8000
lsof -i :8000

# Stop the conflicting service or change ports in .env.deploy
# Edit these lines:
# FRONTEND_HTTP_PORT=3001  (instead of 3000)
# NEO4J_HTTP_PORT=7475     (instead of 7474)
```

### Problem: "Cannot connect to Docker daemon"

**Solution**: Docker Desktop isn't running.

1. Open Docker Desktop application
2. Wait for it to fully start (whale icon in system tray)
3. Try `./deploy.sh` again

### Problem: "Authentication failed"

**Solution**: Using wrong or expired token.

```bash
# Get fresh token
cat .env.deploy | grep AUTH_TOKEN

# Use it in your request
curl -H "Authorization: Bearer PASTE_TOKEN_HERE" ...
```

### Problem: "Neo4j not healthy"

**Solution**: Database needs more time to start.

```bash
# Check Neo4j status
docker ps | grep neo4j

# Wait 30 seconds and check health
curl http://localhost:8000/health
```

### Problem: "Code execution timeout"

**Solution**: Code is taking too long or has infinite loop.

- Default timeout is 30 seconds
- Check your code for infinite loops
- Optimize slow operations

---

## 🚀 Advanced Usage

### Using with Claude Desktop

1. **Install Claude Desktop** from Anthropic
2. **Configure MCP** by editing `~/.config/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ultimate-mcp": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch", "http://localhost:8000/mcp"],
      "env": {
        "AUTH_TOKEN": "YOUR_TOKEN_FROM_ENV_DEPLOY"
      }
    }
  }
}
```

3. **Restart Claude Desktop**
4. **Test it**: Ask Claude "Can you lint this Python code for me?"

### Deploying to Production

**Option 1: Railway** (Recommended)
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

**Option 2: Docker Compose on VPS**
```bash
# On your server
git clone https://github.com/Senpai-Sama7/Ultimate_MCP.git
cd Ultimate_MCP
./deploy.sh

# Configure firewall
sudo ufw allow 8000/tcp
sudo ufw allow 3000/tcp
```

**Option 3: Kubernetes**
```bash
# Convert docker-compose to k8s
kompose convert -f deployment/docker-compose.yml

# Apply to cluster
kubectl apply -f .
```

### Custom Configuration

Edit `.env.deploy` to customize:

```bash
# Change ports
FRONTEND_HTTP_PORT=3000
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687

# Security
AUTH_TOKEN=your-secure-token-here
NEO4J_PASSWORD=your-secure-password-here

# Rate limiting
RATE_LIMIT_RPS=10  # Requests per second

# CORS (for web apps)
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Monitoring and Logs

**View logs**:
```bash
# All services
docker compose -f deployment/docker-compose.yml logs -f

# Specific service
docker logs deployment-backend-1 -f
docker logs ultimate_mcp_neo4j -f
```

**Check metrics**:
```bash
# Prometheus format
curl http://localhost:8000/metrics

# JSON format
curl http://localhost:8000/metrics | jq
```

### Backup Neo4j Data

```bash
# Create backup
docker exec ultimate_mcp_neo4j neo4j-admin database dump neo4j --to-path=/backups

# Copy to host
docker cp ultimate_mcp_neo4j:/backups/neo4j.dump ./backup-$(date +%Y%m%d).dump

# Restore backup
docker exec ultimate_mcp_neo4j neo4j-admin database load neo4j --from-path=/backups
```

---

## 📚 Additional Resources

- **Full API Documentation**: http://localhost:8000/docs (when running)
- **Neo4j Cypher Guide**: https://neo4j.com/docs/cypher-manual/current/
- **MCP Protocol Spec**: https://modelcontextprotocol.io/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Docker Guide**: https://docs.docker.com/get-started/

---

## 🤝 Contributing

We welcome contributions! Here's how:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Run tests**: `python scripts/smoke_test.py`
5. **Commit**: `git commit -m "Add amazing feature"`
6. **Push**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

See `AGENTS.md` for detailed contributor guidelines.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🆘 Getting Help

- **Issues**: [GitHub Issues](https://github.com/Senpai-Sama7/Ultimate_MCP/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Senpai-Sama7/Ultimate_MCP/discussions)
- **Documentation**: Check `docs/` folder for detailed guides

---

## 🎉 Quick Reference Card

**Most Common Commands**:
```bash
# Start everything
./deploy.sh

# Stop everything
docker compose -f deployment/docker-compose.yml down

# View logs
docker compose -f deployment/docker-compose.yml logs -f

# Check health
curl http://localhost:8000/health

# Get your token
cat .env.deploy | grep AUTH_TOKEN

# Lint code
curl http://localhost:8000/lint_code -d '{"code":"YOUR_CODE","language":"python"}'

# Execute code (needs token)
curl http://localhost:8000/execute_code -H "Authorization: Bearer TOKEN" -d '{"code":"print(42)","language":"python"}'
```

**Default Ports**:
- Frontend: 3000
- Backend: 8000
- Neo4j Browser: 7474
- Neo4j Bolt: 7687

**Important Files**:
- `.env.deploy` - Your passwords and tokens
- `deployment/docker-compose.yml` - Service configuration
- `backend/requirements.txt` - Python dependencies

---

**Made with ❤️ for the AI development community**
