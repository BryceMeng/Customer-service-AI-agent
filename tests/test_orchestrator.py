from app.config import Settings
from app.fixtures import DEMO_CASES
from app.orchestration.state_machine import SupportCoordinator
from app.schemas.case import FinalAction, RunCaseRequest


def run_fixture(fixture_id: str):
    fixture = DEMO_CASES[fixture_id]
    return SupportCoordinator(Settings(APP_ENV="test")).run(
        RunCaseRequest(
            case_id=fixture.case_id,
            user_message=fixture.user_message,
            context=fixture.context,
            mock_backend_state=fixture.mock_backend_state,
        )
    )


def test_duplicate_charge_auto_refund() -> None:
    output = run_fixture("duplicate_charge")

    assert output.final_action == FinalAction.PROCESS_REFUND
    assert output.escalate is False
    assert output.policy_explanation
    assert output.tool_calls[:4] == ["retrieve_similar", "get_customer", "lookup_order", "get_payment_events"]
    assert "process_refund" in output.tool_calls
    assert any(record.action == "process_refund" for record in output.audit_records)


def test_subscription_incident_routes_to_engineering() -> None:
    output = run_fixture("service_incident")

    assert output.final_action == FinalAction.EXPLAIN_INCIDENT_AND_ROUTE
    assert output.escalate is False
    assert output.policy_explanation
    assert output.tool_calls == [
        "retrieve_similar",
        "get_subscription",
        "search_incidents",
        "get_recent_deployments",
        "query_metrics",
        "query_logs",
        "fetch_policy_doc",
    ]


def test_high_risk_locked_account_escalates() -> None:
    output = run_fixture("account_locked")

    assert output.final_action == FinalAction.ESCALATE
    assert output.escalate is True
    assert output.policy_explanation
    assert output.tool_calls == [
        "retrieve_similar",
        "get_customer",
        "request_account_unlock_approval",
        "escalate_to_human",
        "fetch_policy_doc",
    ]
    assert any(record.action == "escalate_to_human" for record in output.audit_records)
