"""JWT token handling with RBAC support."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

import jwt

from .rbac import Role

if TYPE_CHECKING:
    from .token_blacklist import TokenBlacklist


class JWTHandler:
    """Handle JWT token creation and validation with revocation support."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        token_blacklist: "TokenBlacklist | None" = None,
    ):
        """Initialize JWT handler.

        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT algorithm
            token_blacklist: Optional token blacklist for revocation checks
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_blacklist = token_blacklist

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
        """Verify and decode JWT token without revocation check.

        Args:
            token: JWT token to verify

        Returns:
            Decoded token payload

        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        return jwt.decode(
            token, self.secret_key, algorithms=[self.algorithm], issuer="ultimate-mcp"
        )

    async def verify_token_with_revocation(self, token: str) -> dict[str, Any]:
        """Verify JWT token and check if it's been revoked.

        Args:
            token: JWT token to verify

        Returns:
            Decoded token payload

        Raises:
            jwt.InvalidTokenError: If token is invalid or revoked
        """
        # First verify token signature and expiration
        payload = self.verify_token(token)

        # Check if token is revoked
        if self.token_blacklist:
            is_revoked = await self.token_blacklist.is_revoked(token)
            if is_revoked:
                raise jwt.InvalidTokenError("Token has been revoked")

            # Check if user has global revocation after token was issued
            user_id = payload.get("sub")
            iat = payload.get("iat")
            if user_id and iat:
                issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
                user_revoked = await self.token_blacklist.is_user_revoked(user_id, issued_at)
                if user_revoked:
                    raise jwt.InvalidTokenError("All user tokens have been revoked")

        return payload

    def extract_roles(self, token: str) -> list[Role]:
        """Extract roles from JWT token.

        Args:
            token: JWT token

        Returns:
            List of user roles

        Raises:
            jwt.InvalidTokenError: If token is invalid or expired
            ValueError: If token contains no valid roles
        """
        # Will raise jwt.InvalidTokenError if token is invalid
        payload = self.verify_token(token)
        role_strings = payload.get("roles", [])

        roles = []
        for role_str in role_strings:
            try:
                roles.append(Role(role_str))
            except ValueError:
                # Log invalid role but continue processing other roles
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Invalid role in token: {role_str}")

        # If no valid roles found, raise an error instead of defaulting
        if not roles:
            raise ValueError("Token contains no valid roles")

        return roles
