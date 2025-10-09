# Release Process

The Ultimate MCP release pipeline publishes Docker images and the npm CLI whenever a semantic tag is pushed. Follow the steps below to cut a new release.

## 1. Prepare
- Ensure `main` is green and contains the desired commits.
- Update `cli/package.json` and any other versioned artifacts with the new semantic version (e.g., `0.2.0`).
- Update changelogs/documentation as required.

## 2. Authenticate
- **GitHub Container Registry:** the workflow uses `${{ secrets.GITHUB_TOKEN }}` automatically. No additional setup required.
- **npm:** store a publishable token in the repository secrets as `NPM_TOKEN` with `publish` scope.

## 3. Tag and Push
```bash
git checkout main
git pull origin main
git tag v0.2.0
git push origin v0.2.0
```

## 4. Pipeline
The `.github/workflows/release.yml` workflow will:
1. Build and push multi-arch Docker images to `ghcr.io/<org>/ultimate-mcp-backend` and `ghcr.io/<org>/ultimate-mcp-frontend` (`:v0.2.0` and `:latest`).
2. Publish the CLI from `cli/` to npm as `@ultimate-mcp/cli` with the tag version.
3. Draft GitHub release notes linked to the tag.

Monitor the workflow run until it completes. If it fails:
- Restart after resolving the issue (re-tag if necessary).
- Remove any partially published artifacts (npm supports `npm unpublish <version>` within 24 hours).

After the workflow succeeds, validate the published artifacts:

```bash
npx @ultimate-mcp/cli@latest init smoke-release
cd smoke-release
npx @ultimate-mcp/cli start --detached
curl http://localhost:8000/health
npx @ultimate-mcp/cli stop
```

Once confirmed, delete the temporary directory.

## 5. Post-Release
- Publish documentation updates if needed (e.g., blog, changelog).
- Notify users that `npx @ultimate-mcp/cli init` now pulls the new tag.
