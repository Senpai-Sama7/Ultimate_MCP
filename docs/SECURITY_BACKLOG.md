# Security Backlog

Track remediation items that remain after the initial hardening pass.

1. **Sandbox isolation** – Replace the enhanced execution inline interpreter with a containerized or nsjail-based runner and add regression tests that attempt privilege escalation.
2. **Rate limiting tests** – Add automated coverage for SlowAPI + `RateLimitConfig` interactions, including burst traffic and logging assertions.
3. **Credential enforcement** – Expand configuration validation to reject missing `SECRET_KEY`, ensure secrets rotate per environment, and document rotation procedures.
4. **Dependency auditing** – Schedule recurring checks for PyJWT / cryptography CVEs and automate dependency scanning in CI.

Update this list as issues are opened/closed in GitHub.
