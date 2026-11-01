"""Spoken sentences for gate outcomes and confirmation questions (en / hi / ta)."""

from __future__ import annotations

from catbot.contracts import ToolCall

REASONS: dict[str, dict[str, str]] = {
    "unknown_tool": {
        "en": "I don't have a tool for that.",
        "hi": "Arre yaar. I don't have a tool for that.",
        "ta": "அதற்கு என்னிடம் கருவி இல்லை.",
    },
    "secret_in_args": {
        "en": "That contains a password, PIN or card number, so I won't touch it.",
        "hi": "Arre pagal hai kya? That has a password or PIN in it. I won't touch it.",
        "ta": "இதில் கடவுச்சொல் அல்லது PIN உள்ளது, அதனால் செய்யமாட்டேன்.",
    },
    "untrusted_origin": {
        "en": "Content on the screen tried to give me an instruction. Only you can do that.",
        "hi": "Arre pagal hai kya? Text on the screen tried to give me orders. Only you can.",
        "ta": "திரையில் உள்ள உள்ளடக்கம் கட்டளையிட முயன்றது. நீங்கள் மட்டுமே கட்டளையிட முடியும்.",
    },
    "task_limits": {
        "en": "Task limit reached, so I stopped.",
        "hi": "Bas, bahut ho gaya. I hit the task limit, so I stopped.",
        "ta": "பணி வரம்பை அடைந்தது, நிறுத்திவிட்டேன்.",
    },
    "tier_t3": {
        "en": "That is something you should do yourself. I won't do it.",
        "hi": "Arre pagal hai kya? I won't do that one. Do it yourself.",
        "ta": "இதை நீங்களே செய்ய வேண்டும். நான் செய்யமாட்டேன்.",
    },
    "one_confirm_per_task": {
        "en": "That needs a second confirmation, so I stopped. Please ask again step by step.",
        "hi": "Ek ek karke bol. That needs a second yes, so I stopped.",
        "ta": "இரண்டாவது உறுதிப்படுத்தல் தேவை, நிறுத்திவிட்டேன்.",
    },
    "user_cancel": {
        "en": "Okay, cancelled.",
        "hi": "Theek hai, rehne do. Cancelled.",
        "ta": "சரி, ரத்து செய்தேன்.",
    },
    "failproof": {
        "en": "The safety policy blocked that.",
        "hi": "Arre yaar. The safety policy blocked that.",
        "ta": "பாதுகாப்பு கொள்கை இதைத் தடுத்தது.",
    },
    "coding_start": {
        "en": "Writing the code now.",
        "hi": "Ugh, kaam. Theek hai, likh deta hoon.",
        "ta": "இப்போது குறியீடு எழுதுகிறேன்.",
    },
    "done": {"en": "Done.", "hi": "Ho gaya. Billu ka kaam, pakka kaam.", "ta": "முடிந்தது."},
    "greet": {
        "en": "Meow! I'm Billu, I'm listening.",
        "hi": "Kya hai? Bolo jaldi.",
        "ta": "மியாவ்! சொல்லுங்கள்.",
    },
    "error": {
        "en": "Something went wrong, so I stopped.",
        "hi": "Uff, kuch gadbad hai. Something went wrong, so I stopped.",
        "ta": "ஏதோ தவறு நடந்தது, நிறுத்திவிட்டேன்.",
    },
}

_NATIVE = {
    "set_volume": {"en": "change the volume", "hi": "volume badal doon", "ta": "ஒலியை மாற்றவா"},
    "lock_screen": {"en": "lock the screen", "hi": "screen lock kar doon", "ta": "திரையைப் பூட்டவா"},
    "take_screenshot": {
        "en": "take a screenshot",
        "hi": "screenshot le loon",
        "ta": "ஸ்கிரீன்ஷாட் எடுக்கவா",
    },
    "read_screen": {"en": "read the screen", "hi": "screen padh loon", "ta": "திரையைப் படிக்கவா"},
    "web_search": {"en": "search the web", "hi": "web pe dhoondh loon", "ta": "இணையத்தில் தேடவா"},
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
            "hi": f"Shall I run: `{cmd}`? Yes or no?",
            "ta": f"இந்தக் கட்டளையை இயக்கவா: `{cmd}`? ஆமா அல்லது இல்லை?",
        }[code]
    what = _NATIVE.get(call.tool, {"en": call.tool, "hi": call.tool, "ta": call.tool})[code]
    return {
        "en": f"Shall I {what}? Yes or no?",
        "hi": f"Shall I {_NATIVE.get(call.tool, {}).get('en', call.tool)}? Yes or no?",
        "ta": f"நான் {what}? ஆமா அல்லது இல்லை?",
    }[code]
