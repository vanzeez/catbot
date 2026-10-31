"""Pure helpers for the loop: request_en selection, result truncation, the Stop signal."""

from __future__ import annotations

import json
from typing import Any

from catbot.contracts import ToolResult


def ascii_only(text: str) -> str:
    return " ".join("".join(c for c in text if c.isascii()).split())


def pick_request_en(assistant_text: str, utterance: str) -> str:
    if len(assistant_text.split()) >= 3 and assistant_text.isascii():
        return assistant_text
    stripped = ascii_only(utterance)
    return stripped if len(stripped.split()) >= 3 else utterance


def small_result(result: ToolResult) -> dict[str, Any]:
    d = result.model_dump()
    blob = json.dumps(d.get("data"), ensure_ascii=False, default=str)
    if len(blob) > 1024:
        d["data"] = {"truncated": blob[:1024]}
    return d


class Stop(Exception):
    def __init__(self, policy: str, spoken: str) -> None:
        self.policy, self.spoken = policy, spoken


def parse_args(raw: str) -> Any:
    """Tool-call arguments as an object for display; the raw string if it is not JSON."""
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return raw
