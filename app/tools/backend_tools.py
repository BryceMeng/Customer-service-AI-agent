"""Mock backend tools used by the local support-agent flow."""

import random
from hashlib import sha256

from app.schemas.case import BackendState, Order
from app.tools.audit_tools import AuditLog


def _seeded_random(order_id: str) -> random.Random:
    seed = int(sha256(f"42:{order_id}".encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def build_refund_idempotency_key(
    *,
    case_id: str,
    order_id: str,
    amount: float,
    reason: str,
) -> str:
    """Build a deterministic refund idempotency key."""

    raw = f"{case_id}:{order_id}:{amount:.2f}:{reason}"
    return sha256(raw.encode("utf-8")).hexdigest()


class BackendTools:
    """Read/write operations over a case's mock backend state."""

    def __init__(self, state: BackendState, audit_log: AuditLog) -> None:
        self._state = state
        self._audit_log = audit_log

    def get_customer(self, customer_id: str | None = None) -> dict:
        customer = self._state.customer
        if customer_id is not None and customer is not None and customer.customer_id != customer_id:
            return {"customer": None}
        return {"customer": customer.model_dump() if customer else None}

    def lookup_order(self, order_id: str | None = None) -> dict:
        order = self._state.order
        if order_id is not None and order is not None and order.order_id != order_id:
            return {"order": None}
        if order is not None:
            return {"order": order.model_dump()}
        if order_id is None:
            return {"order": None}
        rng = _seeded_random(order_id)
        if rng.random() < 0.15:
            return {"order": None}
        return {
            "order": Order(
                order_id=order_id,
                customer_id=f"cus_{rng.randint(1000, 9999)}",
                amount=round(rng.uniform(5.0, 500.0), 2),
                currency=rng.choice(["USD", "EUR", "GBP"]),
                status=rng.choice(["paid", "pending", "shipped"]),
                refundable=rng.choice([True, False]),
                days_since_purchase=rng.randint(1, 90),
            ).model_dump()
        }

    def get_subscription(self, customer_id: str | None = None) -> dict:
        subscription = self._state.subscription
        if (
            customer_id is not None
            and subscription is not None
            and subscription.customer_id != customer_id
        ):
            return {"subscription": None}
        return {"subscription": subscription.model_dump() if subscription else None}

    def get_payment_events(self, order_id: str | None = None) -> dict:
        payments = self._state.payments
        if order_id is not None:
            payments = [payment for payment in payments if payment.order_id == order_id]
        return {"payments": [payment.model_dump() for payment in payments]}

    def process_refund(
        self,
        *,
        case_id: str,
        order_id: str,
        amount: float,
        reason: str,
        idempotency_key: str,
    ) -> dict:
        expected_key = build_refund_idempotency_key(
            case_id=case_id,
            order_id=order_id,
            amount=amount,
            reason=reason,
        )
        if idempotency_key != expected_key:
            raise ValueError("Invalid refund idempotency key.")

        payload = {
            "order_id": order_id,
            "amount": amount,
            "reason": reason,
            "idempotency_key": idempotency_key,
            "status": "accepted",
        }
        self._audit_log.append(case_id, "process_refund", payload)
        return payload

    def escalate_to_human(self, *, case_id: str, summary: str) -> dict:
        payload = {"summary": summary, "status": "queued"}
        self._audit_log.append(case_id, "escalate_to_human", payload)
        return payload

