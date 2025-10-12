"""Input validation helpers for API and tool payloads."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ValidationError

_ALLOWED_LANGUAGES = {"python", "javascript", "bash"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")
_FORBIDDEN_CYPHER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bCALL\s+db\.|\bCALL\s+dbms\.", re.IGNORECASE),
    re.compile(r"\bDELETE\b", re.IGNORECASE),
    re.compile(r"\bDETACH\b", re.IGNORECASE),
    re.compile(r"\bREMOVE\b", re.IGNORECASE),
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(r";"),
)

# Security patterns for code validation
_DANGEROUS_PYTHON_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b__import__\s*\(", re.IGNORECASE),
    re.compile(r"\beval\s*\(", re.IGNORECASE),
    re.compile(r"\bexec\s*\(", re.IGNORECASE),
    re.compile(r"\bcompile\s*\(", re.IGNORECASE),
    re.compile(r"\bopen\s*\(.*['\"]w", re.IGNORECASE),
    re.compile(r"\bos\.system\s*\(", re.IGNORECASE),
    re.compile(r"\bsubprocess\.", re.IGNORECASE),
)

# File path validation
_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_\-/\.]+$")
_PARENT_DIR_PATTERN = re.compile(r"\.\.")


class PayloadValidationError(ValueError):
    """Raised when incoming payload validation fails."""


class CodeValidationError(ValueError):
    """Raised when code validation fails for security reasons."""


def ensure_supported_language(language: str) -> None:
    """Validate that the language is supported.
    
    Args:
        language: Programming language name
        
    Raises:
        PayloadValidationError: If language is not supported
    """
    if language.lower() not in _ALLOWED_LANGUAGES:
        raise PayloadValidationError(
            f"Language '{language}' is not supported. "
            f"Supported languages: {', '.join(sorted(_ALLOWED_LANGUAGES))}"
        )


def ensure_valid_identifier(value: str, *, field: str = "identifier") -> None:
    """Validate that a string is a valid identifier.
    
    Args:
        value: Identifier string to validate
        field: Field name for error messages
        
    Raises:
        PayloadValidationError: If identifier is invalid
    """
    if not _IDENTIFIER_RE.fullmatch(value):
        raise PayloadValidationError(
            f"{field} must match {_IDENTIFIER_RE.pattern!r} and be <= 64 characters."
        )


def ensure_safe_cypher(query: str) -> None:
    """Validate that a Cypher query is safe to execute.
    
    Args:
        query: Cypher query string
        
    Raises:
        PayloadValidationError: If query contains forbidden operations
    """
    normalized = query.strip()
    if not normalized:
        raise PayloadValidationError("Cypher query must not be empty.")

    for pattern in _FORBIDDEN_CYPHER_PATTERNS:
        if pattern.search(normalized):
            raise PayloadValidationError(
                f"Cypher query contains forbidden operations. "
                f"Pattern matched: {pattern.pattern}"
            )


def ensure_safe_python_code(code: str, *, strict: bool = False) -> None:
    """Validate that Python code doesn't contain dangerous patterns.
    
    Args:
        code: Python code to validate
        strict: If True, apply stricter validation rules
        
    Raises:
        CodeValidationError: If code contains dangerous patterns
    """
    if not code or not code.strip():
        raise CodeValidationError("Code must not be empty.")
    
    if len(code) > 100_000:  # 100KB limit
        raise CodeValidationError("Code exceeds maximum size of 100KB.")
    
    for pattern in _DANGEROUS_PYTHON_PATTERNS:
        if pattern.search(code):
            raise CodeValidationError(
                f"Code contains potentially dangerous pattern: {pattern.pattern}"
            )
    
    if strict:
        # Additional strict mode checks
        if "import" in code.lower() and any(
            dangerous in code.lower()
            for dangerous in ["socket", "http", "urllib", "requests", "ftplib"]
        ):
            raise CodeValidationError(
                "Code contains potentially dangerous network imports in strict mode."
            )


def ensure_safe_file_path(path: str) -> None:
    """Validate that a file path is safe to use.
    
    Args:
        path: File path to validate
        
    Raises:
        PayloadValidationError: If path is unsafe
    """
    if not path or not path.strip():
        raise PayloadValidationError("File path must not be empty.")
    
    # Check for parent directory traversal
    if _PARENT_DIR_PATTERN.search(path):
        raise PayloadValidationError("File path contains parent directory references.")
    
    # Check for absolute paths (should be relative)
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        raise PayloadValidationError("File path must be relative, not absolute.")
    
    # Check for safe characters
    if not _SAFE_PATH_RE.fullmatch(path):
        raise PayloadValidationError(
            "File path contains invalid characters. "
            "Only alphanumerics, hyphens, underscores, slashes, and dots allowed."
        )


def ensure_within_limits(
    value: int | float,
    min_value: int | float | None = None,
    max_value: int | float | None = None,
    field: str = "value",
) -> None:
    """Validate that a numeric value is within specified limits.
    
    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        field: Field name for error messages
        
    Raises:
        PayloadValidationError: If value is out of bounds
    """
    if min_value is not None and value < min_value:
        raise PayloadValidationError(
            f"{field} must be >= {min_value}, got {value}"
        )
    
    if max_value is not None and value > max_value:
        raise PayloadValidationError(
            f"{field} must be <= {max_value}, got {value}"
        )


def ensure_dict_structure(
    data: dict[str, Any],
    required_keys: set[str],
    optional_keys: set[str] | None = None,
) -> None:
    """Validate that a dictionary has the required structure.
    
    Args:
        data: Dictionary to validate
        required_keys: Keys that must be present
        optional_keys: Keys that may be present (default: any other keys allowed)
        
    Raises:
        PayloadValidationError: If structure is invalid
    """
    if not isinstance(data, dict):
        raise PayloadValidationError("Data must be a dictionary.")
    
    # Check for required keys
    missing_keys = required_keys - set(data.keys())
    if missing_keys:
        raise PayloadValidationError(
            f"Missing required keys: {', '.join(sorted(missing_keys))}"
        )
    
    # Check for unexpected keys if optional_keys is specified
    if optional_keys is not None:
        allowed_keys = required_keys | optional_keys
        unexpected_keys = set(data.keys()) - allowed_keys
        if unexpected_keys:
            raise PayloadValidationError(
                f"Unexpected keys: {', '.join(sorted(unexpected_keys))}"
            )


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a string by removing potentially dangerous characters.
    
    Args:
        value: String to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
        
    Raises:
        PayloadValidationError: If string exceeds max length
    """
    if len(value) > max_length:
        raise PayloadValidationError(
            f"String exceeds maximum length of {max_length} characters."
        )
    
    # Remove null bytes and other control characters
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", value)
    
    return sanitized.strip()


def ensure_model(payload: dict[str, object], model: type[BaseModel]) -> BaseModel:
    """Validate and parse payload using Pydantic model.
    
    Args:
        payload: Dictionary payload to validate
        model: Pydantic model class
        
    Returns:
        Validated model instance
        
    Raises:
        PayloadValidationError: If validation fails
    """
    try:
        return model.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - handled by FastAPI tests
        raise PayloadValidationError(str(exc)) from exc


# Convenience aliases for backward compatibility
validate_code = ensure_safe_python_code
validate_language = ensure_supported_language


__all__ = [
    "CodeValidationError",
    "PayloadValidationError",
    "ensure_dict_structure",
    "ensure_model",
    "ensure_safe_cypher",
    "ensure_safe_file_path",
    "ensure_safe_python_code",
    "ensure_supported_language",
    "ensure_valid_identifier",
    "ensure_within_limits",
    "sanitize_string",
    "validate_code",
    "validate_language",
]
