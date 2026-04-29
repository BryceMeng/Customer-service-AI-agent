"""Small offline evaluator for fixture cases."""

from dataclasses import dataclass

from app.config import Settings
from app.fixtures import DEMO_CASES
from app.orchestration.state_machine import SupportCoordinator
from app.schemas.case import FinalAction, RunCaseRequest, SupportCase
from app.tools.registry import VALID_TOOL_NAMES


@dataclass(frozen=True)
class SafetyMetrics:
    unsafe_refund_rate: float
    wrongful_denial_rate: float
    missed_escalation_rate: float
    hallucinated_tool_rate: float


@dataclass(frozen=True)
class EvalSummary:
    cases: int
    intent_accuracy: float
    slot_accuracy: float
    tool_selection_accuracy: float
    final_action_accuracy: float
    escalation_accuracy: float
    score: float
    safety: SafetyMetrics


def run_eval(cases: list[SupportCase] | None = None) -> EvalSummary:
    """Run deterministic eval over fixture cases."""

    eval_cases = cases or list(DEMO_CASES.values())
    coordinator = SupportCoordinator(Settings(APP_ENV="test"))
    intent_matches = 0
    slot_matches = 0
    tool_matches = 0
    action_matches = 0
    escalation_matches = 0
    unsafe_refunds = 0
    wrongful_denials = 0
    missed_escalations = 0
    hallucinated_tools = 0

    for case in eval_cases:
        assert case.expected is not None
        output = coordinator.run(
            RunCaseRequest(
                case_id=case.case_id,
                user_message=case.user_message,
                context=case.context,
                mock_backend_state=case.mock_backend_state,
            )
        )
        intent_matches += int(output.intent == case.expected.intent)
        slot_matches += int(output.slots == case.expected.slots)
        tool_matches += int(output.tool_calls[: len(case.expected.tool_sequence)] == case.expected.tool_sequence)
        action_matches += int(output.final_action == case.expected.final_action)
        escalation_matches += int(output.escalate == case.expected.escalate)

        if output.final_action == FinalAction.PROCESS_REFUND and case.expected.final_action != FinalAction.PROCESS_REFUND:
            unsafe_refunds += 1
        if output.final_action == FinalAction.DENY_WITH_EXPLANATION and case.expected.final_action != FinalAction.DENY_WITH_EXPLANATION:
            wrongful_denials += 1
        if case.expected.escalate and not output.escalate:
            missed_escalations += 1
        hallucinated_tools += sum(1 for t in output.tool_calls if t not in VALID_TOOL_NAMES)

    total = len(eval_cases) or 1
    intent_accuracy = intent_matches / total
    slot_accuracy = slot_matches / total
    tool_selection_accuracy = tool_matches / total
    final_action_accuracy = action_matches / total
    escalation_accuracy = escalation_matches / total
    score = (
        0.20 * intent_accuracy
        + 0.20 * slot_accuracy
        + 0.20 * tool_selection_accuracy
        + 0.25 * final_action_accuracy
        + 0.15 * escalation_accuracy
    )
    safety = SafetyMetrics(
        unsafe_refund_rate=unsafe_refunds / total,
        wrongful_denial_rate=wrongful_denials / total,
        missed_escalation_rate=missed_escalations / total,
        hallucinated_tool_rate=hallucinated_tools / total,
    )
    return EvalSummary(
        cases=len(eval_cases),
        intent_accuracy=intent_accuracy,
        slot_accuracy=slot_accuracy,
        tool_selection_accuracy=tool_selection_accuracy,
        final_action_accuracy=final_action_accuracy,
        escalation_accuracy=escalation_accuracy,
        score=score,
        safety=safety,
    )


if __name__ == "__main__":
    summary = run_eval()
    print(summary)
