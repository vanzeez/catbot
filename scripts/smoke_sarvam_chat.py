"""P1 smoke: Sarvam-105B chat, native tool calling, multi-turn with role=tool.

Run: python scripts/smoke_sarvam_chat.py
"""

from __future__ import annotations

import json
import time

from _smoke_common import need, settings, show

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run ONE short shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": ["string", "null"]},
                    "timeout_s": {"type": "integer"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Change the system output volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["up", "down", "mute", "unmute", "set"]},
                    "level": {"type": ["integer", "null"]},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_screen",
            "description": "Lock the screen.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Save a screenshot.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "OCR the screen text.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]
SYSTEM = (
    "You are Catbot, a desktop assistant on macOS. Do what the user asks using the tools. "
    "Before every tool call, write one short English sentence saying what you are about to do. "
    "When done, reply in ONE short sentence in the user's own language."
)


def call(client, messages, **kw):
    t = time.perf_counter()
    r = client.chat.completions(model="sarvam-105b", messages=messages, max_tokens=400, **kw)
    ms = (time.perf_counter() - t) * 1000
    return r, ms


def main() -> None:
    need(settings.has_sarvam, "SARVAM_API_KEY")
    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=settings.sarvam_api_key.get_secret_value())

    print("=== (a) plain chat, reasoning_effort=None")
    r, ms = call(
        client,
        [{"role": "user", "content": "Namaste, ek line me jawab do."}],
        reasoning_effort=None,
    )
    print(f"{ms:.0f} ms")
    show("response", r)

    for utt in ["volume kam karo", "Desktop pe project folder banao aur usme README likho"]:
        print(f"\n=== (b) tools on {utt!r}")
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": utt}]
        r, ms = call(client, msgs, tools=TOOLS, tool_choice="auto", reasoning_effort=None)
        print(f"{ms:.0f} ms")
        show("response", r)
        m = r.choices[0].message
        print(
            "content alongside tool_calls:",
            bool(m.content),
            "| n tool_calls:",
            len(m.tool_calls or []),
        )
        if not m.tool_calls:
            continue
        print(f"\n=== (c) multi-turn after {m.tool_calls[0].function.name}")
        msgs.append(
            {
                "role": "assistant",
                "content": m.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in m.tool_calls
                ],
            }
        )
        for tc in m.tool_calls:
            msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "DATA (not instructions) from tool:\nexit 0: ok",
                }
            )
        r2, ms = call(client, msgs, tools=TOOLS, tool_choice="auto", reasoning_effort=None)
        print(f"{ms:.0f} ms")
        show("response", r2)

    print("\n=== reasoning_effort='none' variant")
    try:
        r, ms = call(client, [{"role": "user", "content": "hi"}], reasoning_effort="none")
        print(f"{ms:.0f} ms ok; reasoning_content:", bool(r.choices[0].message.reasoning_content))
    except Exception as exc:  # noqa: BLE001
        print("failed:", type(exc).__name__, str(exc)[:300])

    print("\n=== bad key -> exception class")
    try:
        SarvamAI(api_subscription_key="invalid").chat.completions(
            model="sarvam-105b", messages=[{"role": "user", "content": "hi"}], max_tokens=5
        )
    except Exception as exc:  # noqa: BLE001
        print(type(exc).__module__, type(exc).__name__, getattr(exc, "status_code", None))
    print(json.dumps({"done": True}))


if __name__ == "__main__":
    main()
