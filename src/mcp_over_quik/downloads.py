"""Serve static Claude/Cursor setup files from the container."""

from __future__ import annotations

import os
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

_CLAUDE_FILES: dict[str, str] = {
    "index.json": "application/json; charset=utf-8",
    "mcp.json": "application/json; charset=utf-8",
    "CLAUDE.md": "text/markdown; charset=utf-8",
    "cursor-mcp.json": "application/json; charset=utf-8",
}


def claude_static_dir() -> Path:
    env_dir = os.environ.get("WEBQUIK_STATIC_DIR")
    if env_dir:
        return Path(env_dir)
    container = Path("/app/static/claude")
    if container.is_dir():
        return container
    return Path(__file__).resolve().parents[2] / "static" / "claude"


def _file_response(filename: str) -> Response:
    media_type = _CLAUDE_FILES[filename]
    path = claude_static_dir() / filename
    if not path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    download_name = ".mcp.json" if filename == "mcp.json" else filename
    return FileResponse(path, media_type=media_type, filename=download_name)


def register_claude_download_routes(mcp) -> None:
    @mcp.custom_route("/claude", methods=["GET"])
    async def claude_index(_request: Request) -> Response:
        return _file_response("index.json")

    @mcp.custom_route("/claude/index.json", methods=["GET"])
    async def claude_index_json(_request: Request) -> Response:
        return _file_response("index.json")

    @mcp.custom_route("/claude/mcp.json", methods=["GET"])
    async def claude_mcp(_request: Request) -> Response:
        return _file_response("mcp.json")

    @mcp.custom_route("/claude/CLAUDE.md", methods=["GET"])
    async def claude_instructions(_request: Request) -> Response:
        return _file_response("CLAUDE.md")

    @mcp.custom_route("/claude/cursor-mcp.json", methods=["GET"])
    async def claude_cursor(_request: Request) -> Response:
        return _file_response("cursor-mcp.json")
