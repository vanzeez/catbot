"""Wake word "meow". Sarvam STT transcribes it as "Meow" reliably (FINDINGS: 8/8 clips)."""

from __future__ import annotations

import re

# STT hears meow as "Now" in continuous mode, so "now" also wakes (demo trade-off).
# Also: meow, miaow, miao, mew, myau, Devanagari म्याऊं; "hey/ok meow" wakes too.
_WAKE_WORD = r"(?:now|m+e+o+w+|mi+a+o+w*|m+e+w+|mya+u+|म्या[ऊउ]ं?)"
_WAKE = re.compile(
    rf"^\W*(?:(?:hey|hi|ok|okay|arre|oye)\W+)?{_WAKE_WORD}(?:\W+{_WAKE_WORD})*\b\W*",
    re.I,
)


def split_wake(text: str) -> tuple[bool, str]:
    """(woke, rest). Woke only when the utterance starts with the wake word."""
    m = _WAKE.match(text or "")
    if not m:
        return False, (text or "").strip()
    return True, text[m.end() :].strip()
