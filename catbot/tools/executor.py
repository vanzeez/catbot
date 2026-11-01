"""Executor: runs a tool only with a GateToken minted by policy_gate.issue_token."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from catbot.contracts import GateToken, ToolCall, ToolResult
from catbot.safety.policy_gate import redeem


class ToolBackend(Protocol):
    name: str

    async def run(self, tool: str, args: dict[str, Any]) -> tuple[list[str], ToolResult]: ...


class RealTools:
    name = "real"

    def __init__(self, shell_cwd: Path, tavily_key: str = "", codex_model: str = "gpt-5.6-luna"):
        self.shell_cwd = shell_cwd
        self.tavily_key = tavily_key
        self.codex_model = codex_model

    async def run(self, tool: str, args: dict[str, Any]) -> tuple[list[str], ToolResult]:
        from catbot.tools import desktop, screen, shell, web

        if tool == "run_command":
            return await shell.run_command(
                args["command"], args.get("cwd"), args.get("timeout_s"), default_cwd=self.shell_cwd
            )
        if tool == "set_volume":
            return await desktop.set_volume(args["action"], args.get("level"))
        if tool == "lock_screen":
            return await desktop.lock_screen()
        if tool == "take_screenshot":
            return await desktop.take_screenshot()
        if tool == "read_screen":
            return await screen.read_screen()
        if tool == "web_search":
            return await web.web_search(args["query"], self.tavily_key)
        if tool == "write_code":
            from catbot.tools.coder import write_code

            return await write_code(
                args["app_name"], args["spec"], sandbox=self.shell_cwd, model=self.codex_model
            )
        return [tool], ToolResult(ok=False, summary="unknown tool", error="unknown tool")


class Executor:
    def __init__(self, backend: ToolBackend) -> None:
        self.backend = backend

    async def execute(
        self, call: ToolCall, token: GateToken | None
    ) -> tuple[list[str], ToolResult]:
        redeem(call, token)  # raises PermissionError without a valid, unused token
        try:
            return await self.backend.run(call.tool, call.args)
        except Exception as exc:  # noqa: BLE001 - a tool crash is a failed result, not a crash
            return [call.tool], ToolResult(ok=False, summary="tool crashed", error=str(exc))
