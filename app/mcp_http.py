"""Combined HTTP MCP server app for local and remote tool hosting."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount

from app.mcp_servers.backend_server import mcp as backend_mcp
from app.mcp_servers.governance_server import mcp as governance_mcp
from app.mcp_servers.knowledge_server import mcp as knowledge_mcp
from app.mcp_servers.observability_server import mcp as observability_mcp

backend_app = backend_mcp.streamable_http_app()
governance_app = governance_mcp.streamable_http_app()
observability_app = observability_mcp.streamable_http_app()
knowledge_app = knowledge_mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(_: Starlette) -> AsyncIterator[None]:
    """Start all mounted MCP streamable HTTP session managers."""

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(backend_mcp.session_manager.run())
        await stack.enter_async_context(governance_mcp.session_manager.run())
        await stack.enter_async_context(observability_mcp.session_manager.run())
        await stack.enter_async_context(knowledge_mcp.session_manager.run())
        yield


app = Starlette(
    lifespan=lifespan,
    routes=[
        Mount("/backend", app=backend_app),
        Mount("/governance", app=governance_app),
        Mount("/observability", app=observability_app),
        Mount("/knowledge", app=knowledge_app),
    ]
)
