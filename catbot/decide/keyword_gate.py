"""KeywordGate: regex risk tiers, utterance floor, yes/no lexicon (spec 5.5). Stand-in for Laya."""

from __future__ import annotations

import re
import time

from pydantic import ValidationError

from catbot.contracts import Answer, RiskDecision, Tier, ToolCall, max_tier
from catbot.tools.registry import TOOLS, validate_args

_I = re.I


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in parts), _I)


T3_RX = _rx(
    r"\brm\s+(-[a-z]*\s+)*-[a-z]*r",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bformat\b",
    r"diskutil|fdisk|Format-Volume",
    r"Remove-Item\b.*-Recurse",
    r"\brd\b.*/s|rmdir\s+/s",
    r"curl\b.*\|\s*(ba|z)?sh\b",
    r"chmod\s+-R\s+777",
    r"git\s+push\b.*--force",
    r"\b(shutdown|reboot|halt)\b",
    r"passwd|find-generic-password|Get-Credential|keychain",
    r"\bpay\b|\bupi\b|\btransfer\b",
    r"Clear-RecycleBin|empty\s+(the\s+)?trash|\.Trash/\*",
)
_FIND_DELETE = re.compile(r"\bfind\b.*-delete", _I)
_FIND_BROAD = re.compile(r"-type\s+d|\*|~|(^|\s)/", _I)
T2_RX = _rx(
    r"\brm\b",
    r"\bmv\b",
    r"\bdel\b|\berase\b|\brmdir\b|\brd\b|\bunlink\b|\bshred\b",
    r"Remove-Item|Move-Item|Clear-Content",
    r"\bfind\b.*-delete",
    r"trash|Recycle|\.Trash",
    r"Finder.*delete",
    r"git\s+(push|commit|clean)|git\s+reset\s+--hard",
    r"curl\b.*-X\s*(POST|PUT|DELETE)|wget\b.*--post",
    r"\bmail\b|sendmail|osascript\b.*Mail",
    r"Send-MailMessage",
    r"\b(kill|pkill|killall|taskkill)\b|Stop-Process",
    r"brew\s+install|pip3?\s+install|npm\s+install|\bwinget\b|\bchoco\b",
)
T1_RX = _rx(
    r"\bmkdir\b|\btouch\b|\becho\b.*>|\btee\b|\bcp\b|New-Item|Set-Content|Out-File|Add-Content",
    r"\bopen\b|\bstart\b|\bcode\b|git\s+(init|add)|defaults\s+write|osascript|Copy-Item",
)
_SPLIT = re.compile(r"\s*(?:;|&&|\|\||\|)\s*")
_PURE_READ_HEADS = {
    "ls",
    "pwd",
    "cat",
    "head",
    "tail",
    "wc",
    "stat",
    "du",
    "df",
    "file",
    "grep",
    "rg",
    "find",
    "which",
    "whoami",
    "date",
    "tree",
    "get-childitem",
    "gci",
    "dir",
    "get-content",
    "gc",
    "get-location",
    "test-path",
    "get-item",
    "select-string",
    "echo",
    "printf",
    "sort",
    "uniq",
    "cut",
    "basename",
    "dirname",
    "write-output",
    "write-host",
}
_STDERR_ONLY = re.compile(r"\s2>(/dev/null|&1|\$null)")
_UNSAFE_IN_READ = re.compile(r"[>`]|\$\(|-delete|-exec|-ok\b|\bxargs\b", _I)


# Text written to a file by echo/printf is data, not a command: `echo "npm install" > README.md`
# must not read as an install. Only a quoted payload directly followed by > or >> is blanked, so
# `echo "rm -rf ~" | sh` (payload piped into a shell) is still scored on its text.
_ECHO_PAYLOAD = re.compile(
    r"""\b(echo|printf|Write-Output)\s+(-[a-zA-Z]+\s+)*("(?:[^"\\]|\\.)*"|'[^']*')(?=\s*>{1,2})""",
    re.S,
)


_HEREDOC = re.compile(r"""<<-?\s*(['"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b""", re.S)
_WRITE_REDIRECT = re.compile(r"(?<![0-9&])>{1,2}\s*(?!&)[^\s]")  # stdout to a file; not 2>/dev/null


def strip_payloads(command: str) -> str:
    """Blank text that is only written into a file (echo payloads, heredoc bodies)."""
    command = _HEREDOC.sub("<< EOF", command) if _WRITE_REDIRECT.search(command) else command
    return _ECHO_PAYLOAD.sub(lambda m: f'{m.group(1)} ""', command)


def command_tier(command: str) -> Tier:
    """Highest tier over the whole command and each ;/&&/| part. First matching row wins."""
    command = strip_payloads(command)
    parts = [command, *_SPLIT.split(command)]
    return max_tier(*(_part_tier(p) for p in parts if p.strip()))


def _part_tier(part: str) -> Tier:
    if T3_RX.search(part) or (_FIND_DELETE.search(part) and _FIND_BROAD.search(part)):
        return "T3"
    if T2_RX.search(part):
        return "T2"
    if T1_RX.search(part) or _WRITE_REDIRECT.search(part.replace("2>/dev/null", "")):
        return "T1"
    return "T0"


