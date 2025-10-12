"""Tests for enhanced input validation."""

from __future__ import annotations

import pytest
from mcp_server.utils.validation import (
    CodeValidationError,
    PayloadValidationError,
    ensure_dict_structure,
    ensure_safe_cypher,
    ensure_safe_file_path,
    ensure_safe_python_code,
    ensure_supported_language,
    ensure_valid_identifier,
    ensure_within_limits,
    sanitize_string,
)


def test_ensure_supported_language_valid():
    """Test validation of supported languages."""
    ensure_supported_language("python")
    ensure_supported_language("Python")  # Case insensitive
    ensure_supported_language("javascript")
    ensure_supported_language("bash")


def test_ensure_supported_language_invalid():
    """Test rejection of unsupported languages."""
    with pytest.raises(PayloadValidationError, match="not supported"):
        ensure_supported_language("ruby")
    
    with pytest.raises(PayloadValidationError, match="not supported"):
        ensure_supported_language("java")


def test_ensure_valid_identifier_valid():
    """Test validation of valid identifiers."""
    ensure_valid_identifier("valid_name")
    ensure_valid_identifier("ValidName")
    ensure_valid_identifier("valid-name")
    ensure_valid_identifier("_private")
    ensure_valid_identifier("name123")


def test_ensure_valid_identifier_invalid():
    """Test rejection of invalid identifiers."""
    with pytest.raises(PayloadValidationError, match="must match"):
        ensure_valid_identifier("123invalid")  # Starts with number
    
    with pytest.raises(PayloadValidationError, match="must match"):
        ensure_valid_identifier("invalid name")  # Contains space
    
    with pytest.raises(PayloadValidationError, match="must match"):
        ensure_valid_identifier("a" * 65)  # Too long


def test_ensure_safe_cypher_valid():
    """Test validation of safe Cypher queries."""
    ensure_safe_cypher("MATCH (n) RETURN n")
    ensure_safe_cypher("MATCH (n:User) WHERE n.id = $id RETURN n")
    ensure_safe_cypher("CREATE (n:Node {key: $key})")


def test_ensure_safe_cypher_forbidden_operations():
    """Test rejection of dangerous Cypher operations."""
    with pytest.raises(PayloadValidationError, match="forbidden"):
        ensure_safe_cypher("DELETE n")
    
    with pytest.raises(PayloadValidationError, match="forbidden"):
        ensure_safe_cypher("DETACH DELETE n")
    
    with pytest.raises(PayloadValidationError, match="forbidden"):
        ensure_safe_cypher("DROP INDEX")
    
    with pytest.raises(PayloadValidationError, match="forbidden"):
        ensure_safe_cypher("REMOVE n.property")
    
    with pytest.raises(PayloadValidationError, match="forbidden"):
        ensure_safe_cypher("MATCH (n); MATCH (m) RETURN m")  # Semicolon


def test_ensure_safe_cypher_empty():
    """Test rejection of empty Cypher queries."""
    with pytest.raises(PayloadValidationError, match="must not be empty"):
        ensure_safe_cypher("")
    
    with pytest.raises(PayloadValidationError, match="must not be empty"):
        ensure_safe_cypher("   ")


def test_ensure_safe_python_code_valid():
    """Test validation of safe Python code."""
    ensure_safe_python_code("print('hello')")
    ensure_safe_python_code("x = 1 + 2")
    ensure_safe_python_code("def foo(): return 42")


def test_ensure_safe_python_code_dangerous_patterns():
    """Test rejection of dangerous Python patterns."""
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("eval('1+1')")
    
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("exec('print(1)')")
    
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("__import__('os')")
    
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("compile('1+1', '<string>', 'eval')")
    
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("open('file.txt', 'w')")
    
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("os.system('ls')")
    
    with pytest.raises(CodeValidationError, match="dangerous pattern"):
        ensure_safe_python_code("import subprocess")


def test_ensure_safe_python_code_empty():
    """Test rejection of empty code."""
    with pytest.raises(CodeValidationError, match="must not be empty"):
        ensure_safe_python_code("")
    
    with pytest.raises(CodeValidationError, match="must not be empty"):
        ensure_safe_python_code("   ")


def test_ensure_safe_python_code_size_limit():
    """Test rejection of oversized code."""
    large_code = "x = 1\n" * 50_000  # > 100KB
    with pytest.raises(CodeValidationError, match="exceeds maximum size"):
        ensure_safe_python_code(large_code)


def test_ensure_safe_python_code_strict_mode():
    """Test strict mode validation."""
    # Should pass in non-strict mode
    ensure_safe_python_code("import json")
    
    # Should fail in strict mode for network imports
    with pytest.raises(CodeValidationError, match="dangerous network imports"):
        ensure_safe_python_code("import socket", strict=True)
    
    with pytest.raises(CodeValidationError, match="dangerous network imports"):
        ensure_safe_python_code("from http.client import HTTPConnection", strict=True)


