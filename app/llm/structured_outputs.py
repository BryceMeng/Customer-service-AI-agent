"""Structured output helpers for Claude responses."""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredOutputError(ValueError):
    """Raised when Claude output cannot be parsed into the expected schema."""


def _raw_preview(raw_text: str, limit: int = 500) -> str:
    """Return a bounded repr of Claude's raw text for logs and exceptions."""

    if len(raw_text) <= limit:
        return repr(raw_text)
    return repr(raw_text[:limit] + "...<truncated>")


def parse_json_model(raw_text: str, response_model: type[ModelT]) -> ModelT:
    """Parse raw JSON text into a Pydantic model."""

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            "Claude returned invalid JSON "
            f"({exc.msg} at line {exc.lineno} column {exc.colno} pos {exc.pos}). "
            f"Raw response: {_raw_preview(raw_text)}"
        ) from exc

    try:
        return response_model.model_validate(payload)
    except ValidationError as exc:
        raise StructuredOutputError(
            "Claude JSON failed schema validation "
            f"({exc.errors(include_url=False)}). "
            f"Raw response: {_raw_preview(raw_text)}"
        ) from exc
