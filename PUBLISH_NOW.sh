#!/usr/bin/env bash
# Quick Publishing Script for Ultimate MCP
# Run this after you have PyPI and npm tokens configured

set -euo pipefail

echo "=== Ultimate MCP Publishing Script ==="
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Publishing Python Package to PyPI${NC}"
echo "Command: .build_venv/bin/twine upload dist/*"
echo
read -p "Press Enter to publish to PyPI (Ctrl+C to cancel)..."
.build_venv/bin/twine upload dist/*
echo -e "${GREEN}✓ Python package published!${NC}"
echo

echo -e "${YELLOW}Step 2: Publishing npm Package${NC}"
echo "Command: cd cli && npm publish --access public"
echo
read -p "Press Enter to publish to npm (Ctrl+C to cancel)..."
cd cli
npm publish --access public
cd ..
echo -e "${GREEN}✓ npm package published!${NC}"
echo

echo -e "${YELLOW}Step 3: Creating GitHub Release${NC}"
echo "Creating git tag v0.1.0..."
git tag -a v0.1.0 -m "Release v0.1.0 - Production-ready MCP platform" 2>/dev/null || echo "Tag already exists"
echo
read -p "Press Enter to push tag to GitHub (Ctrl+C to cancel)..."
git push origin v0.1.0
echo -e "${GREEN}✓ Tag pushed!${NC}"
echo

echo "=== Publishing Complete! ==="
echo
echo "Next steps:"
echo "1. Go to https://github.com/Senpai-Sama7/Ultimate_MCP/releases/new"
echo "2. Select tag: v0.1.0"
echo "3. Upload files from dist/ folder"
echo "4. Publish release"
echo
echo "Verify installations:"
echo "  pip install ultimate-mcp"
echo "  npx @ultimate-mcp/cli --version"
