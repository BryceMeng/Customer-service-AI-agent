"""Centralized prompt templates for Claude calls."""

PROMPTS: dict[str, str] = {
    "intake_parse_prompt": (
        "You are a support intake classifier. Your job is to understand what a customer needs "
        "and produce a structured IntakeResult.\n\n"
        "After you have gathered enough information (or if none is needed), output ONLY a JSON "
        "block matching the provided schema. Do not explain yourself — just call tools if needed, "
        "then output the JSON."
    ),
    "policy_grounding_prompt": (
        "Given the detected intent, final action, relevant policy documents, and tool evidence, "
        "return JSON that selects the applicable policy refs from the provided refs and explains "
        "why they support the action. Do not invent refs that were not provided."
    ),
    "user_response_prompt": (
        "Write a concise customer-facing response based only on the approved final action. "
        "Use the provided similar past cases as reference for tone and phrasing, but do not "
        "copy them verbatim or reference them explicitly to the customer."
    ),
    "audit_summary_prompt": (
        "Write a concise internal audit summary based only on the provided tool evidence."
    ),
    "seed_case_cleanup_prompt": "Normalize this raw support case into the target case schema.",
    "synthetic_variant_prompt": (
        "Rewrite the case message while preserving the underlying truth and expected action."
    ),
    "refund_policy_decision_prompt": (
        "You are a refund eligibility evaluator. "
        "You will receive an order record, the full text of the applicable refund policy, "
        "and similar past cases for reference. "
        "Based on the order data, the policy, and the patterns in similar cases, "
        "decide whether this refund request should be approved or denied. "
        "Do not invent facts beyond what is provided. "
        "Return JSON with exactly two fields: "
        "\"recommended_action\" (one of: \"process_refund\", \"deny_with_explanation\", \"escalate\") "
        "and \"reason\" (a single sentence explaining your decision citing the policy). "
        "Use escalate when the order status is not 'paid' and the request may be legitimate — "
        "a human agent should review. "
        "If days_since_purchase is null or missing, treat it as within the policy window. "
        "If the order is not found (order is null), always return deny_with_explanation."
    ),
}


def get_prompt(prompt_name: str) -> str:
    """Return a prompt template by name."""

    try:
        return PROMPTS[prompt_name]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt: {prompt_name}") from exc
