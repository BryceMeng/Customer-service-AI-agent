import logging

from app.main import ANSI_GREEN, ANSI_RESET, ANSI_YELLOW, AnthropicHighlightFormatter


def test_formatter_colors_success_rows_green() -> None:
    formatter = AnthropicHighlightFormatter("%(levelname)s  %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="AGENT:intake  parser=claude",
        args=(),
        exc_info=None,
    )
    record.case_id = "case_123"
    record.anthropic_api_status = "ok"

    rendered = formatter.format(record)

    assert rendered.startswith(ANSI_GREEN)
    assert rendered.endswith(ANSI_RESET)


def test_formatter_colors_failure_rows_yellow() -> None:
    formatter = AnthropicHighlightFormatter("%(levelname)s  %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="AGENT:policy  source=claude  status=failed",
        args=(),
        exc_info=None,
    )
    record.case_id = "case_123"
    record.anthropic_api_status = "failed"

    rendered = formatter.format(record)

    assert rendered.startswith(ANSI_YELLOW)
    assert rendered.endswith(ANSI_RESET)
