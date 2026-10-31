"""Gate selection (spec 5.1)."""

from __future__ import annotations

import logging

from catbot.config import Settings
from catbot.contracts import Gate
from catbot.decide.keyword_gate import KeywordGate

log = logging.getLogger("catbot.decide")


def get_gate(settings: Settings) -> tuple[Gate, Gate | None]:
    """(active gate, shadow gate or None). Any Laya failure falls back to keyword + shadow."""
    shadow: Gate | None = None
    if settings.router == "laya":
        try:
            from catbot.decide.laya_gate import LayaGate

            return LayaGate.load(settings, tuned=True), None
        except Exception as exc:  # noqa: BLE001
            log.warning("Laya gate unavailable (%s); using keyword gate, shadow on", exc)
            settings.shadow = True
    if settings.shadow:
        try:
            from catbot.decide.laya_gate import BackgroundLaya

            shadow = BackgroundLaya(settings)  # loads in a thread; skipped until ready
        except Exception as exc:  # noqa: BLE001
            log.warning("shadow Laya unavailable: %s", exc)
    return KeywordGate(), shadow
