"""Security utilities for validating user-provided code before execution."""

from __future__ import annotations

import ast
from typing import Iterable


class SecurityViolationError(RuntimeError):
    """Raised when a payload violates execution safety rules."""


DISALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "subprocess",
        "socket",
        "shutil",
        "pathlib",
        "asyncio",
        "multiprocessing",
        "signal",
        "inspect",
        "importlib",
        "ctypes",
        "resource",
        "fcntl",
        "pty",
        "pwd",
        "grp",
    }
)

DISALLOWED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "eval",
        "exec",
        "open",
        "compile",
        "__import__",
        "globals",
        "locals",
        "input",
    }
)


def _iter_names(node: ast.AST) -> Iterable[str]:
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            yield child.id
        elif isinstance(child, ast.Attribute):
            yield child.attr


def ensure_safe_python(code: str) -> None:
    """Validate Python source before execution.

    The validator is intentionally conservative. It blocks imports of dangerous modules and
    disallows common escape hatches such as ``eval`` and ``exec``. The caller should surface the
    raised :class:`SecurityViolationError` as a user-facing error response.
    """

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:  # pragma: no cover - FastAPI handles parse errors
        raise SecurityViolationError("Provided code is not syntactically valid Python") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in DISALLOWED_MODULES:
                    raise SecurityViolationError(
                        f"Importing module '{root}' is not allowed in execution requests."
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in DISALLOWED_MODULES:
                    raise SecurityViolationError(
                        f"Importing from module '{root}' is not allowed in execution requests."
                    )

    for name in _iter_names(tree):
        if name in DISALLOWED_FUNCTIONS:
            raise SecurityViolationError(f"Usage of '{name}' is blocked for safety reasons.")


__all__ = ["ensure_safe_python", "SecurityViolationError"]
