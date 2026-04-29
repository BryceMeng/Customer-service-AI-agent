"""Report and response generation."""

import logging

from app.config import Settings, get_settings
from app.llm.claude_client import ClaudeClient
from app.schemas.case import AgentRunOutput, AuditNoteOutput, FinalAction, Intent, UserResponseOutput

logger = logging.getLogger(__name__)


def build_user_response(
    final_action: FinalAction,
    intent: Intent,
    action_explanation: str | None = None,
    policy_explanation: str | None = None,
    settings: Settings | None = None,
    similar_cases: list | None = None,
) -> str:
    logger.info("AGENT:report  building user_response  final_action=%s", final_action.value)
    resolved = settings or get_settings()
    if resolved.has_claude_credentials and not resolved.debug_mode:
        try:
            out = ClaudeClient(resolved).generate_json(
                prompt_name="user_response_prompt",
                variables={
                    "final_action": final_action.value,
                    "intent": intent.value,
                    "action_explanation": action_explanation or "",
                    "policy_explanation": policy_explanation or "",
                    "similar_cases": similar_cases or [],
                },
                response_model=UserResponseOutput,
                temperature=0.3,
            )
            logger.info(
                "AGENT:report  source=claude  target=user_response  final_action=%s",
                final_action.value,
                extra={"anthropic_api_status": "ok"},
            )
            return out.response
        except Exception as exc:
            logger.warning(
                "AGENT:report  source=claude  target=user_response  status=failed  final_action=%s  error=%s  falling back to template",
                final_action.value,
                exc,
                extra={"anthropic_api_status": "failed"},
            )
    return _template_response(final_action, intent, action_explanation)


def build_audit_note(output: AgentRunOutput, settings: Settings | None = None) -> str:
    logger.info("AGENT:report  building audit_note  case_id=%s", output.case_id)
    resolved = settings or get_settings()
    if resolved.has_claude_credentials and not resolved.debug_mode:
        try:
            out = ClaudeClient(resolved).generate_json(
                prompt_name="audit_summary_prompt",
                variables={
                    "case_id": output.case_id,
                    "intent": output.intent.value,
                    "final_action": output.final_action.value,
                    "tool_calls": output.tool_calls,
                    "escalate": output.escalate,
                    "policy_explanation": output.policy_explanation or "",
                    "policy_refs": output.policy_refs,
                },
                response_model=AuditNoteOutput,
                temperature=0.3,
            )
            logger.info(
                "AGENT:report  source=claude  target=audit_note  case_id=%s",
                output.case_id,
                extra={"anthropic_api_status": "ok"},
            )
            return out.audit_note
        except Exception as exc:
            logger.warning(
                "AGENT:report  source=claude  target=audit_note  status=failed  case_id=%s  error=%s  falling back to template",
                output.case_id,
                exc,
                extra={"anthropic_api_status": "failed"},
            )
    return _template_audit_note(output)


def _template_response(
    final_action: FinalAction,
    intent: Intent,
    action_explanation: str | None,
) -> str:
    if final_action == FinalAction.PROCESS_REFUND:
        return "I found a duplicate successful charge and refunded one of the payments."
    if final_action == FinalAction.EXPLAIN_INCIDENT_AND_ROUTE:
        return (
            "Your subscription is active, and the failures match an active service incident. "
            "I routed the case for engineering follow-up instead of issuing a refund."
        )
    if final_action == FinalAction.ESCALATE:
        return "I cannot safely complete that action automatically, so I escalated the case for human review."
    if final_action == FinalAction.ASK_CLARIFYING_QUESTION:
        return "I need a little more information before I can safely resolve this request."
    explanation = action_explanation or "No eligible action was found from the available evidence."
    return f"I reviewed this {intent.value.replace('_', ' ')} request. {explanation}"


def _template_audit_note(output: AgentRunOutput) -> str:
    return (
        f"Case {output.case_id}: intent={output.intent.value}, "
        f"action={output.final_action.value}, escalate={output.escalate}, "
        f"tools={','.join(output.tool_calls)}"
    )
