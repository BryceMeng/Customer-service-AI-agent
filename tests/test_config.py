from pathlib import Path

from app.config import Settings


def test_settings_reads_anthropic_key_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-dotenv-key\n", encoding="utf-8")

    settings = Settings()

    assert settings.anthropic_api_key == "test-dotenv-key"
    assert settings.claude_auth_mode == "api_key"
    assert settings.has_claude_credentials is True


def test_settings_uses_api_key_auth_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-dotenv-key\n", encoding="utf-8")

    settings = Settings()

    assert settings.anthropic_api_key == "test-dotenv-key"
    assert settings.claude_auth_mode == "api_key"
    assert settings.has_claude_credentials is True
