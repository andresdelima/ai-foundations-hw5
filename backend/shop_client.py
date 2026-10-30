"""The backend's only way to read or change the shop: the Campus Customs MCP server.

The agents reach the server through PydanticAI's MCPToolset; the agent loop in
team.py (and later the API) uses this client. Both talk to the same FastMCP
server (mcp_server/server.py) in-process, so there is no second shop-tools
layer: every shop fact comes from an MCP tool over data/campus_customs_new.db.
"""

from __future__ import annotations

import shutil
from typing import Any

from fastmcp import Client

import config


def _server():
    from server import mcp  # mcp_server/server.py

    return mcp


async def call(tool: str, **args: Any) -> Any:
    """Call one MCP tool and return its structured result."""
    async with Client(_server()) as client:
        result = await client.call_tool(tool, args)
    return result.data


def reset_working_copy() -> dict[str, Any]:
    """Start a fresh run: copy the untouched original over the working copy.
    (A file copy, not a shop tool — the MCP server recreates its board tables on first use.)"""
    shutil.copyfile(config.ORIGINAL_DB, config.WORKING_DB)
    config.WORKING_DB.chmod(0o644)
    return {"reset": True, "working_copy": config.WORKING_DB.name, "from": config.ORIGINAL_DB.name}
