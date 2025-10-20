"""Input validation helpers for API and tool payloads."""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

_ALLOWED_LANGUAGES = {"python", "javascript", "bash"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-:]{0,63}$")
_FORBIDDEN_CYPHER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bCALL\s+db\.|\bCALL\s+dbms\.", re.IGNORECASE),
    re.compile(r"\bDELETE\b", re.IGNORECASE),
    re.compile(r"\bDETACH\b", re.IGNORECASE),
    re.compile(r"\bREMOVE\b", re.IGNORECASE),
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(r";"),
)

# Dangerous Python modules and functions for AST-based validation
_DANGEROUS_MODULES: set[str] = {
    "os",
    "subprocess",
    "sys",
    "socket",
    "http",
    "urllib",
    "urllib2",
    "urllib3",
    "requests",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc",
    "pickle",
    "shelve",
    "marshal",
    "code",
    "codeop",
    "pty",
    "tty",
    "termios",
    "fcntl",
    "resource",
    "ctypes",
    "cffi",
    "importlib",
    "imp",
    "runpy",
    "multiprocessing",
    "threading",
    "asyncio",
}

_DANGEROUS_FUNCTIONS: set[str] = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "execfile",
    "input",  # Python 2 input is dangerous
    "breakpoint",
    "exit",
    "quit",
    "help",
    "open",  # Can be dangerous for file I/O
    "file",  # Python 2
    "reload",
    "vars",
    "locals",
    "globals",
    "dir",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
}

_DANGEROUS_ATTRIBUTES: set[str] = {
    "__builtins__",
    "__globals__",
    "__code__",
    "__class__",
    "__bases__",
    "__subclasses__",
    "__import__",
    "__loader__",
    "__spec__",
    "__package__",
    "func_globals",
    "func_code",
}


class PythonSecurityChecker(ast.NodeVisitor):
    """AST-based security checker for Python code.

    Validates Python code by traversing the AST and checking for:
    - Dangerous imports
    - Dangerous function calls
    - Dangerous attribute access
    - Attempts to access internal Python structures
    """

    def __init__(self, strict: bool = False) -> None:
        """Initialize security checker.

        Args:
            strict: If True, apply stricter rules (e.g., no file I/O at all)
        """
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Check Import statements."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]  # Get top-level module
            if module_name in _DANGEROUS_MODULES:
                self.errors.append(
                    f"Line {node.lineno}: Dangerous import of '{alias.name}' is not allowed"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check ImportFrom statements."""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in _DANGEROUS_MODULES:
                self.errors.append(
                    f"Line {node.lineno}: Dangerous import from '{node.module}' is not allowed"
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check function calls."""
        func_name = self._get_call_name(node)

        if func_name in _DANGEROUS_FUNCTIONS:
            self.errors.append(
                f"Line {node.lineno}: Call to dangerous function '{func_name}' is not allowed"
            )

        # Check for open() with write modes in strict mode
        if self.strict and func_name == "open":
            if len(node.args) >= 2:
                mode_arg = node.args[1]
                if isinstance(mode_arg, ast.Constant) and isinstance(mode_arg.value, str):
                    if any(m in mode_arg.value for m in ["w", "a", "x", "+"]):
                        self.errors.append(
                            f"Line {node.lineno}: File writing with open() is not allowed in strict mode"
                        )

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check attribute access."""
        if node.attr in _DANGEROUS_ATTRIBUTES:
            self.errors.append(
                f"Line {node.lineno}: Access to dangerous attribute '{node.attr}' is not allowed"
            )

        # Check for attribute chains like obj.__class__.__bases__
        if isinstance(node.value, ast.Attribute) and node.value.attr in _DANGEROUS_ATTRIBUTES:
            self.errors.append(
                f"Line {node.lineno}: Chained access to dangerous attributes is not allowed"
            )

        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Check name access."""
        # Check for direct access to dangerous built-in names
        if node.id in _DANGEROUS_ATTRIBUTES:
            self.errors.append(
                f"Line {node.lineno}: Access to dangerous name '{node.id}' is not allowed"
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Check subscript operations (e.g., obj['key'])."""
        # Check for __dict__ access via subscript
        if isinstance(node.slice, ast.Constant):
            if node.slice.value in _DANGEROUS_ATTRIBUTES:
                self.errors.append(
                    f"Line {node.lineno}: Subscript access to '{node.slice.value}' is not allowed"
                )
        self.generic_visit(node)

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract function name from call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        elif isinstance(node.func, ast.Call):
            # Nested call like func()()
            return self._get_call_name(node.func)
        return ""

    def check_code(self, tree: ast.AST) -> tuple[bool, list[str], list[str]]:
        """Check code AST for security issues.

        Args:
            tree: Parsed AST tree

        Returns:
            Tuple of (is_safe, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        self.visit(tree)
        return (len(self.errors) == 0, self.errors, self.warnings)

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
    """Validate that Python code doesn't contain dangerous patterns using AST analysis.

    This function performs comprehensive security validation by parsing the Python
    code into an Abstract Syntax Tree (AST) and checking for:
    - Dangerous imports (os, subprocess, socket, etc.)
    - Dangerous function calls (eval, exec, __import__, etc.)
    - Dangerous attribute access (__builtins__, __globals__, etc.)
    - Attempts to access or manipulate internal Python structures

    Args:
        code: Python code to validate
        strict: If True, apply stricter rules (e.g., no file I/O, no threading)

    Raises:
        CodeValidationError: If code contains dangerous patterns or fails to parse
    """
    if not code or not code.strip():
        raise CodeValidationError("Code must not be empty.")

    if len(code) > 100_000:  # 100KB limit
        raise CodeValidationError("Code exceeds maximum size of 100KB.")

    # Parse code into AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise CodeValidationError(
            f"Code contains syntax errors: {e.msg} at line {e.lineno}"
        ) from e
    except ValueError as e:
        raise CodeValidationError(f"Code parsing failed: {str(e)}") from e

    # Run security checker
    checker = PythonSecurityChecker(strict=strict)
    is_safe, errors, warnings = checker.check_code(tree)

    # Log warnings but don't fail
    for warning in warnings:
        logger.warning(f"Code security warning: {warning}")

    # Fail on any errors
    if not is_safe:
        error_summary = "; ".join(errors[:3])  # Show first 3 errors
        if len(errors) > 3:
            error_summary += f" (and {len(errors) - 3} more)"
        raise CodeValidationError(f"Code contains security violations: {error_summary}")


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