def is_pure_read(command: str) -> bool:
    """True only for plain read-only commands (ls, cat, find without -delete, ...), no redirects."""
    command = _STDERR_ONLY.sub(" ", command)  # 2>/dev/null and 2>&1 only silence errors
    if not command.strip() or _UNSAFE_IN_READ.search(command):
        return False
    for part in _SPLIT.split(command):
        words = part.strip().split()
        if not words or words[0].lower() not in _PURE_READ_HEADS:
            return False
    return command_tier(command) == "T0"


# ---- utterance floor -------------------------------------------------------------------------
_QUANT = (
    "saari",
    "saare",
    "sara",
    "sare",
    "sab",
    "sabhi",
    "sabhee",
    "all",
    "everything",
    "poora",
    "poore",
    "poori",
    "सारी",
    "सारे",
    "सब",
    "सभी",
    "पूरा",
    "எல்லா",
)
_DESTROY = (
    "delete",
    "mita",
    "hata",
    "uda",
    "remove",
    "wipe",
    "format",
    "डिलीट",
    "मिटा",
    "हटा",
    "நீக்கு",
)
_MONEY_EXACT = {"otp", "pin", "pay", "upi", "paise", "पैसे"}
_MONEY_PREFIX = ("password", "payment", "transfer", "bhugtan", "पासवर्ड")
_T2_PREFIX = (
    "delete",
    "mita",
    "hata",
    "uda",
    "trash",
    "remove",
    "bhej",
    "send",
    "mail",
    "push",
    "install",
    "uninstall",
    "kill",
    "डिलीट",
    "हटा",
    "भेज",
)
_PUNCT = re.compile(r"[^\wऀ-ॿ஀-௿]+")


def _tokens(text: str) -> list[str]:
    return [t for t in (_PUNCT.sub("", w) for w in text.lower().split()) if t]


def _starts(tok: str, prefixes: tuple[str, ...]) -> bool:
    return any(tok.startswith(p) for p in prefixes)


def utterance_tier(utterance: str) -> Tier | None:
    toks = _tokens(utterance)
    quant = [i for i, t in enumerate(toks) if t in _QUANT or t.startswith("எல்லா")]
    destroy = [i for i, t in enumerate(toks) if _starts(t, _DESTROY)]
    if any(abs(q - d) <= 6 for q in quant for d in destroy):
        return "T3"
    if any(t in _MONEY_EXACT or _starts(t, _MONEY_PREFIX) for t in toks):
        return "T3"
    if any(_starts(t, _T2_PREFIX) for t in toks) or "band kar" in " ".join(toks):
        return "T2"
    return None


# ---- yes / no lexicon --------------------------------------------------------------------------
_YES = (
    "haan",
    "han",
    "ha",
    "haanji",
    "ji",
    "yes",
    "yeah",
    "yep",
    "ok",
    "okay",
    "theek",
    "thik",
    "sure",
    "हाँ",
    "हां",
    "ठीक",
    "சரி",
    "ஆமா",
    "ஆம்",
)
_NO = (
    "nahi",
    "nahin",
    "nai",
    "na",
    "no",
    "nope",
    "mat",
    "cancel",
    "ruko",
    "stop",
    "नहीं",
    "नही",
    "मत",
    "வேண்டாம்",
    "இல்லை",
)
_NO_PHRASES = ("rehne do", "rahne do")
_YES_PHRASES = ("kar do", "kardo")


def read_reply(reply: str) -> Answer:
    text = " ".join(reply.lower().split())
    toks = set(_tokens(text)) | set(text.split())
    if toks & set(_NO) or any(p in text for p in _NO_PHRASES):
        return Answer(choice="B", confidence=0.92, source="keyword")
    if toks & set(_YES) or any(p in text for p in _YES_PHRASES):
        return Answer(choice="A", confidence=0.92, source="keyword")
    return Answer(choice="C", confidence=0.50, source="keyword")


class KeywordGate:
    name = "keyword"

    def __init__(self) -> None:
        self.last_top: dict[str, list[Answer]] = {}

    def classify(self, call: ToolCall) -> RiskDecision:
        t = time.perf_counter()
        spec = TOOLS.get(call.tool)
        if spec is not None and spec.tier_hint is not None:
            tier = Answer(choice=spec.tier_hint, confidence=1.0, source="keyword")
        elif call.tool == "run_command":
            cmd = str(call.args.get("command", ""))
            choice = command_tier(cmd)
            conf = 0.85 if choice == "T0" else 0.92
            tier = Answer(choice=choice, confidence=conf, source="keyword")
        else:
            tier = Answer(choice="T3", confidence=0.5, source="keyword")
        try:
            validate_args(call.tool, call.args)
            verify = Answer(choice="execute", confidence=0.90, source="keyword")
        except (KeyError, ValidationError):
            verify = Answer(choice="unclear", confidence=0.60, source="keyword")
        self.last_top = {"risk_tier": [tier], "verify_call": [verify]}
        return RiskDecision(
            tier=tier, verify=verify, latency_ms=int((time.perf_counter() - t) * 1e3)
        )

    def read_confirmation(self, question: str, reply: str) -> Answer:
        ans = read_reply(reply)
        self.last_top["confirm_reply"] = [ans]
        return ans
