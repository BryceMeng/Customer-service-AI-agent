"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Support Agent service."""

    app_env: str = Field(default="development", alias="APP_ENV")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-haiku-4-5", alias="CLAUDE_MODEL")
    claude_small_model: str = Field(default="claude-haiku-4-5", alias="CLAUDE_SMALL_MODEL")
    claude_temperature: float = Field(default=0.2, alias="CLAUDE_TEMPERATURE", ge=0, le=1)
    claude_max_tokens: int = Field(default=2000, alias="CLAUDE_MAX_TOKENS", ge=1)
    debug_mode: bool = Field(default=False, alias="DEBUG_MODE")
    state_db_path: str = Field(default="support_agent_state.sqlite3", alias="STATE_DB_PATH")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def has_claude_credentials(self) -> bool:
        """Return whether Claude API credentials are configured."""

        return bool(self.anthropic_api_key)

    @property
    def claude_auth_mode(self) -> str | None:
        """Return the preferred Claude auth mode for the current settings."""

        if self.anthropic_api_key:
            return "api_key"
        return None


@lru_cache
def get_settings() -> Settings:
    """Return cached settings read from the current process environment."""

    return Settings()
