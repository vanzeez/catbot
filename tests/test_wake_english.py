import pytest

from catbot.core.prompts import system_prompt
from catbot.core.wake import split_wake
from catbot.tools.shell import scrubbed_env


@pytest.mark.parametrize(
    "text,woke,rest",
    [
        ("Meow. Turn the volume down.", True, "Turn the volume down."),
        ("meow, volume kam karo", True, "volume kam karo"),
        ("Hey meow, what can you do?", True, "what can you do?"),
        ("Meow", True, ""),
        ("meow meow lock my screen", True, "lock my screen"),
        ("Miaow, take a screenshot", True, "take a screenshot"),
        ("म्याऊं आवाज़ कम करो", True, "आवाज़ कम करो"),
        ("turn the volume down", False, "turn the volume down"),
        ("homework is done", False, "homework is done"),
        ("Billu, volume kam kar", True, "volume kam kar"),
        ("Now, turn the volume down.", True, "turn the volume down."),
        ("the cat said meow", False, "the cat said meow"),
    ],
)
def test_split_wake(text, woke, rest):
    assert split_wake(text) == (woke, rest)


async def test_wake_word_prefix_runs_command_in_delhi_hinglish(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("Meow, volume kam karo", lang="en-IN")
    assert out.ok and out.spoken == "Ho gaya, Billu ka kaam pakka kaam. Volume is down."
    assert [e for e in rt.events if e.stage == "speak"][-1].payload["lang"] == "hi-IN"


async def test_billu_wakes_too(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("Billu, volume kam karo")
    assert out.ok and any(e.stage == "execute" for e in rt.events)


async def test_bare_meow_greets(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("meow")
    assert out.ok and out.spoken == "Kya hai? Bolo jaldi."
    assert [e.stage for e in rt.events] == ["speak", "done"]


async def test_english_mode_still_available(make_rt):
    rt = make_rt(reply_lang="en-IN")
    out = await rt.loop.handle("meow")
    assert out.spoken == "Meow! I'm Billu, I'm listening."


async def test_capabilities_answered_without_tools(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("Hey meow, what can you do?")
    assert out.ok and "volume" in out.spoken and not any(e.stage == "execute" for e in rt.events)


async def test_delhi_confirm_question(make_rt):
    rt = make_rt()
    await rt.loop.handle("purani screenshots Trash me daal do")
    q = [e for e in rt.events if e.stage == "confirm" and "question" in e.payload][0]
    assert q.payload["question"].startswith("Shall I run:")  # straight question, no banter


def test_prompt_styles():
    assert "Billu" in system_prompt("macos", "/tmp/x") and "Delhi" in system_prompt(
        "macos", "/tmp/x"
    )
    assert "ONE short English sentence" in system_prompt("macos", "/tmp/x", style="english")
    assert "user's own language" in system_prompt("macos", "/tmp/x", style="match")


def test_npm_launcher_vars_scrubbed(monkeypatch):
    monkeypatch.setenv("npm_config_prefix", "/x")
    monkeypatch.setenv("npm_lifecycle_event", "start")
    env = scrubbed_env()
    assert "npm_config_prefix" not in env and "npm_lifecycle_event" not in env
