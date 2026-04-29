from app.fixtures import DEMO_CASES
from app.mcp_servers.backend_server import (
    get_customer,
    get_payment_events,
    process_refund,
    refund_idempotency_key,
)
from app.mcp_servers.governance_server import request_refund_approval
from app.mcp_servers.knowledge_server import explain_action, policy_refs
from app.mcp_servers.observability_server import search_incidents
from app.schemas.case import FinalAction, Intent


def test_backend_mcp_tools_wrap_existing_backend_behavior() -> None:
    fixture = DEMO_CASES["duplicate_charge"]
    backend_state = fixture.mock_backend_state.model_dump()

    customer = get_customer(backend_state=backend_state, customer_id="cus_123")
    payments = get_payment_events(backend_state=backend_state, order_id="ord_123")

    assert customer["customer"]["customer_id"] == "cus_123"
    assert len(payments["payments"]) == 2


def test_backend_mcp_refund_write_returns_audit_records() -> None:
    key = refund_idempotency_key(
        case_id="case_123",
        order_id="ord_123",
        amount=49.0,
        reason="duplicate_charge",
    )["idempotency_key"]

    result = process_refund(
        case_id="case_123",
        order_id="ord_123",
        amount=49.0,
        reason="duplicate_charge",
        idempotency_key=key,
    )

    assert result["refund"]["status"] == "accepted"
    assert result["audit_records"][0]["action"] == "process_refund"


def test_governance_mcp_tools_return_approval_and_audit_records() -> None:
    result = request_refund_approval(case_id="case_123", amount=49.0)

    assert result["approval"]["approved"] is True
    assert result["audit_records"][0]["action"] == "request_refund_approval"


def test_observability_mcp_tools_wrap_incident_lookup() -> None:
    fixture = DEMO_CASES["service_incident"]

    result = search_incidents(
        service="api",
        backend_state=fixture.mock_backend_state.model_dump(),
    )

    assert result["incidents"][0]["incident_id"] == "inc_500"


def test_knowledge_mcp_tools_wrap_policy_helpers() -> None:
    refs = policy_refs(Intent.DUPLICATE_CHARGE)
    explanation = explain_action(FinalAction.PROCESS_REFUND)

    assert refs == {"refs": ["refund_policy.duplicate_charge"]}
    assert "refund" in explanation["explanation"].lower()
