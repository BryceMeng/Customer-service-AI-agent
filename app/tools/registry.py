"""Tool registry used by validation and hallucination checks."""

VALID_TOOL_NAMES = {
    "get_customer",
    "lookup_order",
    "get_subscription",
    "get_payment_events",
    "refund_idempotency_key",
    "process_refund",
    "escalate_to_human",
    "search_policy",
    "search_incidents",
    "get_recent_deployments",
    "request_refund_approval",
    "request_account_unlock_approval",
    "create_audit_record",
    "policy_refs",
    "explain_action",
    "fetch_policy_doc",
    "retrieve_similar",
    "query_metrics",
    "query_logs",
}

