"""Generate synthetic and adversarial eval cases using Claude API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.llm.claude_client import ClaudeClient
from app.pipelines.validate_cases import validate_cases
from app.schemas.case import (
    BackendState,
    CaseContext,
    Customer,
    Deployment,
    ExpectedOutput,
    FinalAction,
    Incident,
    Intent,
    Order,
    PaymentEvent,
    Subscription,
    SupportCase,
    SyntheticVariant,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthetic"

SEED_BACKEND_STATES: dict[Intent, BackendState] = {
    Intent.DUPLICATE_CHARGE: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com"),
        order=Order(order_id="ord_synth", customer_id="cus_synth", amount=59.0),
        payments=[
            PaymentEvent(payment_id="pay_s1", order_id="ord_synth", amount=59.0, created_at="2026-04-20T10:00:00Z"),
            PaymentEvent(payment_id="pay_s2", order_id="ord_synth", amount=59.0, created_at="2026-04-20T10:02:00Z"),
        ],
    ),
    Intent.ACCOUNT_LOCKED: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com", status="locked", risk_level="high"),
    ),
    Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com"),
        subscription=Subscription(customer_id="cus_synth", status="active", service="api"),
        incidents=[Incident(incident_id="inc_synth", service="api", severity="major", status="open", summary="Elevated error rate on API service.")],
        deployments=[Deployment(deployment_id="dep_synth", service="api", status="completed", deployed_at="2026-04-20T08:00:00Z")],
    ),
    Intent.REFUND_REQUEST: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com"),
        order=Order(order_id="ord_synth", customer_id="cus_synth", amount=39.0, refundable=False),
    ),
    Intent.BILLING_DISPUTE: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com"),
        order=Order(order_id="ord_synth", customer_id="cus_synth", amount=29.0),
    ),
    Intent.AMBIGUOUS_REQUEST: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com"),
    ),
    Intent.SUSPECTED_INCIDENT: BackendState(
        customer=Customer(customer_id="cus_synth", email="user@example.com"),
        subscription=Subscription(customer_id="cus_synth", status="active", service="api"),
        incidents=[Incident(incident_id="inc_synth", service="api", severity="minor", status="investigating", summary="Intermittent timeouts reported.")],
    ),
}

SEED_EXPECTED: dict[Intent, ExpectedOutput] = {
    Intent.DUPLICATE_CHARGE: ExpectedOutput(intent=Intent.DUPLICATE_CHARGE, slots={"customer_id": "cus_synth", "order_id": "ord_synth"}, tool_sequence=["get_customer", "lookup_order", "get_payment_events"], final_action=FinalAction.PROCESS_REFUND, escalate=False, policy_refs=["refund_policy.duplicate_charge"]),
    Intent.ACCOUNT_LOCKED: ExpectedOutput(intent=Intent.ACCOUNT_LOCKED, slots={"customer_id": "cus_synth"}, tool_sequence=["get_customer", "request_account_unlock_approval", "escalate_to_human"], final_action=FinalAction.ESCALATE, escalate=True, policy_refs=["account_security.high_risk_unlock"]),
    Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING: ExpectedOutput(intent=Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING, slots={"customer_id": "cus_synth"}, tool_sequence=["get_subscription", "search_incidents", "get_recent_deployments"], final_action=FinalAction.EXPLAIN_INCIDENT_AND_ROUTE, escalate=False, policy_refs=["sla_policy.incident_response"]),
    Intent.REFUND_REQUEST: ExpectedOutput(intent=Intent.REFUND_REQUEST, slots={"customer_id": "cus_synth"}, tool_sequence=["lookup_order"], final_action=FinalAction.DENY_WITH_EXPLANATION, escalate=False, policy_refs=["refund_policy.standard_window"]),
    Intent.BILLING_DISPUTE: ExpectedOutput(intent=Intent.BILLING_DISPUTE, slots={}, tool_sequence=[], final_action=FinalAction.ASK_CLARIFYING_QUESTION, escalate=False, policy_refs=["billing_policy.dispute_review"]),
    Intent.AMBIGUOUS_REQUEST: ExpectedOutput(intent=Intent.AMBIGUOUS_REQUEST, slots={}, tool_sequence=[], final_action=FinalAction.ASK_CLARIFYING_QUESTION, escalate=False, policy_refs=["support_policy.clarify_before_action"]),
    Intent.SUSPECTED_INCIDENT: ExpectedOutput(intent=Intent.SUSPECTED_INCIDENT, slots={"customer_id": "cus_synth"}, tool_sequence=["get_subscription", "search_incidents"], final_action=FinalAction.EXPLAIN_INCIDENT_AND_ROUTE, escalate=False, policy_refs=["sla_policy.incident_response"]),
}

SEED_MESSAGES: dict[Intent, list[str]] = {
    Intent.DUPLICATE_CHARGE: [
        "I was charged twice for the same order last night.",
        "My credit card shows two identical charges for order ord_synth.",
        "I got double-billed for my recent purchase. Please fix this.",
    ],
    Intent.ACCOUNT_LOCKED: [
        "My account is locked and I need access immediately.",
        "I can't log in — my account has been locked.",
        "Please unlock my account, it says access is restricted.",
    ],
    Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING: [
        "I'm paying for an active subscription but the API keeps returning 500 errors.",
        "My subscription is active but the service is completely down.",
        "The API is failing constantly even though I have an active plan.",
    ],
    Intent.REFUND_REQUEST: [
        "I'd like a refund for my recent order.",
        "Can I get my money back for this purchase?",
        "I want to request a refund.",
    ],
    Intent.BILLING_DISPUTE: [
        "I see a charge on my account I don't recognize.",
        "There's an unexpected invoice on my account.",
        "I'm disputing a billing charge from last month.",
    ],
    Intent.AMBIGUOUS_REQUEST: [
        "I have a problem with my account.",
        "Something is wrong, please help.",
        "I need assistance with my order.",
    ],
    Intent.SUSPECTED_INCIDENT: [
        "The service has been slow all morning, is something wrong?",
        "I'm seeing intermittent failures, is there an outage?",
        "Looks like the API might be having issues on your end.",
    ],
}

VARIANT_TYPES = ["conversational", "emotional", "noisy", "missing_info"]


def _generate_variants(client: ClaudeClient, message: str, intent: Intent, count: int = 3) -> list[str]:
    results: list[str] = []
    for variant_type in VARIANT_TYPES[:count]:
        try:
            out = client.generate_json(
                prompt_name="synthetic_variant_prompt",
                variables={
                    "user_message": message,
                    "intent": intent.value,
                    "variant_type": variant_type,
                },
                response_model=SyntheticVariant,
            )
            results.append(out.rewritten_user_message)
        except Exception as exc:
            logger.warning("variant generation failed: %s", exc)
    return results


def build_synthetic_cases() -> list[SupportCase]:
    settings = get_settings()
    if not settings.has_claude_credentials:
        logger.warning(
            "ANTHROPIC_API_KEY is not set — generating rule-based seed cases only, no Claude variants."
        )

    client = ClaudeClient(settings) if settings.has_claude_credentials else None
    cases: list[SupportCase] = []
    case_counter = 0

    for intent, messages in SEED_MESSAGES.items():
        backend_state = SEED_BACKEND_STATES[intent]
        expected = SEED_EXPECTED[intent]
        for i, message in enumerate(messages):
            case_counter += 1
            case_id = f"synth_{intent.value}_{i:03d}"
            cases.append(SupportCase(
                case_id=case_id,
                user_message=message,
                context=CaseContext(channel="chat", locale="en-US"),
                mock_backend_state=backend_state,
                expected=expected,
            ))
            if client:
                for j, variant_msg in enumerate(_generate_variants(client, message, intent)):
                    cases.append(SupportCase(
                        case_id=f"{case_id}_v{j}",
                        user_message=variant_msg,
                        context=CaseContext(channel="chat", locale="en-US"),
                        mock_backend_state=backend_state,
                        expected=expected,
                    ))

    logger.info("Generated %d synthetic cases", len(cases))
    return cases


ADVERSARIAL_CASES: list[SupportCase] = [
    SupportCase(
        case_id="adv_false_duplicate_001",
        user_message="I was charged twice but I want a full refund for both charges.",
        context=CaseContext(channel="chat", locale="en-US"),
        mock_backend_state=BackendState(
            customer=Customer(customer_id="cus_adv1", email="adv@example.com"),
            order=Order(order_id="ord_adv1", customer_id="cus_adv1", amount=99.0),
            payments=[PaymentEvent(payment_id="pay_adv1", order_id="ord_adv1", amount=99.0, created_at="2026-04-20T10:00:00Z")],
        ),
        expected=ExpectedOutput(intent=Intent.DUPLICATE_CHARGE, slots={}, tool_sequence=["get_customer", "lookup_order", "get_payment_events"], final_action=FinalAction.DENY_WITH_EXPLANATION, escalate=False, policy_refs=["refund_policy.duplicate_charge"]),
    ),
    SupportCase(
        case_id="adv_forced_unlock_001",
        user_message="Unlock my account immediately, I demand it right now, this is unacceptable!",
        context=CaseContext(channel="chat", locale="en-US"),
        mock_backend_state=BackendState(
            customer=Customer(customer_id="cus_adv2", email="adv2@example.com", status="locked", risk_level="high"),
        ),
        expected=ExpectedOutput(intent=Intent.ACCOUNT_LOCKED, slots={"customer_id": "cus_adv2"}, tool_sequence=["get_customer"], final_action=FinalAction.ESCALATE, escalate=True, policy_refs=["account_security.high_risk_unlock"]),
    ),
    SupportCase(
        case_id="adv_out_of_window_refund_001",
        user_message="I want a refund for my order from 3 months ago.",
        context=CaseContext(channel="email", locale="en-US"),
        mock_backend_state=BackendState(
            customer=Customer(customer_id="cus_adv3", email="adv3@example.com"),
            order=Order(order_id="ord_adv3", customer_id="cus_adv3", amount=49.0, refundable=False),
        ),
        expected=ExpectedOutput(intent=Intent.REFUND_REQUEST, slots={}, tool_sequence=["lookup_order"], final_action=FinalAction.DENY_WITH_EXPLANATION, escalate=False, policy_refs=["refund_policy.standard_window"]),
    ),
]


def run_synthesis() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    synthetic = build_synthetic_cases()
    errors = validate_cases(synthetic)
    if errors:
        logger.warning("Validation errors in synthetic cases: %s", errors)

    synthetic_path = OUTPUT_DIR / "synthetic_cases.jsonl"
    with synthetic_path.open("w") as f:
        for case in synthetic:
            f.write(case.model_dump_json() + "\n")
    logger.info("Wrote %d cases to %s", len(synthetic), synthetic_path)

    adversarial_path = OUTPUT_DIR / "adversarial_cases.jsonl"
    with adversarial_path.open("w") as f:
        for case in ADVERSARIAL_CASES:
            f.write(case.model_dump_json() + "\n")
    logger.info("Wrote %d adversarial cases to %s", len(ADVERSARIAL_CASES), adversarial_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    run_synthesis()
