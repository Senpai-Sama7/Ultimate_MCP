# Publishing Guide - Ultimate MCP

## Status: Ready to Publish ✅

Both packages are built and ready for publication.

---

## 1. Python Package (PyPI)

### Built Files
- `dist/ultimate_mcp-0.1.0-py3-none-any.whl` (70KB)
- `dist/ultimate_mcp-0.1.0.tar.gz` (60KB)

### Publish to PyPI

```bash
# Test on TestPyPI first (recommended)
.build_venv/bin/twine upload --repository testpypi dist/*

# Publish to PyPI
.build_venv/bin/twine upload dist/*
```

You'll be prompted for:
- Username: `__token__`
- Password: Your PyPI API token (starts with `pypi-`)

### Get PyPI Token
1. Go to https://pypi.org/manage/account/token/
2. Create new API token
3. Copy token (starts with `pypi-`)

### Verify Installation
```bash
pip install ultimate-mcp
python -c "import mcp_server; print('Success!')"
```

---

## 2. npm Package (CLI)

### Package Info
- Name: `@ultimate-mcp/cli`
- Version: 0.1.3
- Size: 7.8 KB (packed)

### Publish to npm

```bash
cd cli

# Login to npm (one-time)
npm login

# Publish (scoped packages need --access public)
npm publish --access public
```

### Get npm Token
1. Go to https://www.npmjs.com/settings/~/tokens
2. Create new access token (Automation or Publish)
3. Use for `npm login`

### Verify Installation
```bash
npx @ultimate-mcp/cli --version
# Should show: 0.1.3
```

---

## 3. GitHub Release

### Create Release Tag

```bash
# Tag the release
git tag -a v0.1.0 -m "Release v0.1.0 - Production-ready MCP platform"

# Push tag
git push origin v0.1.0
```

### Create GitHub Release
1. Go to https://github.com/Senpai-Sama7/Ultimate_MCP/releases/new
2. Choose tag: `v0.1.0`
3. Release title: `v0.1.0 - Production Release`
4. Description:
```markdown
## Ultimate MCP v0.1.0

Production-ready Model Context Protocol (MCP) platform.

### Features
- 🔐 Security-first with JWT auth, RBAC, rate limiting
- 🧪 5 MCP tools: lint, execute, test, generate, graph operations
- 🧠 Neo4j graph storage
- 📊 Comprehensive monitoring and audit logging
- 🛠️ FastMCP integration

### Installation

**CLI (Fastest)**
```bash
npx @ultimate-mcp/cli init my-project
cd my-project
npx @ultimate-mcp/cli start
```

**Python Package**
```bash
pip install ultimate-mcp
```

### What's Included
- FastAPI backend with MCP server
- React frontend
- Neo4j database
- Docker Compose deployment
- CLI tool for easy setup

### Documentation
- [README](https://github.com/Senpai-Sama7/Ultimate_MCP#readme)
- [API Docs](http://localhost:8000/docs) (after deployment)

### Assets
- Python wheel: `ultimate_mcp-0.1.0-py3-none-any.whl`
- Source tarball: `ultimate_mcp-0.1.0.tar.gz`
```

5. Attach files from `dist/` folder
6. Click "Publish release"

---

## Pre-Publishing Checklist

- [x] Python package built successfully
- [x] npm package validated
- [x] All tests passing
- [x] Documentation updated
- [x] Version numbers consistent
- [x] No hardcoded secrets
- [x] .gitignore configured
- [ ] PyPI account created
- [ ] npm account created
- [ ] GitHub release prepared

---

## Post-Publishing

### Update README Badges

Add to README.md:
```markdown
[![PyPI version](https://badge.fury.io/py/ultimate-mcp.svg)](https://badge.fury.io/py/ultimate-mcp)
[![npm version](https://badge.fury.io/js/%40ultimate-mcp%2Fcli.svg)](https://badge.fury.io/js/%40ultimate-mcp%2Fcli)
```

### Announce

- Twitter/X
- Reddit (r/Python, r/node)
- Dev.to
- Hacker News

### Monitor

- PyPI downloads: https://pypistats.org/packages/ultimate-mcp
- npm downloads: https://www.npmjs.com/package/@ultimate-mcp/cli
- GitHub stars/issues

---

## Troubleshooting

### PyPI Upload Fails
```bash
# Check package
.build_venv/bin/twine check dist/*

# Use TestPyPI first
.build_venv/bin/twine upload --repository testpypi dist/*
```

### npm Publish Fails
```bash
# Check package
npm pack --dry-run

# Verify login
npm whoami

# Check package name availability
npm view @ultimate-mcp/cli
```

### Version Conflicts
```bash
# Update version in pyproject.toml
# Update version in cli/package.json
# Rebuild and republish
```

---

## Next Version

To publish v0.1.1:

1. Update `pyproject.toml` version
2. Update `cli/package.json` version
3. Update README if needed
4. Rebuild: `python -m build`
5. Republish: `twine upload dist/*` and `npm publish`
6. Tag: `git tag v0.1.1`
