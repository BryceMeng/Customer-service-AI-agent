"""Static policy lookup tools for v1."""

from app.schemas.case import FinalAction, Intent
from app.config import get_settings
from app.cache.state_store import StateStore

POLICY_BY_INTENT: dict[Intent, list[str]] = {
    Intent.DUPLICATE_CHARGE: ["refund_policy.duplicate_charge"],
    Intent.REFUND_REQUEST: ["refund_policy.standard"],
    Intent.ACCOUNT_LOCKED: ["account_security.high_risk_unlock"],
    Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING: ["sla_policy.incident_response"],
    Intent.BILLING_DISPUTE: ["billing_policy.dispute_review"],
    Intent.AMBIGUOUS_REQUEST: ["support_policy.clarify_before_action"],
    Intent.SUSPECTED_INCIDENT: ["sla_policy.incident_response"],
}


def search_policy_docs(query: str, locale: str = "en-US") -> dict:
    """Return local policy references matching the query."""

    normalized_query = query.lower()
    refs = [
        ref
        for intent, refs_for_intent in POLICY_BY_INTENT.items()
        for ref in refs_for_intent
        if intent.value in normalized_query or intent.value.replace("_", " ") in normalized_query
    ]
    return {"locale": locale, "refs": refs or ["support_policy.general"]}


def policy_refs_for_intent(intent: Intent) -> list[str]:
    """Return static policy references for an intent."""

    return POLICY_BY_INTENT[intent]


POLICY_DOCS: dict[str, str] = {
    "refund_policy.duplicate_charge": (
        "Customers charged more than once for the same order are entitled to a full refund "
        "of the duplicate amount within 30 days of the original charge."
    ),
    "refund_policy.standard": (
        "Refund Policy — Standard Window\n"
        "\n"
        "Eligibility:\n"
        "  - Refund requests must be submitted within 30 days of the purchase date.\n"
        "  - The order must have a status of 'paid'. Orders with status 'shipped' or 'pending' "
        "require human review before a refund can be issued.\n"
        "  - The order must be marked refundable. Non-refundable orders (e.g. digital downloads, "
        "custom items) are not eligible under this policy.\n"
        "\n"
        "Approval:\n"
        "  - Refunds up to $100 are approved automatically by the system.\n"
        "  - Refunds above $100 require escalation to a human agent for manual approval.\n"
        "\n"
        "Outside the window:\n"
        "  - Requests submitted more than 30 days after purchase are denied under standard policy. "
        "Exceptions may be granted by a supervisor for documented service failures or extenuating "
        "circumstances, but require manual escalation.\n"
        "\n"
        "Process:\n"
        "  - Approved refunds are returned to the original payment method within 5–10 business days.\n"
        "  - Each refund requires a unique idempotency key to prevent duplicate processing."
    ),
    "sla_policy.incident_response": (
        "Active service incidents are routed to engineering within 1 hour. "
        "Affected customers receive a status update within 2 hours of the incident being confirmed."
    ),
    "account_security.high_risk_unlock": (
        "High-risk locked accounts require manual review by the trust and safety team before being unlocked. "
        "Automated unlocking is not permitted for accounts flagged as high-risk."
    ),
    "billing_policy.dispute_review": (
        "Billing disputes are reviewed within 5 business days. "
        "Customers should provide transaction details and a brief description of the issue."
    ),
    "support_policy.clarify_before_action": (
        "Agents must gather sufficient information before taking any action on ambiguous requests. "
        "Do not execute write operations without confirmed intent and supporting evidence."
    ),
}

