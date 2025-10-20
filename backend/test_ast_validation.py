#!/usr/bin/env python
"""Quick test script for AST-based validation."""

import sys
sys.path.insert(0, "/home/donovan/Documents/projects/Ultimate_MCP/backend")

from mcp_server.utils.validation import ensure_safe_python_code, CodeValidationError

# Test cases
test_cases = [
    # Safe code
    ("def add(a, b): return a + b", True, "Simple function"),
    ("print('Hello, world!')", True, "Simple print"),
    ("x = [i**2 for i in range(10)]", True, "List comprehension"),

    # Dangerous imports
    ("import os", False, "Import os module"),
    ("from subprocess import call", False, "Import subprocess"),
    ("import socket", False, "Import socket"),

    # Dangerous function calls
    ("eval('1+1')", False, "Call to eval"),
    ("exec('x = 1')", False, "Call to exec"),
    ("__import__('os')", False, "Call to __import__"),
    ("compile('x=1', '<string>', 'exec')", False, "Call to compile"),

    # Dangerous attribute access
    ("x.__builtins__", False, "Access __builtins__"),
    ("obj.__class__.__bases__", False, "Access __class__.__bases__"),
    ("func.__globals__", False, "Access __globals__"),

    # Bypass attempts
    ("getattr(__builtins__, '__import__')('os')", False, "getattr bypass"),
    ("globals()['__builtins__']", False, "globals() bypass"),

    # String concatenation (should still be caught via AST)
    ("'__' + 'import__'", True, "String concat (just strings, not called)"),
]

print("Running AST-based validation tests...\n")

passed = 0
failed = 0

for code, should_pass, description in test_cases:
    try:
        ensure_safe_python_code(code)
        result = "PASSED"
        actual_pass = True
    except CodeValidationError as e:
        result = f"FAILED: {str(e)[:60]}"
        actual_pass = False

    expected = "PASS" if should_pass else "FAIL"
    actual = "PASS" if actual_pass else "FAIL"

    if (should_pass and actual_pass) or (not should_pass and not actual_pass):
        status = "✓"
        passed += 1
    else:
        status = "✗"
        failed += 1

    print(f"{status} [{expected}→{actual}] {description}")
    print(f"   Code: {code[:50]}")
    print(f"   {result}\n")

print(f"\n{'='*70}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
print(f"{'='*70}")

sys.exit(0 if failed == 0 else 1)
