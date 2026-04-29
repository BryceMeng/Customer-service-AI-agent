"""Observability MCP server implemented with the MCP Python SDK."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.common import parse_backend_state
from app.tools.incident_tools import IncidentTools

mcp = FastMCP("support-observability")


@mcp.tool()
def search_incidents(
    *,
    service: str,
    window: str = "24h",
    backend_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search incidents in the supplied backend state."""

    return IncidentTools(parse_backend_state(backend_state)).search_incidents(
        service=service,
        window=window,
    )


@mcp.tool()
def get_recent_deployments(
    *,
    service: str,
    backend_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List recent deployments in the supplied backend state."""

    return IncidentTools(parse_backend_state(backend_state)).get_recent_deployments(service=service)


@mcp.tool()
def query_metrics(
    *,
    metric_name: str,
    window: str = "1h",
    backend_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return mock time-series metric data for a named metric."""

    return IncidentTools(parse_backend_state(backend_state)).query_metrics(
        metric_name=metric_name,
        window=window,
    )


@mcp.tool()
def query_logs(
    *,
    service: str,
    filters: dict[str, Any] | None = None,
    backend_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return mock log lines for a service."""

    return IncidentTools(parse_backend_state(backend_state)).query_logs(
        service=service,
        filters=filters,
    )


def main() -> None:
    """Run the observability MCP server over streamable HTTP."""

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
