"""In-memory audit recorder for local runs."""

from app.schemas.case import AuditRecord


class AuditLog:
    """Collect audit entries for one orchestrator run."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def append(self, case_id: str, action: str, payload: dict) -> AuditRecord:
        """Append and return an audit entry."""

        record = AuditRecord(case_id=case_id, action=action, payload=payload)
        self.records.append(record)
        return record

