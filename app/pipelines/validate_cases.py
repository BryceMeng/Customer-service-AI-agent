"""Strict validation for support-agent eval cases."""

from collections.abc import Iterable

from app.schemas.case import FinalAction, Intent, SupportCase
from app.tools.registry import VALID_TOOL_NAMES


def validate_cases(cases: Iterable[SupportCase]) -> list[str]:
    """Return validation errors for a sequence of cases."""

    errors: list[str] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if case.case_id in seen_case_ids:
            errors.append(f"{case.case_id}: duplicate case_id")
        seen_case_ids.add(case.case_id)

        if case.expected is None:
            errors.append(f"{case.case_id}: missing expected output")
            continue

        if not isinstance(case.expected.intent, Intent):
            errors.append(f"{case.case_id}: invalid intent")
        if not isinstance(case.expected.final_action, FinalAction):
            errors.append(f"{case.case_id}: invalid final_action")
        if not isinstance(case.expected.escalate, bool):
            errors.append(f"{case.case_id}: escalate must be boolean")

        invalid_tools = [
            tool for tool in case.expected.tool_sequence if tool not in VALID_TOOL_NAMES
        ]
        for tool in invalid_tools:
            errors.append(f"{case.case_id}: unknown tool {tool}")

        if case.expected.intent == Intent.DUPLICATE_CHARGE and len(case.mock_backend_state.payments) < 2:
            errors.append(f"{case.case_id}: duplicate_charge requires at least two payments")

        if case.expected.final_action == FinalAction.PROCESS_REFUND:
            if case.mock_backend_state.order is None or not case.mock_backend_state.payments:
                errors.append(f"{case.case_id}: process_refund requires order/payment evidence")

    return errors

