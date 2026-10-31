"""The 3 Laya questions and their state builders (spec 5.2). States are English only."""

from __future__ import annotations

import json
from typing import Any

from catbot.contracts import ToolCall

RISK_TIER = {
    "type": "choice",
    "instructions": "How risky is this action?",
    "criteria": {
        "T0": "only reads or looks",
        "T1": "local change, easy to undo",
        "T2": "sends, publishes, trashes or hard to undo",
        "T3": "destroys data, pays, or touches credentials or system",
    },
}
VERIFY_CALL = {
    "type": "choice",
    "instructions": "Does this action match the request?",
    "criteria": {
        "execute": "matches the request",
        "wrong_tool": "a different action fits",
        "unclear": "cannot tell",
    },
}
CONFIRM_REPLY = {
    "type": "choice",
    "instructions": "What did the user answer?",
    "criteria": {"A": "the user agrees", "B": "the user refuses", "C": "unclear"},
}
QUESTIONS = {"risk_tier": RISK_TIER, "verify_call": VERIFY_CALL, "confirm_reply": CONFIRM_REPLY}


def risk_state_text(request_en: str, tool: str, args: dict[str, Any]) -> str:
    return f"Request: {request_en}\nAction: {tool} {json.dumps(args, ensure_ascii=False)[:400]}"


def risk_state(call: ToolCall) -> str:
    return risk_state_text(call.request_en, call.tool, call.args)


def confirm_state(question: str, reply: str) -> str:
    return f"Question: {question}\nReply: {reply}"
