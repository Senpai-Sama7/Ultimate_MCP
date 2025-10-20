#!/usr/bin/env bash
set -euo pipefail

echo "=== Ultimate MCP Validation Script ==="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }

# Check Python
echo "Checking Python..."
python3 --version || fail "Python 3 not found"
pass "Python 3 installed"

# Check Node.js
echo "Checking Node.js..."
node --version || fail "Node.js not found"
pass "Node.js installed"

# Check Docker
echo "Checking Docker..."
docker --version || fail "Docker not found"
pass "Docker installed"

# Validate pyproject.toml
echo "Validating pyproject.toml..."
python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))" || fail "Invalid pyproject.toml"
pass "pyproject.toml valid"

# Validate package.json
echo "Validating CLI package.json..."
node -e "JSON.parse(require('fs').readFileSync('cli/package.json', 'utf8'))" || fail "Invalid package.json"
pass "package.json valid"

# Check Python syntax
echo "Checking Python syntax..."
python3 -m py_compile backend/mcp_server/enhanced_server.py || fail "Python syntax error"
pass "Python syntax valid"

# Check deploy.sh syntax
echo "Checking deploy.sh syntax..."
bash -n deploy.sh || fail "deploy.sh syntax error"
pass "deploy.sh syntax valid"

# Check required files
echo "Checking required files..."
for file in README.md LICENSE pyproject.toml deploy.sh; do
    [ -f "$file" ] || fail "Missing $file"
done
pass "All required files present"

# Check backend structure
echo "Checking backend structure..."
for dir in backend/mcp_server backend/agent_integration backend/tests; do
    [ -d "$dir" ] || fail "Missing $dir"
done
pass "Backend structure valid"

# Check CLI structure
echo "Checking CLI structure..."
[ -f "cli/package.json" ] || fail "Missing cli/package.json"
[ -f "cli/bin/ultimate-mcp.js" ] || fail "Missing CLI binary"
pass "CLI structure valid"

# Check Docker files
echo "Checking Docker files..."
[ -f "backend/Dockerfile" ] || fail "Missing backend Dockerfile"
[ -f "frontend/Dockerfile" ] || fail "Missing frontend Dockerfile"
[ -f "deployment/docker-compose.yml" ] || fail "Missing docker-compose.yml"
pass "Docker files present"

# Check .gitignore
echo "Checking .gitignore..."
grep -q ".env" .gitignore || fail ".env not in .gitignore"
grep -q "__pycache__" .gitignore || fail "__pycache__ not in .gitignore"
pass ".gitignore configured"

echo
echo "=== All validations passed! ==="
