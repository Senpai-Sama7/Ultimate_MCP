"""Token revocation and blacklist management."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class TokenBlacklist:
    """Manage revoked JWT tokens using Neo4j as the backend.

    Tokens are stored by their hash (SHA256) to protect the actual token value.
    Expired blacklist entries are automatically cleaned up during checks.
    """

    def __init__(self, neo4j_client: Any) -> None:
        """Initialize token blacklist.

        Args:
            neo4j_client: Neo4j client for persistence
        """
        self.neo4j = neo4j_client
        self._ensure_schema_called = False

    async def _ensure_schema(self) -> None:
        """Ensure database schema for blacklist exists."""
        if self._ensure_schema_called:
            return

        try:
            # Create index on token_hash for fast lookup
            await self.neo4j.execute_write(
                """
                CREATE INDEX blacklist_token_hash IF NOT EXISTS
                FOR (t:BlacklistedToken) ON (t.token_hash)
                """
            )

            # Create index on expiration for cleanup queries
            await self.neo4j.execute_write(
                """
                CREATE INDEX blacklist_expires_at IF NOT EXISTS
                FOR (t:BlacklistedToken) ON (t.expires_at)
                """
            )

            self._ensure_schema_called = True
            logger.info("Token blacklist schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize blacklist schema: {e}")
            raise

    @staticmethod
    def _hash_token(token: str) -> str:
        """Create SHA256 hash of token for storage.

        Args:
            token: JWT token string

        Returns:
            Hex digest of token hash
        """
        return hashlib.sha256(token.encode()).hexdigest()

    async def revoke(
        self,
        token: str,
        reason: str = "manual_revocation",
        revoked_by: str | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Revoke a token by adding it to the blacklist.

        Args:
            token: JWT token to revoke
            reason: Reason for revocation (e.g., 'logout', 'compromised', 'expired')
            revoked_by: User ID who initiated revocation
            expires_at: When the token expires (for automatic cleanup)
        """
        await self._ensure_schema()

        token_hash = self._hash_token(token)
        now = datetime.now(timezone.utc)

        # If no expiration provided, set to 7 days (reasonable default)
        if expires_at is None:
            from datetime import timedelta
            expires_at = now + timedelta(days=7)

        try:
            await self.neo4j.execute_write(
                """
                MERGE (t:BlacklistedToken {token_hash: $token_hash})
                SET t.revoked_at = datetime($revoked_at),
                    t.expires_at = datetime($expires_at),
                    t.reason = $reason,
                    t.revoked_by = $revoked_by
                """,
                {
                    "token_hash": token_hash,
                    "revoked_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "reason": reason,
                    "revoked_by": revoked_by,
                },
            )
            logger.info(
                f"Token revoked",
                token_hash=token_hash[:16],
                reason=reason,
                revoked_by=revoked_by,
            )
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            raise

    async def is_revoked(self, token: str) -> bool:
        """Check if a token is blacklisted.

        Args:
            token: JWT token to check

        Returns:
            True if token is revoked, False otherwise
        """
        await self._ensure_schema()

        token_hash = self._hash_token(token)
        now = datetime.now(timezone.utc)

        try:
            result = await self.neo4j.execute_read(
                """
                MATCH (t:BlacklistedToken {token_hash: $token_hash})
                WHERE datetime(t.expires_at) > datetime($now)
                RETURN t.token_hash AS hash LIMIT 1
                """,
                {"token_hash": token_hash, "now": now.isoformat()},
            )

            is_blacklisted = len(result) > 0

            if is_blacklisted:
                logger.warning(f"Attempted use of revoked token", token_hash=token_hash[:16])

            return is_blacklisted

        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            # Fail secure - treat as revoked on error
            return True

    async def cleanup_expired(self) -> int:
        """Remove expired tokens from blacklist.

        Returns:
            Number of tokens removed
        """
        await self._ensure_schema()

        now = datetime.now(timezone.utc)

        try:
            result = await self.neo4j.execute_write(
                """
                MATCH (t:BlacklistedToken)
                WHERE datetime(t.expires_at) <= datetime($now)
                DELETE t
                RETURN count(t) AS deleted_count
                """,
                {"now": now.isoformat()},
            )

            deleted_count = result[0]["deleted_count"] if result else 0
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired blacklisted tokens")

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0

    async def revoke_all_for_user(self, user_id: str, reason: str = "user_initiated") -> int:
        """Revoke all tokens for a specific user.

        This is useful for 'logout from all devices' functionality.

        Args:
            user_id: User identifier
            reason: Reason for mass revocation

        Returns:
            Number of tokens revoked (estimated, as we don't track individual tokens)
        """
        await self._ensure_schema()

        # Note: This requires tracking user_id with tokens
        # For now, we'll store a user-level revocation marker
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires_at = now + timedelta(days=7)

        try:
            await self.neo4j.execute_write(
                """
                MERGE (u:UserRevocation {user_id: $user_id})
                SET u.revoked_at = datetime($revoked_at),
                    u.expires_at = datetime($expires_at),
                    u.reason = $reason
                """,
                {
                    "user_id": user_id,
                    "revoked_at": now.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "reason": reason,
                },
            )

            logger.info(f"All tokens revoked for user", user_id=user_id, reason=reason)
            return 1  # Return 1 to indicate successful revocation

        except Exception as e:
            logger.error(f"Failed to revoke tokens for user: {e}")
            raise

    async def is_user_revoked(self, user_id: str, issued_at: datetime) -> bool:
        """Check if user has global revocation after token was issued.

        Args:
            user_id: User identifier
            issued_at: When the token was issued

        Returns:
            True if user has active revocation after token issue time
        """
        await self._ensure_schema()

        try:
            result = await self.neo4j.execute_read(
                """
                MATCH (u:UserRevocation {user_id: $user_id})
                WHERE datetime(u.revoked_at) > datetime($issued_at)
                AND datetime(u.expires_at) > datetime($now)
                RETURN u.user_id AS user_id LIMIT 1
                """,
                {
                    "user_id": user_id,
                    "issued_at": issued_at.isoformat(),
                    "now": datetime.now(timezone.utc).isoformat(),
                },
            )

            return len(result) > 0

        except Exception as e:
            logger.error(f"Failed to check user revocation: {e}")
            # Fail secure
            return True

    async def get_stats(self) -> dict[str, int]:
        """Get blacklist statistics.

        Returns:
            Dictionary with blacklist metrics
        """
        await self._ensure_schema()

        now = datetime.now(timezone.utc)

        try:
            result = await self.neo4j.execute_read(
                """
                MATCH (t:BlacklistedToken)
                WITH count(t) AS total,
                     sum(CASE WHEN datetime(t.expires_at) > datetime($now) THEN 1 ELSE 0 END) AS active,
                     sum(CASE WHEN datetime(t.expires_at) <= datetime($now) THEN 1 ELSE 0 END) AS expired
                RETURN total, active, expired
                """,
                {"now": now.isoformat()},
            )

            if result:
                return {
                    "total": result[0]["total"],
                    "active": result[0]["active"],
                    "expired": result[0]["expired"],
                }
            return {"total": 0, "active": 0, "expired": 0}

        except Exception as e:
            logger.error(f"Failed to get blacklist stats: {e}")
            return {"total": 0, "active": 0, "expired": 0}


__all__ = ["TokenBlacklist"]
