"""Hand-authored demo cases for the first closed-loop implementation."""

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
)


DEMO_CASES: dict[str, SupportCase] = {
    "duplicate_charge": SupportCase(
        case_id="demo_duplicate_charge",
        user_message="I got charged twice last night for the same order. Please refund one.",
        context=CaseContext(channel="chat", locale="en-US"),
        mock_backend_state=BackendState(
            customer=Customer(
                customer_id="cus_123",
                email="customer@example.com",
            ),
            order=Order(order_id="ord_123", customer_id="cus_123", amount=49.0),
            subscription=Subscription(customer_id="cus_123", status="active", service="api"),
            payments=[
                PaymentEvent(
                    payment_id="pay_1",
                    order_id="ord_123",
                    amount=49.0,
                    created_at="2026-04-19T21:01:00Z",
                ),
                PaymentEvent(
                    payment_id="pay_2",
                    order_id="ord_123",
                    amount=49.0,
                    created_at="2026-04-19T21:03:00Z",
                ),
            ],
        ),
        expected=ExpectedOutput(
            intent=Intent.DUPLICATE_CHARGE,
            slots={"customer_id": "cus_123", "order_id": "ord_123"},
            tool_sequence=["get_customer", "lookup_order", "get_payment_events"],
            final_action=FinalAction.PROCESS_REFUND,
            escalate=False,
            policy_refs=["refund_policy.duplicate_charge"],
        ),
    ),
    "service_incident": SupportCase(
        case_id="demo_service_incident",
        user_message="My subscription is active but the API keeps returning 500 errors.",
        context=CaseContext(channel="email", locale="en-US"),
        mock_backend_state=BackendState(
            customer=Customer(customer_id="cus_456", email="api-user@example.com"),
            subscription=Subscription(customer_id="cus_456", status="active", service="api"),
            incidents=[
                Incident(
                    incident_id="inc_500",
                    service="api",
                    severity="major",
                    status="open",
                    summary="Elevated 500 responses for API requests.",
                )
            ],
            deployments=[
                Deployment(
                    deployment_id="dep_42",
                    service="api",
                    status="completed",
                    deployed_at="2026-04-19T19:00:00Z",
                )
            ],
        ),
        expected=ExpectedOutput(
            intent=Intent.SUBSCRIPTION_ACTIVE_BUT_SERVICE_FAILING,
            slots={"customer_id": "cus_456"},
            tool_sequence=["get_subscription", "search_incidents", "get_recent_deployments"],
            final_action=FinalAction.EXPLAIN_INCIDENT_AND_ROUTE,
            escalate=False,
            policy_refs=["sla_policy.incident_response"],
        ),
    ),
    "account_locked": SupportCase(
        case_id="demo_account_locked",
        user_message="Unlock my account immediately. I cannot wait and I need access now.",
        context=CaseContext(channel="chat", locale="en-US"),
        mock_backend_state=BackendState(
            customer=Customer(
                customer_id="cus_789",
                email="locked@example.com",
                status="locked",
                risk_level="high",
            )
        ),
        expected=ExpectedOutput(
            intent=Intent.ACCOUNT_LOCKED,
            slots={"customer_id": "cus_789"},
            tool_sequence=["get_customer", "request_account_unlock_approval", "escalate_to_human"],
            final_action=FinalAction.ESCALATE,
            escalate=True,
            policy_refs=["account_security.high_risk_unlock"],
        ),
    ),
}


def get_demo_case(fixture_id: str) -> SupportCase:
    """Return a demo case by fixture id."""

    return DEMO_CASES[fixture_id]

