# Security Backlog

Track remediation items that remain after the initial hardening pass.

## Active Security Findings

### Configuration Security
1. **Bind to all interfaces (0.0.0.0)** - DOCUMENTED: The default host binding is intentional for container deployments. Production deployments should:
   - Use reverse proxy (nginx, traefik) in front of the service
   - Configure firewall rules to restrict access
   - Override `HOST` environment variable if binding to localhost only
   - Reference: `mcp_server/config.py:55`

### Code Generation Security
2. **Jinja2 autoescape disabled** - ACCEPTABLE: Template autoescape is intentionally disabled for code generation as we're generating source code, not HTML. This is:
   - Marked with `noqa: S701` 
   - Only used for trusted template rendering
   - Input validation occurs before template rendering
   - Reference: `mcp_server/tools/gen_tool.py:14`

### Process Execution Security
3. **Subprocess usage** - MITIGATED: Subprocess calls are necessary for code execution/linting and have security measures:
   - All subprocess calls avoid `shell=True`
   - Commands are constructed from hardcoded lists, not user input
   - Marked with `noqa: S603`
   - Additional sandboxing via resource limits in enhanced_exec_tool
   - References: `exec_tool.py`, `lint_tool.py`, `test_tool.py`

## Planned Improvements

1. **Sandbox isolation** – Replace the enhanced execution inline interpreter with a containerized or nsjail-based runner and add regression tests that attempt privilege escalation.
2. **Rate limiting tests** – Add automated coverage for SlowAPI + `RateLimitConfig` interactions, including burst traffic and logging assertions.
3. **Credential enforcement** – Expand configuration validation to reject missing `SECRET_KEY`, ensure secrets rotate per environment, and document rotation procedures.
4. **Dependency auditing** – Schedule recurring checks for PyJWT / cryptography CVEs and automate dependency scanning in CI.
5. **Code coverage expansion** – Increase test coverage for auth decorators (currently 18%, used in endpoint context).

## Completed Security Enhancements

- ✅ JWT token authentication with role-based access control (RBAC)
- ✅ Audit logging for security events (authentication, authorization, code execution)
- ✅ Permission system with frozen dataclasses for security
- ✅ Security scanning with bandit (all critical issues resolved)
- ✅ Code linting and formatting enforced (ruff, mypy)
- ✅ 87% test coverage for audit and auth modules

Update this list as issues are opened/closed in GitHub.
