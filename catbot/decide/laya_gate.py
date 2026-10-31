"""LayaGate: the 3 fine-tuned questions on one pinned checkpoint (spec 5.1-5.2, FINDINGS Laya).

- `laya.Agent(path)` loads exactly one checkpoint, so routing never switches to multilingual.
- Confidence = chosen option's probability after per-question temperature from calibration.json
  (FINDINGS: `answer_confidence`, not `confidence`). The checkpoint's own temperatures are
  already applied by laya, so calibration.json defaults to 1.0.
- Native tools keep their tier_hint (confidence 1.0); Laya still answers verify_call.
- read_confirmation uses Laya for Latin-script replies only; other scripts use the lexicon.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from catbot.config import REPO, Settings
from catbot.contracts import Answer, RiskDecision, ToolCall, tier_rank
from catbot.decide.keyword_gate import KeywordGate, read_reply
from catbot.decide.questions import CONFIRM_REPLY, RISK_TIER, VERIFY_CALL, confirm_state, risk_state
from catbot.tools.registry import TOOLS

log = logging.getLogger("catbot.laya")
ZERO_SHOT = "convaiinnovations/laya"  # English checkpoint, un-tuned


def calibrate(probs: dict[str, float], temperature: float) -> dict[str, float]:
    if not probs:
        return {}
    t = temperature if temperature > 0 else 1.0
    powered = {k: max(v, 1e-9) ** (1.0 / t) for k, v in probs.items()}
    total = sum(powered.values())
    return {k: v / total for k, v in powered.items()}


def is_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isascii() for c in letters)


class LayaGate:
    name = "laya"

    def __init__(
        self,
        agent: Any,
        checkpoint: str,
        calibration: dict[str, float] | None = None,
        tuned: bool = True,
    ) -> None:
        self.agent = agent
        self.checkpoint = checkpoint
        self.tuned = tuned
        self.calibration = calibration or {}
        self.last_top: dict[str, list[Answer]] = {}
        self._keyword = KeywordGate()

    @classmethod
    def load(cls, settings: Settings, *, tuned: bool) -> LayaGate:
        os.environ.setdefault("USE_TF", "0")
        import laya

        if tuned:
            if not settings.laya_checkpoint_dir:
                raise RuntimeError("LAYA_CHECKPOINT_DIR is empty")
            path = Path(settings.laya_checkpoint_dir).expanduser()
            path = path if path.is_absolute() else REPO / path
            if not (path / "rl_agent_config.json").exists():
                raise RuntimeError(f"no Laya checkpoint at {path}")
            src, label = str(path), "catbot-tuned"
        else:
            src, label = ZERO_SHOT, "english-zero-shot"
        t = time.perf_counter()
        agent = laya.Agent(src)
        log.warning("Laya %s loaded in %.1f s", label, time.perf_counter() - t)
        return cls(agent, label, settings.calibration, tuned=tuned)

    def _answer(self, res: dict[str, Any], qid: str) -> tuple[Answer, list[Answer]]:
        raw = res["answers"][qid]
        probs = calibrate(raw.get("probabilities") or {}, self.calibration.get(qid, 1.0))
        if probs:
            ranked = sorted(probs.items(), key=lambda kv: -kv[1])
            choice, conf = ranked[0]
        else:
            ranked, choice, conf = [], raw["choice"], float(raw.get("answer_confidence", 0.0))
        top = [
            Answer(choice=c, confidence=round(p, 4), source="laya", checkpoint=self.checkpoint)
            for c, p in ranked[:3]
        ]
        return Answer(
            choice=choice, confidence=round(conf, 4), source="laya", checkpoint=self.checkpoint
        ), top

    def classify(self, call: ToolCall) -> RiskDecision:
        t = time.perf_counter()
        res = self.agent.predict(
            risk_state(call), {"risk_tier": RISK_TIER, "verify_call": VERIFY_CALL}
        )
        tier, tier_top = self._answer(res, "risk_tier")
        verify, verify_top = self._answer(res, "verify_call")
        spec = TOOLS.get(call.tool)
        if spec is not None and spec.tier_hint is not None:
            tier = Answer(
                choice=spec.tier_hint, confidence=1.0, source="laya", checkpoint=self.checkpoint
            )
        else:
            # Defense in depth (EVAL: the tuned checkpoint called credential reads T0 at 0.98):
            # the regex tier is a floor. Laya may raise risk, never lower it below the keyword.
            kw = self._keyword.classify(call).tier
            if tier_rank(kw.choice) > tier_rank(tier.choice):  # type: ignore[arg-type]
                tier = kw

        self.last_top = {"risk_tier": tier_top, "verify_call": verify_top}
        return RiskDecision(
            tier=tier, verify=verify, latency_ms=int((time.perf_counter() - t) * 1000)
        )

    def read_confirmation(self, question: str, reply: str) -> Answer:
        if not reply.strip() or not is_latin(reply):
            ans = read_reply(reply)
        else:
            res = self.agent.predict(
                confirm_state(question, reply), {"confirm_reply": CONFIRM_REPLY}
            )
            ans, top = self._answer(res, "confirm_reply")
            self.last_top["confirm_reply"] = top
        return ans


class BackgroundLaya:
    """Shadow gate that loads in a thread so startup is not blocked; skipped until ready."""

    name = "laya"

    def __init__(self, settings: Settings) -> None:
        self._gate: LayaGate | None = None
        self.error: str | None = None
        self.last_top: dict[str, list[Answer]] = {}
        threading.Thread(target=self._load, args=(settings,), daemon=True).start()

    def _load(self, settings: Settings) -> None:
        try:
            self._gate = LayaGate.load(settings, tuned=False)
        except Exception as exc:  # noqa: BLE001
            self.error = str(exc)
            log.warning("shadow Laya failed to load: %s", exc)

    @property
    def ready(self) -> bool:
        return self._gate is not None

    @property
    def checkpoint(self) -> str | None:
        return self._gate.checkpoint if self._gate else None

    def classify(self, call: ToolCall) -> RiskDecision:
        if self._gate is None:
            raise RuntimeError("shadow Laya still loading" if not self.error else self.error)
        return self._gate.classify(call)

    def read_confirmation(self, question: str, reply: str) -> Answer:
        return read_reply(reply)