SIMILAR_CASES: dict[str, list[dict]] = {
    "duplicate_charge": [
        {
            "summary": "Customer charged twice for the same order in a 2-minute window.",
            "tool_sequence": ["get_customer", "lookup_order", "get_payment_events"],
            "evidence": "Two payment events found with identical amounts 2 minutes apart; order confirmed valid.",
            "final_action": "process_refund",
            "response": "We found a duplicate charge on your account and have issued a full refund for the extra payment. It should appear within 3–5 business days.",
        },
        {
            "summary": "Double charge on subscription renewal; customer noticed on bank statement.",
            "tool_sequence": ["get_customer", "lookup_order", "get_payment_events"],
            "evidence": "Two successful payment events for the same subscription renewal; governance approved refund.",
            "final_action": "process_refund",
            "response": "We confirmed the duplicate charge on your subscription renewal and have processed a refund for the second payment.",
        },
        {
            "summary": "Customer claimed duplicate charge but backend showed only one payment.",
            "tool_sequence": ["get_customer", "lookup_order", "get_payment_events"],
            "evidence": "Only one payment event found for the order; no duplicate detected.",
            "final_action": "deny_with_explanation",
            "response": "After reviewing your account we found only one charge for this order. If you are seeing a pending transaction it may be a temporary authorization that will drop off automatically.",
        },
    ],
    "account_locked": [
        {
            "summary": "High-risk account locked after multiple failed login attempts.",
            "tool_sequence": ["get_customer", "request_account_unlock_approval", "escalate_to_human"],
            "evidence": "Customer risk_level=high; account locked after 10 failed attempts in 5 minutes.",
            "final_action": "escalate",
            "response": "Your account has been flagged for a manual security review. Our trust and safety team will contact you within 24 hours to verify your identity and restore access.",
        },
        {
            "summary": "Account locked due to suspicious activity from an unrecognized location.",
            "tool_sequence": ["get_customer", "request_account_unlock_approval", "escalate_to_human"],
            "evidence": "Login attempt from a new country; risk signals present; automated unlock not permitted.",
            "final_action": "escalate",
            "response": "We have placed a security hold on your account due to unusual activity. A member of our team will reach out to complete verification before restoring access.",
        },
        {
            "summary": "Account locked but no risk signals present; customer forgot password.",
            "tool_sequence": ["get_customer"],
            "evidence": "Account status=locked but risk_level=normal; likely a routine lockout.",
            "final_action": "ask_clarifying_question",
            "response": "It looks like your account may have been locked after too many password attempts. Can you confirm whether you recently tried to reset your password so we can point you to the right recovery steps?",
        },
    ],
    "subscription_active_but_service_failing": [
        {
            "summary": "Active API subscription returning 500 errors; open incident confirmed.",
            "tool_sequence": ["get_subscription", "search_incidents", "get_recent_deployments"],
            "evidence": "Subscription status=active; open major incident on API service; recent deployment 2 hours prior.",
            "final_action": "explain_incident_and_route",
            "response": "We are aware of an active issue affecting the API and our engineering team is working on it. Your subscription is in good standing and you will not be charged for downtime. We will send a status update once resolved.",
        },
        {
            "summary": "Service degradation after a deployment rollback; customer seeing intermittent failures.",
            "tool_sequence": ["get_subscription", "search_incidents", "get_recent_deployments"],
            "evidence": "Incident status=investigating; deployment rolled back 30 minutes ago; error rate elevated.",
            "final_action": "explain_incident_and_route",
            "response": "We identified a service degradation tied to a recent deployment. Our team has rolled back the change and is monitoring recovery. We appreciate your patience.",
        },
        {
            "summary": "Customer reporting failures but no active incident found in observability.",
            "tool_sequence": ["get_subscription", "search_incidents", "get_recent_deployments"],
            "evidence": "No open incidents; subscription active; metrics nominal. Issue may be customer-side.",
            "final_action": "escalate",
            "response": "We do not see any active incidents on our end right now. I am escalating your case to our support engineers to investigate further and they will follow up with you shortly.",
        },
    ],
    "refund_request": [
        {
            "summary": "Customer requested refund within 30-day window but no qualifying reason found.",
            "tool_sequence": ["lookup_order"],
            "evidence": "Order placed 12 days ago; refundable=false; no duplicate or service failure detected.",
            "final_action": "deny_with_explanation",
            "response": "After reviewing your order we are unable to process a refund as it does not meet our standard refund criteria. If you believe this is an error please reply with more details and we will take another look.",
        },
        {
            "summary": "Refund request submitted 45 days after purchase; outside policy window.",
            "tool_sequence": ["lookup_order"],
            "evidence": "Order placed 45 days ago; refund window is 30 days; request is out of window.",
            "final_action": "deny_with_explanation",
            "response": "Unfortunately your request falls outside our 30-day refund window and we are unable to process it. If there are exceptional circumstances please let us know and we will review your case.",
        },
    ],
    "billing_dispute": [
        {
            "summary": "Customer disputed an unrecognized charge; turned out to be an annual renewal.",
            "tool_sequence": [],
            "evidence": "Insufficient detail to look up order; clarifying question needed first.",
            "final_action": "ask_clarifying_question",
            "response": "We would like to help resolve this billing concern. Could you share the approximate charge amount and the date it appeared so we can locate the transaction?",
        },
    ],
}


def fetch_policy(policy_id: str) -> dict:
    """Return the full text of a policy by its ID."""

    text = POLICY_DOCS.get(policy_id, "Policy document not found for the given ID.")
    return {"policy_id": policy_id, "text": text}


def retrieve_similar_cases(issue_type: str, context: str = "") -> dict:
    """Return the top 2 similar past cases from history, falling back to static examples."""

    try:
        store = StateStore(get_settings().state_db_path)
        cases = store.query_similar_by_intent(issue_type, limit=2)
    except Exception:
        cases = []

    if len(cases) < 2:
        fallback = SIMILAR_CASES.get(issue_type, [])
        cases = (cases + fallback)[:2]

    return {"issue_type": issue_type, "context": context, "similar_cases": cases}


def action_explanation(final_action: FinalAction) -> str:
    """Return a stable explanation for the final action."""

    return {
        FinalAction.PROCESS_REFUND: "A duplicate successful payment was found, so a refund was issued for one charge.",
        FinalAction.DENY_WITH_EXPLANATION: "The available evidence does not meet the refund policy.",
        FinalAction.EXPLAIN_INCIDENT_AND_ROUTE: "An active service incident explains the failure, so the case was routed for engineering follow-up.",
        FinalAction.ESCALATE: "The request requires human review before any high-risk action can be taken.",
        FinalAction.ASK_CLARIFYING_QUESTION: "More information is needed before a safe decision can be made.",
        FinalAction.NO_ACTION: "No eligible action was found from the available evidence.",
    }[final_action]

