import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import pytest


# Force deterministic test behavior even when a real .env file is present.
os.environ["DEBUG_MODE"] = "true"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("MCP HTTP test server exited before accepting connections.")
        with socket.socket() as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError("Timed out waiting for MCP HTTP test server.")


@pytest.fixture(scope="session", autouse=True)
def mcp_http_server() -> Iterator[None]:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "MCP_BACKEND_URL": f"{base_url}/backend/mcp",
        "MCP_GOVERNANCE_URL": f"{base_url}/governance/mcp",
        "MCP_OBSERVABILITY_URL": f"{base_url}/observability/mcp",
        "MCP_KNOWLEDGE_URL": f"{base_url}/knowledge/mcp",
    }
    os.environ.update(
        {
            "MCP_BACKEND_URL": env["MCP_BACKEND_URL"],
            "MCP_GOVERNANCE_URL": env["MCP_GOVERNANCE_URL"],
            "MCP_OBSERVABILITY_URL": env["MCP_OBSERVABILITY_URL"],
            "MCP_KNOWLEDGE_URL": env["MCP_KNOWLEDGE_URL"],
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.mcp_http:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
    )
    _wait_for_port(port, process)
    try:
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
