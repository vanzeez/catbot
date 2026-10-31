"""Shared pydantic models and protocols (spec sections 2 and 2.1).

Changes only with agreement of every part of the system: loop, gate, UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

Origin = Literal["user", "command_output", "screen", "web"]
Tier = Literal["T0", "T1", "T2", "T3"]
Stage = Literal[
    "listen", "think", "risk", "gate", "confirm", "execute", "result", "speak", "done", "error"
]

TIERS: tuple[Tier, ...] = ("T0", "T1", "T2", "T3")


def tier_rank(tier: Tier) -> int:
    return TIERS.index(tier)


def max_tier(*tiers: Tier | None) -> Tier:
    """Highest tier among the non-None arguments (T0 if none)."""
    present = [t for t in tiers if t is not None]
    return max(present, key=tier_rank) if present else "T0"


class Answer(BaseModel):
    choice: str
    confidence: float
    source: Literal["laya", "keyword"]
    checkpoint: str | None = None  # english | multilingual | None


class ToolCall(BaseModel):
    task_id: str
    step: int
    call_id: str  # Sarvam tool_call id
    tool: str
    args: dict[str, Any]
    request_en: str  # English line used in the Laya state (section 4 step 4a)
    last_origin: Origin = "user"  # origin of the most recent tool result in context
    last_origin_flagged: bool = False  # provenance.flag_instructions fired on that result


class RiskDecision(BaseModel):
    tier: Answer  # choice in T0..T3
    verify: Answer  # execute | wrong_tool | unclear
    latency_ms: int


class PolicyVerdict(BaseModel):
    verdict: Literal["allow", "confirm", "deny"]
    policy: str
    reason: str  # English; safety/messages.py translates for speech
    hard: bool = True  # hard deny ends the task; soft deny feeds corrective_context back
    corrective_context: str | None = None  # appended as the tool message on a soft deny


class GateToken(BaseModel):
    call_id: str
    verdict: PolicyVerdict
    confirmed: bool = False


class ToolResult(BaseModel):
    ok: bool
    summary: str
    data: dict[str, Any] | None = None
    origin: Origin = "command_output"
    error: str | None = None


class Event(BaseModel):
    ts: str
    task_id: str
    stage: Stage
    step: int | None = None
    tool: str | None = None
    verdict: str | None = None
    latency_ms: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Speaker(Protocol):
    async def speak(self, text: str, lang: str) -> None: ...


class ConfirmChannel(Protocol):
    async def ask(
        self, task_id: str, question: str, lang: str, timeout_s: float = 8.0
    ) -> str | None: ...


@dataclass
class TaskOutcome:
    task_id: str
    ok: bool
    spoken: str
    steps: list[ToolResult] = field(default_factory=list)
    stopped_by: str | None = None  # policy id or None


class Gate(Protocol):
    name: Literal["keyword", "laya"]
    last_top: dict[str, list[Answer]]

    def classify(self, call: ToolCall) -> RiskDecision: ...

    def read_confirmation(self, question: str, reply: str) -> Answer: ...
