from app.fixtures import DEMO_CASES
from app.pipelines.run_eval import run_eval
from app.pipelines.validate_cases import validate_cases


def test_demo_cases_validate() -> None:
    assert validate_cases(DEMO_CASES.values()) == []


def test_fixture_eval_scores_all_core_metrics() -> None:
    summary = run_eval()

    assert summary.cases == 3
    assert summary.intent_accuracy == 1
    assert summary.final_action_accuracy == 1
    assert summary.escalation_accuracy == 1
    assert summary.score > 0.75
