"""Governance gates for high-risk write operations."""

from app.tools.audit_tools import AuditLog


class GovernanceTools:
    """Approval tool simulation for controlled operations."""

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log

    def request_refund_approval(self, *, case_id: str, amount: float) -> dict:
        approved = amount <= 100
        payload = {"amount": amount, "approved": approved}
        self._audit_log.append(case_id, "request_refund_approval", payload)
        return payload

    def request_account_unlock_approval(self, *, case_id: str) -> dict:
        payload = {"approved": False, "reason": "high_risk_account_requires_human_review"}
        self._audit_log.append(case_id, "request_account_unlock_approval", payload)
        return payload

