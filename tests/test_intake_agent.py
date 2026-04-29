import logging

from app.agents.intake_agent import IntakeAgent
from app.config import Settings
from app.llm.structured_outputs import StructuredOutputError


def test_intake_agent_logs_detailed_claude_parse_error(monkeypatch, caplog) -> None:
    def fake_parse_with_claude(self, user_message, backend_state):
        raise StructuredOutputError(
            "Claude returned invalid JSON (Expecting value at line 1 column 3 pos 2). "
            "Raw response: '  '"
        )

    monkeypatch.setattr(
        "app.agents.intake_agent.IntakeAgent._parse_with_claude",
        fake_parse_with_claude,
    )
    caplog.set_level(logging.WARNING)

    result = IntakeAgent(
        Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key")
    ).parse("charged twice on ord_123 for cus_456")

    assert result.intent.value == "duplicate_charge"
    assert "Claude returned invalid JSON (Expecting value at line 1 column 3 pos 2)." in caplog.text
    assert "Raw response: '  '" in caplog.text
    assert "falling back to rules" in caplog.text
