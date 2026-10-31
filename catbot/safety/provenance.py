"""Flag instruction-like text inside tool output (screen, web, command output)."""

from __future__ import annotations

import re

_VERB = (
    r"(send|bhej\w*|forward|delete|ignore\s+(?:all|previous)|run|execute|install"
    r"|password|pay|transfer)"
)
_TARGET = r"(this|to everyone|sabko|all|assistant|catbot|ai)"
_FLAG = re.compile(
    rf"\b{_VERB}\b.{{0,40}}\b{_TARGET}\b|\b{_TARGET}\b.{{0,40}}\b{_VERB}\b", re.I | re.S
)


def flag_instructions(text: str) -> bool:
    return bool(text) and bool(_FLAG.search(text))
