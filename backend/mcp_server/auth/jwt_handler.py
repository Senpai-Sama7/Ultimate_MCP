"""JWT token handling with RBAC support."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from .rbac import Role


class JWTHandler:
    """Handle JWT token creation and validation."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """Initialize JWT handler.

        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT algorithm
        """
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_token(
        self,
        user_id: str,
        roles: list[Role],
        expires_in_hours: int = 24,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create JWT token with roles.

        Args:
            user_id: User identifier
            roles: User's roles
            expires_in_hours: Token expiration time
            additional_claims: Additional claims to include

        Returns:
            Signed JWT token
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=expires_in_hours)

        payload = {
            "sub": user_id,
            "roles": [role.value for role in roles],
            "iat": now,
            "exp": expires_at,
            "iss": "ultimate-mcp",
        }

        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode JWT token.

        Args:
            token: JWT token to verify

        Returns:
            Decoded token payload

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm], issuer="ultimate-mcp")

    def extract_roles(self, token: str) -> list[Role]:
        """Extract roles from JWT token.

        Args:
            token: JWT token

        Returns:
            List of user roles
        """
        try:
            payload = self.verify_token(token)
            role_strings = payload.get("roles", ["viewer"])
            return [Role(role) for role in role_strings]
        except (jwt.InvalidTokenError, ValueError):
            return [Role.VIEWER]  # Default to viewer on error
