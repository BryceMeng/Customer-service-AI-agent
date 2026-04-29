"""FastAPI entrypoint for the Support Agent service."""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.log_context import CaseIdFilter

LOG_FORMAT = "%(levelname)s  %(module)-20s  [%(case_id)s]  %(message)s"
ANSI_RESET = "\033[0m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"


class AnthropicHighlightFormatter(logging.Formatter):
    """Highlight Claude-backed success and failure rows for terminal logs."""

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        status = getattr(record, "anthropic_api_status", None)
        if status == "ok":
            return f"{ANSI_GREEN}{message}{ANSI_RESET}"
        if status == "failed":
            return f"{ANSI_YELLOW}{message}{ANSI_RESET}"
        return message


def _handler_has_case_id_filter(handler: logging.Handler) -> bool:
    return any(isinstance(filter_, CaseIdFilter) for filter_ in handler.filters)


def configure_logging(settings: "Settings") -> None:
    root_logger = logging.getLogger()

    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    if not root_logger.handlers:
        logging.basicConfig(level=log_level, format=LOG_FORMAT)
    else:
        root_logger.setLevel(log_level)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)
    logging.getLogger("_trace").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream in {sys.stderr, sys.stdout}:
            handler.setFormatter(AnthropicHighlightFormatter(LOG_FORMAT))
        if not _handler_has_case_id_filter(handler):
            handler.addFilter(CaseIdFilter())

from app.cache.state_store import StateStore
from app.config import Settings, get_settings
from app.fixtures import DEMO_CASES, get_demo_case
from app.orchestration.state_machine import SupportCoordinator
from app.schemas.case import AgentRunOutput, FixtureSummary, RunCaseRequest


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(resolved_settings)
        yield

    api = FastAPI(
        title="Support Agent API",
        version="0.1.0",
        description="v1 Support Agent system powered by Claude API.",
        lifespan=lifespan,
    )

    @api.get("/")
    def service_info() -> dict[str, str]:
        return {
            "name": "Support Agent API",
            "version": "0.1.0",
            "environment": resolved_settings.app_env,
        }

    @api.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "environment": resolved_settings.app_env,
        }

    @api.post("/cases/run")
    def run_case(request: RunCaseRequest) -> AgentRunOutput:
        """Run one support case through the local support-agent flow."""

        output = SupportCoordinator(resolved_settings).run(request)
        StateStore(resolved_settings.state_db_path).save_completed_run(output)
        return output

    @api.get("/cases/fixtures")
    def list_fixtures() -> list[FixtureSummary]:
        """List built-in demo fixtures that can be run from the API docs."""

        summaries: list[FixtureSummary] = []
        for fixture_id, fixture in DEMO_CASES.items():
            expected = fixture.expected
            summaries.append(
                FixtureSummary(
                    fixture_id=fixture_id,
                    case_id=fixture.case_id,
                    user_message=fixture.user_message,
                    expected_intent=expected.intent if expected else None,
                    expected_final_action=expected.final_action if expected else None,
                    expected_escalate=expected.escalate if expected else None,
                )
            )
        return summaries

    @api.post("/cases/run-fixture/{fixture_id}")
    def run_fixture(fixture_id: str) -> AgentRunOutput:
        """Run a built-in demo fixture without requiring a JSON body."""

        try:
            fixture = get_demo_case(fixture_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown fixture: {fixture_id}") from exc

        output = SupportCoordinator(resolved_settings).run(
            RunCaseRequest(
                case_id=fixture.case_id,
                user_message=fixture.user_message,
                context=fixture.context,
                mock_backend_state=fixture.mock_backend_state,
            )
        )
        StateStore(resolved_settings.state_db_path).save_completed_run(output)
        return output

    @api.get("/cases/{case_id}")
    def get_case_run(case_id: str) -> AgentRunOutput:
        """Return a previously completed case run."""

        payload = StateStore(resolved_settings.state_db_path).load_run(case_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Case run not found: {case_id}")
        return AgentRunOutput.model_validate(payload)

    return api


app = create_app()
