"""Integration tests for JWT authentication."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_and_access_protected_endpoint(client: TestClient):
    """Test that a user can log in and access a protected endpoint with the obtained token."""
    # 1. Log in to get a token
    response = client.post(
        "/auth/token",
        data={"username": "developer", "password": "dev_password"},
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]

    # 2. Use the token to access a protected endpoint
    headers = {"Authorization": f"Bearer {access_token}"}
    test_payload = {
        "code": "def test_addition():\n    assert 1 + 1 == 2",
        "language": "python",
    }
    response = client.post("/run_tests", headers=headers, json=test_payload)
    assert response.status_code == 200
    result = response.json()
    assert result["return_code"] == 0


def test_access_protected_endpoint_with_invalid_token(client: TestClient):
    """Test that an invalid token is rejected."""
    headers = {"Authorization": "Bearer invalidtoken"}
    test_payload = {
        "code": "def test_addition():\n    assert 1 + 1 == 2",
        "language": "python",
    }
    response = client.post("/run_tests", headers=headers, json=test_payload)
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_access_protected_endpoint_without_token(client: TestClient):
    """Test that a request without a token is rejected."""
    test_payload = {
        "code": "def test_addition():\n    assert 1 + 1 == 2",
        "language": "python",
    }
    response = client.post("/run_tests", json=test_payload)
    assert response.status_code == 401
    assert "Invalid or missing bearer token" in response.json()["detail"]
