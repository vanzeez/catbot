"""Secret detectors for tool arguments: OTP, PIN, password, card numbers (Luhn), UPI PIN."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "otp": re.compile(r"\botp\b\D{0,12}\d{4,8}|\d{4,8}\D{0,12}\botp\b", re.I),
    "pin": re.compile(r"\b(m?pin)\b\D{0,10}\d{4,6}\b", re.I),
    "password": re.compile(r"\b(password|passwd|passcode)\b", re.I),
    "upi_pin": re.compile(r"\bupi\b.{0,20}\bpin\b", re.I),
}
_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def find_card(text: str) -> bool:
    for m in _CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            return True
    return False


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list | tuple):
        for v in value:
            yield from _strings(v)


def secret_kind(args: dict[str, Any]) -> str | None:
    """Name of the first secret pattern found in any string argument, else None."""
    for text in _strings(args):
        for name, pat in SECRET_PATTERNS.items():
            if pat.search(text):
                return name
        if find_card(text):
            return "card"
    return None