def test_ensure_safe_file_path_valid():
    """Test validation of safe file paths."""
    ensure_safe_file_path("file.txt")
    ensure_safe_file_path("dir/file.txt")
    ensure_safe_file_path("path/to/file.py")
    ensure_safe_file_path("valid-name_123.json")


def test_ensure_safe_file_path_parent_traversal():
    """Test rejection of parent directory traversal."""
    with pytest.raises(PayloadValidationError, match="parent directory"):
        ensure_safe_file_path("../file.txt")
    
    with pytest.raises(PayloadValidationError, match="parent directory"):
        ensure_safe_file_path("dir/../../etc/passwd")


def test_ensure_safe_file_path_absolute():
    """Test rejection of absolute paths."""
    with pytest.raises(PayloadValidationError, match="must be relative"):
        ensure_safe_file_path("/etc/passwd")
    
    with pytest.raises(PayloadValidationError, match="must be relative"):
        ensure_safe_file_path("C:/Windows/System32")


def test_ensure_safe_file_path_invalid_characters():
    """Test rejection of invalid characters in paths."""
    with pytest.raises(PayloadValidationError, match="invalid characters"):
        ensure_safe_file_path("file; rm -rf /")
    
    with pytest.raises(PayloadValidationError, match="invalid characters"):
        ensure_safe_file_path("file\x00.txt")


def test_ensure_safe_file_path_empty():
    """Test rejection of empty paths."""
    with pytest.raises(PayloadValidationError, match="must not be empty"):
        ensure_safe_file_path("")
    
    with pytest.raises(PayloadValidationError, match="must not be empty"):
        ensure_safe_file_path("   ")


def test_ensure_within_limits_valid():
    """Test validation of values within limits."""
    ensure_within_limits(5, min_value=0, max_value=10)
    ensure_within_limits(0, min_value=0)
    ensure_within_limits(100, max_value=100)
    ensure_within_limits(3.14, min_value=0.0, max_value=10.0)


def test_ensure_within_limits_below_minimum():
    """Test rejection of values below minimum."""
    with pytest.raises(PayloadValidationError, match="must be >="):
        ensure_within_limits(-1, min_value=0)
    
    with pytest.raises(PayloadValidationError, match="must be >="):
        ensure_within_limits(5, min_value=10, field="timeout")


def test_ensure_within_limits_above_maximum():
    """Test rejection of values above maximum."""
    with pytest.raises(PayloadValidationError, match="must be <="):
        ensure_within_limits(11, max_value=10)
    
    with pytest.raises(PayloadValidationError, match="must be <="):
        ensure_within_limits(100, max_value=50, field="size")


def test_ensure_dict_structure_valid():
    """Test validation of dictionary structure."""
    data = {"required1": "value1", "required2": "value2", "optional": "value3"}
    ensure_dict_structure(
        data,
        required_keys={"required1", "required2"},
        optional_keys={"optional"},
    )


def test_ensure_dict_structure_missing_required():
    """Test rejection of missing required keys."""
    data = {"required1": "value1"}
    with pytest.raises(PayloadValidationError, match="Missing required keys"):
        ensure_dict_structure(data, required_keys={"required1", "required2"})


def test_ensure_dict_structure_unexpected_keys():
    """Test rejection of unexpected keys."""
    data = {"required": "value", "unexpected": "value"}
    with pytest.raises(PayloadValidationError, match="Unexpected keys"):
        ensure_dict_structure(
            data,
            required_keys={"required"},
            optional_keys=set(),
        )


def test_ensure_dict_structure_any_additional_keys():
    """Test allowing any additional keys when optional_keys not specified."""
    data = {"required": "value", "anything": "else"}
    # Should not raise
    ensure_dict_structure(data, required_keys={"required"})


def test_ensure_dict_structure_not_dict():
    """Test rejection of non-dictionary data."""
    with pytest.raises(PayloadValidationError, match="must be a dictionary"):
        ensure_dict_structure("not a dict", required_keys=set())  # type: ignore


def test_sanitize_string_normal():
    """Test sanitizing normal strings."""
    assert sanitize_string("  hello world  ") == "hello world"
    assert sanitize_string("valid string") == "valid string"


def test_sanitize_string_control_characters():
    """Test removal of control characters."""
    result = sanitize_string("hello\x00world\x01test")
    assert "\x00" not in result
    assert "\x01" not in result
    assert "helloworldtest" in result


def test_sanitize_string_max_length():
    """Test enforcement of maximum length."""
    with pytest.raises(PayloadValidationError, match="exceeds maximum length"):
        sanitize_string("a" * 1001)
    
    # Should pass with custom max
    assert sanitize_string("a" * 100, max_length=100) == "a" * 100


def test_sanitize_string_preserves_unicode():
    """Test that sanitization preserves valid Unicode characters."""
    text = "Hello 世界 🌍"
    assert sanitize_string(text) == text
