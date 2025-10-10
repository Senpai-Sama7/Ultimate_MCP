"""Tests for JWT token handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from mcp_server.auth.jwt_handler import JWTHandler
from mcp_server.auth.rbac import Role


@pytest.fixture
def jwt_handler():
    """Create JWT handler instance."""
    return JWTHandler(secret_key="test-secret-key-12345")


def test_create_token_basic(jwt_handler):
    """Test creating basic JWT token."""
    token = jwt_handler.create_token(user_id="user-123", roles=[Role.DEVELOPER])

    # Verify token can be decoded
    payload = jwt.decode(
        token, "test-secret-key-12345", algorithms=["HS256"], issuer="ultimate-mcp"
    )

    assert payload["sub"] == "user-123"
    assert payload["roles"] == ["developer"]
    assert payload["iss"] == "ultimate-mcp"
    assert "iat" in payload
    assert "exp" in payload


def test_create_token_multiple_roles(jwt_handler):
    """Test creating token with multiple roles."""
    token = jwt_handler.create_token(
        user_id="user-123", roles=[Role.DEVELOPER, Role.ADMIN]
    )

    payload = jwt.decode(
        token, "test-secret-key-12345", algorithms=["HS256"], issuer="ultimate-mcp"
    )

    assert payload["roles"] == ["developer", "admin"]


def test_create_token_custom_expiration(jwt_handler):
    """Test creating token with custom expiration."""
    token = jwt_handler.create_token(
        user_id="user-123", roles=[Role.VIEWER], expires_in_hours=48
    )

    payload = jwt.decode(
        token, "test-secret-key-12345", algorithms=["HS256"], issuer="ultimate-mcp"
    )

    # Check expiration is approximately 48 hours from now
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_exp = datetime.now(timezone.utc) + timedelta(hours=48)
    time_diff = abs((exp_time - expected_exp).total_seconds())

    assert time_diff < 5  # Within 5 seconds tolerance


def test_create_token_additional_claims(jwt_handler):
    """Test creating token with additional claims."""
    token = jwt_handler.create_token(
        user_id="user-123",
        roles=[Role.DEVELOPER],
        additional_claims={"email": "user@example.com", "org": "test-org"},
    )

    payload = jwt.decode(
        token, "test-secret-key-12345", algorithms=["HS256"], issuer="ultimate-mcp"
    )

    assert payload["email"] == "user@example.com"
    assert payload["org"] == "test-org"


def test_verify_token_success(jwt_handler):
    """Test verifying valid token."""
    token = jwt_handler.create_token(user_id="user-123", roles=[Role.DEVELOPER])

    payload = jwt_handler.verify_token(token)

    assert payload["sub"] == "user-123"
    assert payload["roles"] == ["developer"]


def test_verify_token_invalid_signature(jwt_handler):
    """Test verifying token with invalid signature."""
    # Create token with different secret
    other_handler = JWTHandler(secret_key="different-secret")
    token = other_handler.create_token(user_id="user-123", roles=[Role.DEVELOPER])

    # Verify with original handler should fail
    with pytest.raises(jwt.InvalidTokenError):
        jwt_handler.verify_token(token)


def test_verify_token_expired(jwt_handler):
    """Test verifying expired token."""
    # Create token that expires immediately
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": "user-123",
            "roles": ["developer"],
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),  # Expired 1 hour ago
            "iss": "ultimate-mcp",
        },
        "test-secret-key-12345",
        algorithm="HS256",
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        jwt_handler.verify_token(expired_token)


def test_verify_token_invalid_issuer(jwt_handler):
    """Test verifying token with invalid issuer."""
    # Create token with wrong issuer
    invalid_token = jwt.encode(
        {
            "sub": "user-123",
            "roles": ["developer"],
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": "wrong-issuer",
        },
        "test-secret-key-12345",
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidIssuerError):
        jwt_handler.verify_token(invalid_token)


def test_extract_roles_success(jwt_handler):
    """Test extracting roles from token."""
    token = jwt_handler.create_token(user_id="user-123", roles=[Role.DEVELOPER, Role.ADMIN])

    roles = jwt_handler.extract_roles(token)

    assert len(roles) == 2
    assert Role.DEVELOPER in roles
    assert Role.ADMIN in roles


def test_extract_roles_no_roles(jwt_handler):
    """Test extracting roles from token with no roles."""
    # Create token without roles claim
    token = jwt.encode(
        {
            "sub": "user-123",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": "ultimate-mcp",
        },
        "test-secret-key-12345",
        algorithm="HS256",
    )

    roles = jwt_handler.extract_roles(token)

    # Should default to viewer
    assert roles == [Role.VIEWER]


def test_extract_roles_invalid_token(jwt_handler):
    """Test extracting roles from invalid token."""
    roles = jwt_handler.extract_roles("invalid-token")

    # Should default to viewer on error
    assert roles == [Role.VIEWER]


def test_extract_roles_invalid_role_value(jwt_handler):
    """Test extracting roles with invalid role value."""
    # Create token with invalid role
    token = jwt.encode(
        {
            "sub": "user-123",
            "roles": ["developer", "invalid_role"],
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": "ultimate-mcp",
        },
        "test-secret-key-12345",
        algorithm="HS256",
    )

    # Should skip invalid role and default to viewer
    roles = jwt_handler.extract_roles(token)
    assert Role.VIEWER in roles


def test_jwt_handler_different_algorithm():
    """Test JWT handler with different algorithm."""
    handler = JWTHandler(secret_key="test-secret", algorithm="HS512")

    token = handler.create_token(user_id="user-123", roles=[Role.DEVELOPER])

    # Verify with correct algorithm
    payload = jwt.decode(token, "test-secret", algorithms=["HS512"], issuer="ultimate-mcp")
    assert payload["sub"] == "user-123"

    # Verify with wrong algorithm should fail
    with pytest.raises(jwt.InvalidAlgorithmError):
        jwt.decode(token, "test-secret", algorithms=["HS256"], issuer="ultimate-mcp")
