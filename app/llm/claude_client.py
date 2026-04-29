"""Centralized Anthropic Claude API client."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
import logging
from typing import Any, TypeVar
from uuid import uuid4

from anthropic import Anthropic
from anthropic.types import MessageParam
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.llm.prompts import get_prompt
from app.llm.structured_outputs import StructuredOutputError, parse_json_model

ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)

_RESET   = "\033[0m"
_CYAN    = "\033[36m"
_MAGENTA = "\033[35m"


@dataclass(frozen=True)
class ClaudeCompletion:
    """Text response metadata returned by Claude."""

    text: str
    model: str
    stop_reason: str | None
    request_id: str


class ClaudeClient:
    """All Claude API calls go through this client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        """Lazily initialize the Anthropic SDK client."""

        auth_mode = self._settings.claude_auth_mode
        if auth_mode is None:
            raise RuntimeError("ANTHROPIC_API_KEY must be set before calling Claude.")

        if self._client is None:
            self._client = Anthropic(api_key=self._settings.anthropic_api_key)

        return self._client

    def complete_text(
        self,
        *,
        system_prompt: str,
        messages: Sequence[MessageParam],
        max_tokens: int | None = None,
        stop_sequences: Sequence[str] | None = None,
        temperature: float | None = None,
    ) -> ClaudeCompletion:
        """Call Claude and return the concatenated text response."""

        if self._settings.debug_mode:
            raise RuntimeError(
                "ClaudeClient: debug_mode is enabled — real API calls are blocked."
            )

        request_id = str(uuid4())
        request_messages = list(messages)
        request_system_prompt = system_prompt
        request_stop_sequences = list(stop_sequences) if stop_sequences else None
        request_max_tokens = max_tokens or self._settings.claude_max_tokens
        request_temperature = temperature if temperature is not None else self._settings.claude_temperature
        logger.debug(
            "CLAUDE_API request_started request_id=%s model=%s message_count=%s max_tokens=%s",
            request_id,
            self._settings.claude_model,
            len(request_messages),
            request_max_tokens,
        )
        logger.debug("%sclaude system | %s%s", _CYAN, request_system_prompt, _RESET)
        for msg in request_messages:
            logger.debug("%sclaude %s | %s%s", _CYAN, msg["role"], msg["content"], _RESET)
        try:
            response = self.client.messages.create(
                model=self._settings.claude_model,
                max_tokens=request_max_tokens,
                temperature=request_temperature,
                system=[
                    {
                        "type": "text",
                        "text": request_system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=request_messages,
                stop_sequences=request_stop_sequences,
            )
        except Exception as exc:
            logger.debug(
                "CLAUDE_API request_failed request_id=%s error_type=%s error=%s",
                request_id,
                type(exc).__name__,
                exc,
            )
            raise
        text_parts = [
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ]
        response_text = "".join(text_parts)
        logger.debug(
            "CLAUDE_API request_succeeded request_id=%s model=%s stop_reason=%s text_length=%s",
            request_id,
            response.model,
            response.stop_reason,
            len(response_text),
        )
        logger.debug("%sclaude response | %s%s", _MAGENTA, response_text, _RESET)
        return ClaudeCompletion(
            text=response_text,
            model=response.model,
            stop_reason=response.stop_reason,
            request_id=request_id,
        )

    def generate_text(
        self,
        *,
        prompt_name: str,
        variables: Mapping[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Render a named prompt and return text."""

        prompt = get_prompt(prompt_name)
        message = json.dumps(dict(variables), sort_keys=True)
        completion = self.complete_text(
            system_prompt=prompt,
            messages=[
                {
                    "role": "user",
                    "content": message,
                }
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.text

    def generate_json(
        self,
        *,
        prompt_name: str,
        variables: Mapping[str, Any],
        response_model: type[ModelT],
        max_attempts: int = 2,
        schema_override: dict | None = None,
        cached_variables: Mapping[str, Any] | None = None,
        temperature: float | None = None,
    ) -> ModelT:
        """Render a named prompt and parse Claude's JSON into a Pydantic model."""

        last_error: StructuredOutputError | None = None
        for attempt in range(max_attempts):
            schema = schema_override or response_model.model_json_schema()
            prompt = get_prompt(prompt_name)
            content: list[dict] = [
                {
                    "type": "text",
                    "text": json.dumps({"respond_with": schema}, sort_keys=True),
                    "cache_control": {"type": "ephemeral"},
                },
            ]
            if cached_variables:
                content.append({
                    "type": "text",
                    "text": json.dumps(dict(cached_variables), sort_keys=True),
                    "cache_control": {"type": "ephemeral"},
                })
            content.append({
                "type": "text",
                "text": json.dumps(dict(variables), sort_keys=True),
            })
            completion = self.complete_text(
                system_prompt=prompt,
                messages=[
                    {
                        "role": "user",
                        "content": content,
                    },
                    {# prefill: if it is openAI, there is a json mode to use
                        "role": "assistant",
                        "content": "The json result is ```json"
                    },
                ],
                stop_sequences=["```"],
                temperature=temperature,
            )
            raw_text = completion.text
            try:
                return parse_json_model(raw_text, response_model)
            except StructuredOutputError as exc:
                last_error = exc

        raise last_error or StructuredOutputError("Claude JSON generation failed.")


    def complete_with_tools(
        self,
        *,
        system_prompt: str,
        messages: list[MessageParam],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        max_tool_rounds: int = 5,
        final_prefill: str | None = None,
        stop_sequences: Sequence[str] | None = None,
        temperature: float | None = None,
    ) -> str:
        """Call Claude with tools and loop until it stops requesting tool calls.

        Claude drives when (and whether) to call tools. The tool_executor
        callback resolves each tool_use block; results are fed back as
        tool_result blocks. final_prefill/stop_sequences are applied only on
        the last call (after all tools are done) to force structured output.
        Returns the final plain-text response.
        """

        if self._settings.debug_mode:
            raise RuntimeError(
                "ClaudeClient: debug_mode is enabled — real API calls are blocked."
            )

        request_id = str(uuid4())
        current_messages = list(messages)

        request_temperature = temperature if temperature is not None else self._settings.claude_temperature
        logger.debug("%sclaude system | %s%s", _CYAN, system_prompt, _RESET)

        for round_num in range(max_tool_rounds + 1):
            logger.debug(
                "CLAUDE_API tool_round=%s request_id=%s", round_num, request_id
            )
            for msg in current_messages:
                role = msg.get("role", "?")
                content = msg.get("content", "")
                logger.debug("%sclaude %s | %s%s", _CYAN, role, content, _RESET)

            response = self.client.messages.create(
                model=self._settings.claude_model,
                max_tokens=self._settings.claude_max_tokens,
                temperature=request_temperature,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=tools,  # type: ignore[arg-type]
                messages=current_messages,
            )

            for block in response.content:
                if getattr(block, "type", None) == "text":
                    logger.debug("%sclaude assistant | %s%s", _MAGENTA, block.text, _RESET)
                elif getattr(block, "type", None) == "tool_use":
                    logger.debug(
                        "%sclaude tool_use | %s(%s)%s",
                        _MAGENTA, block.name, json.dumps(dict(block.input)), _RESET,
                    )

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            if not tool_use_blocks:
                if final_prefill is None:
                    text_parts = [
                        b.text for b in response.content if getattr(b, "type", None) == "text"
                    ]
                    result_text = "".join(text_parts)
                    logger.debug("%sclaude response | %s%s", _MAGENTA, result_text, _RESET)
                    logger.debug(
                        "CLAUDE_API tool_loop_done request_id=%s rounds=%s", request_id, round_num
                    )
                    return result_text

                # Apply prefill on a dedicated final call to get structured output.
                current_messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]
                current_messages.append({"role": "user", "content": "Now output the JSON result."})
                current_messages.append({"role": "assistant", "content": final_prefill})
                logger.debug("%sclaude assistant | %s%s", _CYAN, final_prefill, _RESET)
                final_response = self.client.messages.create(
                    model=self._settings.claude_model,
                    max_tokens=self._settings.claude_max_tokens,
                    temperature=self._settings.claude_temperature,
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=current_messages,
                    stop_sequences=list(stop_sequences) if stop_sequences else None,
                )
                text_parts = [
                    b.text for b in final_response.content if getattr(b, "type", None) == "text"
                ]
                result_text = "".join(text_parts)
                logger.debug("%sclaude response | %s%s", _MAGENTA, result_text, _RESET)
                logger.debug(
                    "CLAUDE_API tool_loop_done request_id=%s rounds=%s", request_id, round_num
                )
                return result_text

            current_messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]

            tool_results = []
            for block in tool_use_blocks:
                logger.debug(
                    "CLAUDE_API tool_call request_id=%s tool=%s input=%s",
                    request_id, block.name, block.input,
                )
                try:
                    tool_output = tool_executor(block.name, dict(block.input))
                    logger.debug(
                        "%sclaude tool_result | %s → %s%s",
                        _CYAN, block.name, json.dumps(tool_output), _RESET,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_output),
                    })
                except Exception as exc:
                    logger.warning("CLAUDE_API tool_error tool=%s error=%s", block.name, exc)
                    logger.debug(
                        "%sclaude tool_result | %s → ERROR: %s%s",
                        _CYAN, block.name, exc, _RESET,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": f"Tool error: {exc}",
                        "is_error": True,
                    })

            current_messages.append({"role": "user", "content": tool_results})

        raise RuntimeError(f"Tool loop exceeded max_tool_rounds={max_tool_rounds}")


def get_claude_client() -> ClaudeClient:
    """Dependency factory for FastAPI and agents."""

    return ClaudeClient()
