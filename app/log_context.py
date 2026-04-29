"""Logging context for per-request case_id injection."""

import contextvars
import logging

_case_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("case_id", default="-")


def set_case_id(case_id: str) -> None:
    _case_id_var.set(case_id)


class CaseIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.case_id = _case_id_var.get()  # type: ignore[attr-defined]
        return True
