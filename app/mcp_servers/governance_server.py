"""Governance MCP server implemented with the MCP Python SDK."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.common import dump_audit_records
from app.tools.audit_tools import AuditLog
from app.tools.governance_tools import GovernanceTools

mcp = FastMCP("support-governance")


@mcp.tool()
def request_refund_approval(*, case_id: str, amount: float) -> dict[str, Any]:
    """Request approval for a refund."""

    audit_log = AuditLog()
    approval = GovernanceTools(audit_log).request_refund_approval(
        case_id=case_id,
        amount=amount,
    )
    return {"approval": approval, "audit_records": dump_audit_records(audit_log)}


@mcp.tool()
def request_account_unlock_approval(*, case_id: str) -> dict[str, Any]:
    """Request approval for an account unlock."""

    audit_log = AuditLog()
    approval = GovernanceTools(audit_log).request_account_unlock_approval(case_id=case_id)
    return {"approval": approval, "audit_records": dump_audit_records(audit_log)}


def main() -> None:
    """Run the governance MCP server over streamable HTTP."""

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
