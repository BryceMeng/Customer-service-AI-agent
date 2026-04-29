"""Resolution decision helpers."""

import logging

from app.schemas.case import FinalAction

logger = logging.getLogger(__name__)


def refund_action_for_duplicate(*, duplicate_payment_found: bool, refundable: bool) -> FinalAction:
    action = FinalAction.PROCESS_REFUND if duplicate_payment_found and refundable else FinalAction.DENY_WITH_EXPLANATION
    logger.info("AGENT:resolution  duplicate=%s  refundable=%s  action=%s", duplicate_payment_found, refundable, action.value)
    return action


def refund_action_for_request(*, order_found: bool, refundable: bool) -> FinalAction:
    action = FinalAction.PROCESS_REFUND if order_found and refundable else FinalAction.DENY_WITH_EXPLANATION
    logger.info("AGENT:resolution  order_found=%s  refundable=%s  action=%s", order_found, refundable, action.value)
    return action
