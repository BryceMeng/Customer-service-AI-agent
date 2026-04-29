import logging

from app.agents.policy_agent import ground_policy, policy_guided_refund_decision
from app.config import Settings
from app.schemas.case import FinalAction, Intent, PolicyGroundingOutput, PolicyRefundDecision, ToolCallRecord


def test_policy_agent_uses_claude_grounding_output(monkeypatch) -> None:
    def fake_generate_json(self, **kwargs):
        assert kwargs["variables"]["final_action"] == "process_refund"
        assert "policy_docs" in kwargs["variables"]
        assert kwargs["variables"]["tool_evidence"][0]["tool_name"] == "get_payment_events"
        return PolicyGroundingOutput(
            explanation="Duplicate charge policy supports issuing a refund.",
            refs=["refund_policy.duplicate_charge"],
        )

    monkeypatch.setattr(
        "app.agents.policy_agent.ClaudeClient.generate_json",
        fake_generate_json,
    )

    grounding = ground_policy(
        Intent.DUPLICATE_CHARGE,
        FinalAction.PROCESS_REFUND,
        [
            ToolCallRecord(
                tool_name="get_payment_events",
                arguments={"order_id": "ord_123"},
                result={"payments": [{"payment_id": "pay_1"}]},
            )
        ],
        Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key"),
    )

    assert grounding.refs == ["refund_policy.duplicate_charge"]
    assert "supports issuing a refund" in grounding.explanation


def test_policy_agent_falls_back_to_static_grounding(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.agents.policy_agent"):
        grounding = ground_policy(
            Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING,
            FinalAction.EXPLAIN_INCIDENT_AND_ROUTE,
            [],
            Settings(APP_ENV="test", DEBUG_MODE=True),
        )

    assert grounding.refs == ["sla_policy.incident_response"]
    assert "sla_policy.incident_response" in grounding.explanation
    assert "AGENT:policy  source=rules" in caplog.text


# --- policy_guided_refund_decision unit tests ---

POLICY_DOCS = {"refund_policy.standard": "Refund within 30 days if paid and refundable."}
DEBUG_SETTINGS = Settings(APP_ENV="test", DEBUG_MODE=True)
CLAUDE_SETTINGS = Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key")


def _order(*, amount=50.0, status="paid", refundable=True, days=10):
    return {
        "order_id": "TEST-1",
        "customer_id": "cus_1",
        "amount": amount,
        "status": status,
        "refundable": refundable,
        "days_since_purchase": days,
    }


# -- Deterministic fallback (no Claude) --

def test_refund_decision_none_order_denies() -> None:
    action = policy_guided_refund_decision(None, POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.DENY_WITH_EXPLANATION


def test_refund_decision_outside_window_denies() -> None:
    action = policy_guided_refund_decision(_order(days=31), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.DENY_WITH_EXPLANATION


def test_refund_decision_boundary_day_30_approves() -> None:
    action = policy_guided_refund_decision(_order(days=30), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.PROCESS_REFUND


def test_refund_decision_boundary_day_31_denies() -> None:
    action = policy_guided_refund_decision(_order(days=31), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.DENY_WITH_EXPLANATION


def test_refund_decision_not_refundable_denies() -> None:
    action = policy_guided_refund_decision(_order(refundable=False), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.DENY_WITH_EXPLANATION


def test_refund_decision_null_days_treated_as_within_window() -> None:
    order = _order()
    order["days_since_purchase"] = None
    action = policy_guided_refund_decision(order, POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.PROCESS_REFUND


def test_refund_decision_non_paid_status_escalates() -> None:
    action = policy_guided_refund_decision(_order(status="shipped"), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.ESCALATE


def test_refund_decision_pending_status_escalates() -> None:
    action = policy_guided_refund_decision(_order(status="pending"), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.ESCALATE


def test_refund_decision_paid_within_window_approves() -> None:
    action = policy_guided_refund_decision(_order(), POLICY_DOCS, settings=DEBUG_SETTINGS)
    assert action == FinalAction.PROCESS_REFUND


# -- Claude path --

def test_refund_decision_uses_claude_when_available(monkeypatch) -> None:
    def fake_generate_json(self, **kwargs):
        assert "policy_text" in kwargs["cached_variables"]
        assert "order" in kwargs["variables"]
        return PolicyRefundDecision(recommended_action=FinalAction.PROCESS_REFUND, reason="within window")

    monkeypatch.setattr("app.agents.policy_agent.ClaudeClient.generate_json", fake_generate_json)
    action = policy_guided_refund_decision(_order(), POLICY_DOCS, settings=CLAUDE_SETTINGS)
    assert action == FinalAction.PROCESS_REFUND


def test_refund_decision_claude_can_deny(monkeypatch) -> None:
    def fake_generate_json(self, **kwargs):
        return PolicyRefundDecision(recommended_action=FinalAction.DENY_WITH_EXPLANATION, reason="outside window")

    monkeypatch.setattr("app.agents.policy_agent.ClaudeClient.generate_json", fake_generate_json)
    action = policy_guided_refund_decision(_order(), POLICY_DOCS, settings=CLAUDE_SETTINGS)
    assert action == FinalAction.DENY_WITH_EXPLANATION


def test_refund_decision_claude_can_escalate(monkeypatch) -> None:
    def fake_generate_json(self, **kwargs):
        return PolicyRefundDecision(recommended_action=FinalAction.ESCALATE, reason="non-paid status")

    monkeypatch.setattr("app.agents.policy_agent.ClaudeClient.generate_json", fake_generate_json)
    action = policy_guided_refund_decision(_order(status="shipped"), POLICY_DOCS, settings=CLAUDE_SETTINGS)
    assert action == FinalAction.ESCALATE


def test_refund_decision_falls_back_to_rules_on_claude_failure(monkeypatch, caplog) -> None:
    def fake_generate_json(self, **kwargs):
        raise RuntimeError("API timeout")

    monkeypatch.setattr("app.agents.policy_agent.ClaudeClient.generate_json", fake_generate_json)
    with caplog.at_level(logging.WARNING, logger="app.agents.policy_agent"):
        action = policy_guided_refund_decision(_order(), POLICY_DOCS, settings=CLAUDE_SETTINGS)

    assert action == FinalAction.PROCESS_REFUND
    assert "falling back to rules" in caplog.text
