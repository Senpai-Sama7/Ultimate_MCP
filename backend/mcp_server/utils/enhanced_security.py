"""Enhanced security utilities with comprehensive protection mechanisms."""

from __future__ import annotations

import ast
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

import jwt
from cryptography.fernet import Fernet


class SecurityLevel(Enum):
    """Security levels for different operations."""
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    AUTHORIZED = "authorized"
    ADMIN = "admin"


class SecurityViolationError(RuntimeError):
    """Raised when a payload violates security rules."""


class AuthenticationError(RuntimeError):
    """Raised when authentication fails."""


class AuthorizationError(RuntimeError):
    """Raised when authorization fails."""


@dataclass
class SecurityContext:
    """Security context for requests."""
    user_id: str | None = None
    roles: list[str] | None = None
    permissions: list[str] | None = None
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_allowance: int = 10


class EnhancedSecurityManager:
    """Comprehensive security management."""
    
    def __init__(self, secret_key: str, encryption_key: str | None = None):
        self.secret_key = secret_key
        self.encryption_key = encryption_key or Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        self.rate_limits: dict[str, list[float]] = {}
        
    def generate_secure_token(self, payload: dict[str, Any], expires_in: int = 3600) -> str:
        """Generate secure JWT token."""
        now = time.time()
        token_payload = {
            **payload,
            "iat": now,
            "exp": now + expires_in,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(token_payload, self.secret_key, algorithm="HS256")
    
    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def check_rate_limit(self, identifier: str, config: RateLimitConfig) -> bool:
        """Check if request is within rate limits."""
        now = time.time()
        
        # Clean old entries
        if identifier in self.rate_limits:
            self.rate_limits[identifier] = [
                timestamp for timestamp in self.rate_limits[identifier]
                if now - timestamp < 86400  # Keep last 24 hours
            ]
        else:
            self.rate_limits[identifier] = []
        
        timestamps = self.rate_limits[identifier]
        
        # Check different time windows
        minute_ago = now - 60
        hour_ago = now - 3600
        day_ago = now - 86400
        
        recent_minute = sum(1 for t in timestamps if t > minute_ago)
        recent_hour = sum(1 for t in timestamps if t > hour_ago)
        recent_day = sum(1 for t in timestamps if t > day_ago)
        
        if (recent_minute >= config.requests_per_minute or
            recent_hour >= config.requests_per_hour or
            recent_day >= config.requests_per_day):
            return False
        
        # Record this request
        timestamps.append(now)
        return True
    
    def create_security_context(
        self, 
        token: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None
    ) -> SecurityContext:
        """Create security context from request."""
        if not token:
            return SecurityContext(
                security_level=SecurityLevel.PUBLIC,
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        try:
            payload = self.verify_token(token)
            return SecurityContext(
                user_id=payload.get("user_id"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                security_level=SecurityLevel(payload.get("security_level", "authenticated")),
                session_id=payload.get("session_id"),
                ip_address=ip_address,
                user_agent=user_agent
            )
        except AuthenticationError:
            return SecurityContext(
                security_level=SecurityLevel.PUBLIC,
                ip_address=ip_address,
                user_agent=user_agent
            )


# Enhanced code security
DISALLOWED_MODULES: frozenset[str] = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "asyncio",
    "multiprocessing", "signal", "inspect", "importlib", "ctypes", "resource",
    "fcntl", "pty", "pwd", "grp", "tempfile", "pickle", "marshal", "shelve",
    "dbm", "sqlite3", "http", "urllib", "requests", "ftplib", "smtplib",
    "poplib", "imaplib", "telnetlib", "webbrowser", "platform", "getpass",
})

DISALLOWED_FUNCTIONS: frozenset[str] = frozenset({
    "eval", "exec", "open", "compile", "__import__", "globals", "locals",
    "input", "raw_input", "reload", "vars", "dir", "help", "memoryview",
    "bytearray", "bytes", "exit", "quit", "copyright", "credits", "license",
})

DISALLOWED_ATTRIBUTES: frozenset[str] = frozenset({
    "__class__", "__bases__", "__subclasses__", "__mro__", "__dict__",
    "__globals__", "__code__", "__closure__", "__defaults__", "__kwdefaults__",
    "func_globals", "func_code", "gi_frame", "cr_frame", "f_globals", "f_locals",
})


def _iter_names(node: ast.AST) -> Iterable[str]:
    """Extract all names from AST node."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            yield child.id
        elif isinstance(child, ast.Attribute):
            yield child.attr


def _check_dangerous_patterns(tree: ast.AST) -> None:
    """Check for dangerous code patterns."""
    for node in ast.walk(tree):
        # Check for dynamic attribute access
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("getattr", "setattr", "delattr", "hasattr"):
                raise SecurityViolationError("Dynamic attribute access is not allowed")
        
        # Check for dangerous built-ins
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (isinstance(node.func.value, ast.Name) and 
                node.func.value.id == "__builtins__"):
                raise SecurityViolationError("Access to __builtins__ is not allowed")
        
        # Check for file operations
        if isinstance(node, ast.With):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    if (isinstance(item.context_expr.func, ast.Name) and
                        item.context_expr.func.id == "open"):
                        raise SecurityViolationError("File operations are not allowed")


def ensure_safe_python(code: str, max_complexity: int = 100) -> None:
    """Enhanced Python code validation with complexity analysis."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SecurityViolationError("Invalid Python syntax") from exc
    
    # Check complexity
    complexity = sum(1 for _ in ast.walk(tree))
    if complexity > max_complexity:
        raise SecurityViolationError(f"Code complexity ({complexity}) exceeds limit ({max_complexity})")
    
    # Check imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DISALLOWED_MODULES:
                    raise SecurityViolationError(f"Module '{root}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in DISALLOWED_MODULES:
                    raise SecurityViolationError(f"Module '{root}' is not allowed")
    
    # Check function names
    for name in _iter_names(tree):
        if name in DISALLOWED_FUNCTIONS:
            raise SecurityViolationError(f"Function '{name}' is not allowed")
        if name in DISALLOWED_ATTRIBUTES:
            raise SecurityViolationError(f"Attribute '{name}' is not allowed")
    
    # Check dangerous patterns
    _check_dangerous_patterns(tree)


def generate_api_key() -> str:
    """Generate secure API key."""
    return secrets.token_urlsafe(32)


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash password with salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return password_hash.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify password against hash."""
    computed_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(computed_hash, password_hash)


__all__ = [
    "EnhancedSecurityManager", "SecurityContext", "SecurityLevel", "RateLimitConfig",
    "SecurityViolationError", "AuthenticationError", "AuthorizationError",
    "ensure_safe_python", "generate_api_key", "hash_password", "verify_password"
]
