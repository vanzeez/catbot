"""policy_gate: the only path to a GateToken (spec 5.4). First matching rule wins."""

from __future__ import annotations

import json
from collections.abc import Callable

from catbot.config import Thresholds
from catbot.contracts import GateToken, PolicyVerdict, RiskDecision, Tier, ToolCall, max_tier
from catbot.decide.keyword_gate import is_pure_read
from catbot.safety.patterns import secret_kind
from catbot.tools.registry import TOOLS

_ISSUED: dict[str, GateToken] = {}


def _deny(policy: str, reason: str, *, hard: bool = True, fix: str | None = None) -> PolicyVerdict:
    return PolicyVerdict(
        verdict="deny", policy=policy, reason=reason, hard=hard, corrective_context=fix
    )


def _is_read_only(call: ToolCall) -> bool:
    spec = TOOLS.get(call.tool)
    if spec is not None and spec.tier_hint == "T0":
        return True
    return call.tool == "run_command" and is_pure_read(str(call.args.get("command", "")))


def effective_tier(call: ToolCall, risk: RiskDecision, th: Thresholds, floor: Tier | None) -> Tier:
    """max(tier, floor) when confident, else max(T2, floor). A T2 floor skips pure reads."""
    if floor == "T2" and _is_read_only(call):
        floor = None
    tier: Tier = risk.tier.choice if risk.tier.choice in ("T0", "T1", "T2", "T3") else "T3"  # type: ignore[assignment]
    if risk.tier.confidence >= th.tier_conf:
        return max_tier(tier, floor)
    return max_tier("T2", floor)


def _key(call: ToolCall) -> str:
    return call.tool + json.dumps(call.args, sort_keys=True)


def policy_gate(
    call: ToolCall,
    risk: RiskDecision,
    history: list[ToolCall],
    *,
    confirms_used: int,
    elapsed_s: float,
    utterance_floor: Tier | None,
    thresholds: Thresholds | None = None,
    failproof_check: Callable[[ToolCall, Tier], PolicyVerdict | None] | None = None,
) -> PolicyVerdict:
    th = thresholds or Thresholds()
    if call.tool not in TOOLS:
        return _deny("unknown_tool", f"No tool named {call.tool}.")
    if kind := secret_kind(call.args):
        return _deny("secret_in_args", f"Arguments contain a secret ({kind}).")
    tier = effective_tier(call, risk, th, utterance_floor)
    if call.last_origin_flagged and tier != "T0":
        return _deny("untrusted_origin", "Content tried to issue an instruction; only you can.")
    if call.step > th.max_steps or elapsed_s > th.max_wall_s:
        return _deny("task_limits", "Task step or time limit reached.")
    if sum(_key(h) == _key(call) for h in history) >= 3:
        return _deny(
            "repeat_loop",
            "Same action repeated.",
            hard=False,
            fix="Already done; do not repeat. Tell the user.",
        )
    if risk.verify.choice != "execute" and risk.verify.confidence >= th.verify_conf:
        return _deny(
            "verify_failed",
            "Action does not match the request.",
            hard=False,
            fix="This action does not match the request. Pick the right one or stop.",
        )
    if tier == "T3":
        return _deny("tier_t3", "That is something you should do yourself.")
    if tier == "T2":
        if confirms_used >= th.max_confirms:
            return _deny("one_confirm_per_task", "Only one confirmation per task.")
        verdict = PolicyVerdict(
            verdict="confirm",
            policy="tier_t2_or_unsure",
            reason="Hard to undo or unsure; ask the user first.",
        )
    else:
        verdict = PolicyVerdict(verdict="allow", policy="allow", reason=f"{tier}: safe to run.")
    if failproof_check is not None:
        stricter = failproof_check(call, tier)
        if stricter is not None and stricter.verdict == "deny":
            return stricter
    return verdict


def issue_token(call: ToolCall, verdict: PolicyVerdict, *, confirmed: bool = False) -> GateToken:
    """Mint a token for an allow, or a confirm the user accepted. Only the loop calls this."""
    if verdict.verdict == "deny" or (verdict.verdict == "confirm" and not confirmed):
        raise PermissionError(f"no token for {verdict.verdict} ({verdict.policy})")
    token = GateToken(call_id=call.call_id, verdict=verdict, confirmed=confirmed)
    _ISSUED[call.call_id] = token
    return token


def redeem(call: ToolCall, token: GateToken | None) -> None:
    """Raise PermissionError unless `token` was minted by issue_token for this call. Single use."""
    if token is None or token.call_id != call.call_id or _ISSUED.get(call.call_id) is not token:
        raise PermissionError(f"tool {call.tool} has no valid GateToken")
    del _ISSUED[call.call_id]
