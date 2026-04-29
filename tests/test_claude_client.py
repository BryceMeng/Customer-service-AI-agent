from types import SimpleNamespace

import logging

from app.config import Settings
from app.llm.claude_client import ClaudeClient
from app.llm.structured_outputs import StructuredOutputError, parse_json_model
from app.schemas.case import IntakeResult


def test_generate_json_uses_triple_quotes_and_stop_sequences(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="text",
                    text=(
                        '{"intent":"duplicate_charge","confidence":0.9,'
                        '"extracted_slots":{},"missing_fields":["order_id","customer_id"],'
                        '"suggested_next_step":"gather_evidence"}'
                    ),
                )
            ],
            model="claude-haiku-4-5",
            stop_reason="end_turn",
        )

    client = ClaudeClient(
        Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key")
    )
    client._client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))

    result = client.generate_json(
        prompt_name="intake_parse_prompt",
        variables={"user_message": "charged twice"},
        response_model=IntakeResult,
    )

    assert result.intent.value == "duplicate_charge"
    assert captured["stop_sequences"] == ["```"]
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "The json result is ```json"
    content = messages[0]["content"]
    assert isinstance(content, list)
    assert len(content) == 2
    schema_block, variable_block = content
    assert schema_block["cache_control"] == {"type": "ephemeral"}
    assert '"respond_with"' in schema_block["text"]
    assert '"user_message": "charged twice"' in variable_block["text"]
    assert "cache_control" not in variable_block


def test_generate_text_keeps_plain_message_payload() -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            model="claude-haiku-4-5",
            stop_reason="end_turn",
        )

    client = ClaudeClient(
        Settings(APP_ENV="test", DEBUG_MODE=False, ANTHROPIC_API_KEY="test-key")
    )
    client._client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))

    result = client.generate_text(
        prompt_name="user_response_prompt",
        variables={"foo": "bar"},
    )

    assert result == "ok"
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["content"] == '{"foo": "bar"}'


def test_parse_json_model_reports_decode_position_and_raw_response() -> None:
    raw_text = "  "

    try:
        parse_json_model(raw_text, IntakeResult)
    except StructuredOutputError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected StructuredOutputError")

    assert "Claude returned invalid JSON" in message
    assert "line 1 column 3 pos 2" in message
    assert "Raw response: '  '" in message


def test_complete_text_logs_high_level_request_and_response(caplog) -> None:
    def fake_create(**kwargs):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"ok":true}')],
            model="claude-haiku-4-5",
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
        )

    client = ClaudeClient(
        Settings(
            APP_ENV="test",
            DEBUG_MODE=False,
            ANTHROPIC_API_KEY="test-key",
        )
    )
    client._client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))

    with caplog.at_level(logging.DEBUG, logger="app.llm.claude_client"):
        completion = client.complete_text(
            system_prompt="system prompt",
            messages=[{"role": "user", "content": '{"hello":"world"}'}],
            stop_sequences=["```"],
        )

    assert completion.text == '{"ok":true}'
    assert "CLAUDE_API request_started request_id=" in caplog.text
    assert "message_count=1" in caplog.text
    assert "CLAUDE_API request_succeeded request_id=" in caplog.text
    assert "text_length=11" in caplog.text


def test_client_uses_api_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_anthropic(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(messages=SimpleNamespace(create=lambda **_: None))

    monkeypatch.setattr("app.llm.claude_client.Anthropic", fake_anthropic)

    client = ClaudeClient(
        Settings(
            APP_ENV="test",
            DEBUG_MODE=False,
            ANTHROPIC_API_KEY="test-key",
        )
    )

    resolved = client.client

    assert resolved is not None
    assert captured["api_key"] == "test-key"
    assert "auth_token" not in captured
