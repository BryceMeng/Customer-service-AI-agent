import logging

from app.agents.report_agent import build_audit_note, build_user_response
from app.config import Settings
from app.schemas.case import AgentRunOutput, FinalAction, Intent, UserResponseOutput


def test_build_user_response_logs_claude_success(caplog, monkeypatch) -> None:
    def fake_generate_json(self, **kwargs):
        return UserResponseOutput(response="Claude response")

    monkeypatch.setattr(
        "app.agents.report_agent.ClaudeClient.generate_json",
        fake_generate_json,
    )

    with caplog.at_level(logging.INFO, logger="app.agents.report_agent"):
        response = build_user_response(
            final_action=FinalAction.ESCALATE,
            intent=Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING,
            policy_explanation="Policy requires manual review.",
            settings=Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key"),
        )

    assert response == "Claude response"
    assert "AGENT:report  source=claude  target=user_response  final_action=escalate" in caplog.text


def test_build_audit_note_logs_claude_failure_and_falls_back(caplog, monkeypatch) -> None:
    def fake_generate_json(self, **kwargs):
        raise RuntimeError("bad response")

    monkeypatch.setattr(
        "app.agents.report_agent.ClaudeClient.generate_json",
        fake_generate_json,
    )
    output = AgentRunOutput(
        case_id="case_123",
        intent=Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING,
        confidence=0.9,
        final_action=FinalAction.ESCALATE,
        escalate=True,
        user_response="x",
        audit_note="",
    )

    with caplog.at_level(logging.WARNING, logger="app.agents.report_agent"):
        note = build_audit_note(
            output,
            settings=Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key"),
        )

    assert "Case case_123:" in note
    assert (
        "AGENT:report  source=claude  target=audit_note  status=failed  case_id=case_123  error=bad response  falling back to template"
        in caplog.text
    )
