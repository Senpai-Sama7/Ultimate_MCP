"""Input validation helpers for API and tool payloads."""

from __future__ import annotations

import re

from pydantic import BaseModel, ValidationError

_ALLOWED_LANGUAGES = {"python"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")
_FORBIDDEN_CYPHER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\\bCALL\\s+db\\.|\\bCALL\\s+dbms\\.", re.IGNORECASE),
    re.compile(r"\\bDELETE\\b", re.IGNORECASE),
    re.compile(r"\\bDETACH\\b", re.IGNORECASE),
    re.compile(r"\\bREMOVE\\b", re.IGNORECASE),
    re.compile(r"\\bDROP\\b", re.IGNORECASE),
    re.compile(r";"),
)


class PayloadValidationError(ValueError):
    """Raised when incoming payload validation fails."""


def ensure_supported_language(language: str) -> None:
    if language.lower() not in _ALLOWED_LANGUAGES:
        raise PayloadValidationError(f"Language '{language}' is not supported.")


def ensure_valid_identifier(value: str, *, field: str = "identifier") -> None:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise PayloadValidationError(
            f"{field} must match {_IDENTIFIER_RE.pattern!r} and be <= 64 characters."
        )


def ensure_safe_cypher(query: str) -> None:
    normalized = query.strip()
    if not normalized:
        raise PayloadValidationError("Cypher query must not be empty.")

    for pattern in _FORBIDDEN_CYPHER_PATTERNS:
        if pattern.search(normalized):
            raise PayloadValidationError("Cypher query contains forbidden operations.")


def ensure_model(payload: dict[str, object], model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - handled by FastAPI tests
        raise PayloadValidationError(str(exc)) from exc


__all__ = [
    "PayloadValidationError",
    "ensure_supported_language",
    "ensure_valid_identifier",
    "ensure_safe_cypher",
    "ensure_model",
]
