"""Knowledge MCP server implemented with the MCP Python SDK."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.schemas.case import FinalAction, Intent
from app.tools.policy_tools import (
    action_explanation,
    fetch_policy,
    policy_refs_for_intent,
    retrieve_similar_cases,
    search_policy_docs,
)

mcp = FastMCP("support-knowledge")


@mcp.tool()
def search_policy(query: str, locale: str = "en-US") -> dict[str, Any]:
    """Search local policy references."""

    return search_policy_docs(query=query, locale=locale)


@mcp.tool()
def policy_refs(intent: Intent) -> dict[str, list[str]]:
    """Return policy references for a supported intent."""

    return {"refs": policy_refs_for_intent(intent)}


@mcp.tool()
def explain_action(final_action: FinalAction) -> dict[str, str]:
    """Explain a final action in stable customer-safe language."""

    return {"explanation": action_explanation(final_action)}


@mcp.tool()
def fetch_policy_doc(policy_id: str) -> dict[str, str]:
    """Return the full text of a policy document by ID."""

    return fetch_policy(policy_id=policy_id)


@mcp.tool()
def retrieve_similar(issue_type: str, context: str = "") -> dict[str, Any]:
    """Return representative similar past cases for an issue type."""

    return retrieve_similar_cases(issue_type=issue_type, context=context)


def main() -> None:
    """Run the knowledge MCP server over streamable HTTP."""

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
