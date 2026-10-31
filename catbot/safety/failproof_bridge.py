"""Failproof AI bridge. FINDINGS outcome B: the SDK reports only, so check() never allows more.

report(event): mirrors Catbot events into the Failproof spool. Non-blocking, never raises.
check(call, tier): only in enforce mode; no decision endpoint exists, so it behaves as
"unreachable": T2 is denied, T0/T1 unchanged.
"""

from __future__ import annotations

import logging
from typing import Any

from catbot.contracts import Event, PolicyVerdict, Tier, ToolCall

log = logging.getLogger("catbot.failproof")


class FailproofBridge:
    def __init__(self, mode: str = "report") -> None:
        self.mode = mode
        self._sdk: Any = None
        if mode != "off":
            try:
                import failproofai_sdk

                failproofai_sdk.configure(environment="catbot")
                self._sdk = failproofai_sdk
            except Exception as exc:  # noqa: BLE001
                log.warning("failproof sdk unavailable: %s", exc)

    @property
    def active(self) -> bool:
        return self._sdk is not None

    def report(self, event: Event) -> None:
        if self._sdk is None:
            return
        try:
            self._report(event)
        except Exception as exc:  # noqa: BLE001 - reporting must never break the loop
            log.debug("failproof report failed: %s", exc)

    def _report(self, e: Event) -> None:
        ev, ids = self._sdk.event, {"session_id": e.task_id, "agent_id": "catbot"}
        p = e.payload
        cid = f"{e.task_id}-{e.step}"
        if e.stage == "execute":
            ev.tool_use(**ids, tool_name=e.tool or "?", tool_call_id=cid, input=p.get("args"))
        elif e.stage == "result":
            r = p.get("result") or {}
            ev.tool_result(
                **ids,
                tool_name=e.tool or "?",
                tool_call_id=cid,
                output=r.get("summary"),
                error=r.get("error"),
            )
        elif e.stage == "gate":
            v = p.get("verdict") or {}
            ev.hook_triggered(**ids, hook_name="policy_gate", hook_id=cid, trigger_event="tool")
            ev.hook_completed(
                **ids,
                hook_name="policy_gate",
                hook_id=cid,
                outcome=v.get("verdict"),
                output=v.get("policy"),
            )
        elif e.stage == "confirm" and "question" in p:
            ev.human_wait(**ids, input_id=cid, prompt=p["question"], options=["haan", "nahi"])
        elif e.stage == "confirm" and "reply" in p:
            ev.human_input(**ids, input_id=cid, response=p.get("reply"))
        elif e.stage == "done":
            ev.agent_end(
                **ids, outcome="success" if p.get("ok") else "failed", summary=p.get("stopped_by")
            )
        elif e.stage == "error":
            ev.error(**ids, error_type="catbot", message=str(p.get("message", ""))[:500])

    def check(self, call: ToolCall, tier: Tier) -> PolicyVerdict | None:
        if self.mode != "enforce" or tier != "T2":
            return None
        return PolicyVerdict(
            verdict="deny",
            policy="failproof",
            reason="Failproof enforcement unreachable; T2 denied.",
        )
