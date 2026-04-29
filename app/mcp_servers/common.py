"""Shared helpers for local MCP SDK servers."""

from typing import Any

from app.schemas.case import BackendState
from app.tools.audit_tools import AuditLog


def parse_backend_state(backend_state: dict[str, Any] | None) -> BackendState:
    """Parse MCP tool state payloads into the app's typed backend state."""

    return BackendState.model_validate(backend_state or {})


def dump_audit_records(audit_log: AuditLog) -> list[dict[str, Any]]:
    """Return JSON-serializable audit records from an audit log."""

    return [record.model_dump() for record in audit_log.records]
