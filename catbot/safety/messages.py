"""Spoken sentences for gate outcomes and confirmation questions (en / hi / ta)."""

from __future__ import annotations

from catbot.contracts import ToolCall

REASONS: dict[str, dict[str, str]] = {
    "unknown_tool": {
        "en": "I don't have a tool for that.",
        "hi": "Mere paas iske liye koi tool nahi hai.",
        "ta": "அதற்கு என்னிடம் கருவி இல்லை.",
    },
    "secret_in_args": {
        "en": "That contains a password, PIN or card number, so I won't touch it.",
        "hi": "Isme password, PIN ya card number hai, isliye main ye nahi karunga.",
        "ta": "இதில் கடவுச்சொல் அல்லது PIN உள்ளது, அதனால் செய்யமாட்டேன்.",
    },
    "untrusted_origin": {
        "en": "Content on the screen tried to give me an instruction. Only you can do that.",
        "hi": "Screen ke content ne mujhe hukm dene ki koshish ki. Hukm sirf aap de sakte hain.",
        "ta": "திரையில் உள்ள உள்ளடக்கம் கட்டளையிட முயன்றது. நீங்கள் மட்டுமே கட்டளையிட முடியும்.",
    },
    "task_limits": {
        "en": "Task limit reached, so I stopped.",
        "hi": "Task ki seema poori ho gayi, maine rok diya.",
        "ta": "பணி வரம்பை அடைந்தது, நிறுத்திவிட்டேன்.",
    },
    "tier_t3": {
        "en": "That is something you should do yourself. I won't do it.",
        "hi": "Ye kaam aapko khud karna chahiye. Main ye nahi karunga.",
        "ta": "இதை நீங்களே செய்ய வேண்டும். நான் செய்யமாட்டேன்.",
    },
    "one_confirm_per_task": {
        "en": "That needs a second confirmation, so I stopped. Please ask again step by step.",
        "hi": "Iske liye doosri baar poochhna padta, isliye ruk gaya. Ek ek karke boliye.",
        "ta": "இரண்டாவது உறுதிப்படுத்தல் தேவை, நிறுத்திவிட்டேன்.",
    },
    "user_cancel": {
        "en": "Okay, cancelled.",
        "hi": "Theek hai, cancel kar diya.",
        "ta": "சரி, ரத்து செய்தேன்.",
    },
    "failproof": {
        "en": "The safety policy blocked that.",
        "hi": "Safety policy ne ise rok diya.",
        "ta": "பாதுகாப்பு கொள்கை இதைத் தடுத்தது.",
    },
    "done": {"en": "Done.", "hi": "Ho gaya.", "ta": "முடிந்தது."},
    "error": {
        "en": "Something went wrong, so I stopped.",
        "hi": "Kuch gadbad ho gayi, maine rok diya.",
        "ta": "ஏதோ தவறு நடந்தது, நிறுத்திவிட்டேன்.",
    },
}

_NATIVE = {
    "set_volume": {"en": "change the volume", "hi": "volume badlun", "ta": "ஒலியை மாற்றவா"},
    "lock_screen": {"en": "lock the screen", "hi": "screen lock karun", "ta": "திரையைப் பூட்டவா"},
    "take_screenshot": {"en": "take a screenshot", "hi": "screenshot lun", "ta": "ஸ்கிரீன்ஷாட் எடுக்கவா"},
    "read_screen": {"en": "read the screen", "hi": "screen padhun", "ta": "திரையைப் படிக்கவா"},
    "web_search": {"en": "search the web", "hi": "web pe search karun", "ta": "இணையத்தில் தேடவா"},
}


def short_lang(lang: str | None) -> str:
    code = (lang or "en").split("-")[0].lower()
    return code if code in {"en", "hi", "ta"} else "en"


def reason_text(policy: str, lang: str) -> str:
    table = REASONS.get(policy, REASONS["error"])
    return table[short_lang(lang)]


def confirm_question(call: ToolCall, lang: str) -> str:
    code = short_lang(lang)
    if call.tool == "run_command":
        cmd = " ".join(str(call.args.get("command", "")).split())
        cmd = cmd if len(cmd) <= 90 else cmd[:89] + "…"
        return {
            "en": f"Shall I run: `{cmd}`? Yes or no?",
            "hi": f"Ye command chalaun: `{cmd}`? Haan ya nahi?",
            "ta": f"இந்தக் கட்டளையை இயக்கவா: `{cmd}`? ஆமா அல்லது இல்லை?",
        }[code]
    what = _NATIVE.get(call.tool, {"en": call.tool, "hi": call.tool, "ta": call.tool})[code]
    return {
        "en": f"Shall I {what}? Yes or no?",
        "hi": f"Kya main {what}? Haan ya nahi?",
        "ta": f"நான் {what}? ஆமா அல்லது இல்லை?",
    }[code]
