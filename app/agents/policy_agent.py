"""Policy grounding helpers."""

import logging

from app.config import Settings, get_settings
from app.llm.claude_client import ClaudeClient
from app.mcp_client import McpToolClient
from app.schemas.case import FinalAction, Intent, PolicyGroundingOutput, PolicyRefundDecision, ToolCallRecord

logger = logging.getLogger(__name__)


def ground_policy(
    intent: Intent,
    final_action: FinalAction,
    tool_records: list[ToolCallRecord] | None = None,
    settings: Settings | None = None,
) -> PolicyGroundingOutput:
    resolved = settings or get_settings()
    client = McpToolClient()
    result = client.call("knowledge", "policy_refs", {"intent": intent.value})
    refs = result.get("refs", [])
    logger.info("MCP:tool  knowledge.policy_refs  {'intent': '%s'}  result: refs=%s", intent.value, refs)
    policy_docs = {}
    for ref in refs:
        doc = client.call("knowledge", "fetch_policy_doc", {"policy_id": ref})
        text = doc.get("text", "")
        logger.info("MCP:tool  knowledge.fetch_policy_doc  {'policy_id': '%s'}  result: %d chars", ref, len(text))
        policy_docs[ref] = text
    fallback = PolicyGroundingOutput(
        explanation=_fallback_explanation(refs, policy_docs, final_action),
        refs=refs,
    )

    if resolved.has_claude_credentials and not resolved.debug_mode:
        try:
            grounding = ClaudeClient(resolved).generate_json(
                prompt_name="policy_grounding_prompt",
                variables={
                    "intent": intent.value,
                    "final_action": final_action.value,
                    "refs": refs,
                    "policy_docs": policy_docs,
                    "tool_evidence": _summarize_tool_records(tool_records or []),
                },
                response_model=PolicyGroundingOutput,
                temperature=0.1,
            )
            grounded_refs = [ref for ref in grounding.refs if ref in policy_docs] or refs
            explanation = grounding.explanation.strip() or fallback.explanation
            logger.info(
                "AGENT:policy  source=claude  intent=%s  refs=%s",
                intent.value,
                grounded_refs,
                extra={"anthropic_api_status": "ok"},
            )
            return PolicyGroundingOutput(explanation=explanation, refs=grounded_refs)
        except Exception as exc:
            logger.warning(
                "AGENT:policy  source=claude  status=failed  intent=%s  refs=%s  error=%s  falling back to rules",
                intent.value,
                refs,
                exc,
                extra={"anthropic_api_status": "failed"},
            )
            logger.info("AGENT:policy  source=rules  intent=%s  refs=%s", intent.value, refs)
    else:
        logger.info("AGENT:policy  source=rules  refs=%s", refs)

    return fallback


def policy_guided_refund_decision(
    order: dict | None,
    policy_docs: dict[str, str],
    similar_cases: list[dict] | None = None,
    settings: Settings | None = None,
) -> FinalAction:
    resolved = settings or get_settings()

    if order is None:
        logger.info("AGENT:policy_refund  source=rules  order_found=False  action=deny_with_explanation")
        return FinalAction.DENY_WITH_EXPLANATION

    days = order.get("days_since_purchase")
    refundable = bool(order.get("refundable", False))
    status = order.get("status", "paid")
    within_window = (days is None) or (days <= 30)
    if within_window and refundable and status != "paid":
        fallback_action = FinalAction.ESCALATE
    elif within_window and refundable:
        fallback_action = FinalAction.PROCESS_REFUND
    else:
        fallback_action = FinalAction.DENY_WITH_EXPLANATION

    if not (resolved.has_claude_credentials and not resolved.debug_mode):
        logger.info(
            "AGENT:policy_refund  source=rules  days=%s  refundable=%s  action=%s",
            days, refundable, fallback_action.value,
        )
        return fallback_action

    try:
        policy_text = "\n\n".join(f"[{ref}]\n{text}" for ref, text in policy_docs.items())
        decision = ClaudeClient(resolved).generate_json(
            prompt_name="refund_policy_decision_prompt",
            cached_variables={"policy_text": policy_text},
            variables={
                "order": order,
                "similar_cases": similar_cases or [],
            },
            response_model=PolicyRefundDecision,
            temperature=0.1,
        )
        logger.info(
            "AGENT:policy_refund  source=claude  action=%s  reason=%r",
            decision.recommended_action.value,
            decision.reason,
            extra={"anthropic_api_status": "ok"},
        )
        return decision.recommended_action
    except Exception as exc:
        logger.warning(
            "AGENT:policy_refund  source=claude  status=failed  error=%s  falling back to rules",
            exc,
            extra={"anthropic_api_status": "failed"},
        )
        logger.info(
            "AGENT:policy_refund  source=rules  days=%s  refundable=%s  action=%s",
            days, refundable, fallback_action.value,
        )
        return fallback_action


def _fallback_explanation(
    refs: list[str],
    policy_docs: dict[str, str],
    final_action: FinalAction,
) -> str:
    if not refs:
        return f"No specific policy references were found for action {final_action.value}."

    doc_summaries = " ".join(policy_docs[ref] for ref in refs if policy_docs.get(ref)).strip()
    if doc_summaries:
        return (
            f"The action {final_action.value} is grounded in {', '.join(refs)}. "
            f"{doc_summaries}"
        )
    return f"The action {final_action.value} is grounded in {', '.join(refs)}."


_FULL_RESULT_TOOLS = {"lookup_order"}


def _summarize_tool_records(tool_records: list[ToolCallRecord]) -> list[dict[str, object]]:
    summarized: list[dict[str, object]] = []
    for record in tool_records:
        summary: dict[str, object] = {"tool_name": record.tool_name}
        if record.arguments:
            summary["arguments"] = record.arguments
        if record.result:
            if record.tool_name in _FULL_RESULT_TOOLS:
                summary["result"] = record.result
            else:
                summary["result_keys"] = sorted(record.result.keys())
        summarized.append(summary)
    return summarized
