from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_official_mcp_sdk_initializes_lists_and_calls_guarded_tools() -> None:
    root = Path(__file__).resolve().parents[1]
    server = root / "examples" / "guarded_mcp_server.py"

    async def exercise() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(server)],
            env=os.environ.copy(),
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "intent-integrity"

                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                assert {"save_draft", "publish_report"} <= names

                allowed = await session.call_tool(
                    "save_draft", {"report": "SDK conformance smoke test"}
                )
                assert not allowed.isError
                allowed_payload = json.loads(allowed.content[0].text)
                assert allowed_payload["decision"] == "ALLOW"
                assert allowed_payload["executed"] is True

                blocked = await session.call_tool(
                    "publish_report", {"report": "Must not publish without approval"}
                )
                assert blocked.isError
                blocked_payload = json.loads(blocked.content[0].text)
                assert blocked_payload["decision"] == "BLOCK"
                assert blocked_payload["executed"] is False

    asyncio.run(exercise())
