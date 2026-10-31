import json

from catbot.server.wake import WakeRouter
from tests.test_server import client, done_for, wait  # noqa: F401  (fixture + helpers)


def router(pending=False):
    log = {"tasks": [], "confirms": [], "acks": 0}

    async def ack():
        log["acks"] += 1

    r = WakeRouter(
        has_confirm=lambda: pending,
        resolve_confirm=log["confirms"].append,
        start_task=lambda t, lang: log["tasks"].append((t, lang)),
        ack=ack,
        reply_lang="en-IN",
    )
    return r, log


async def test_wake_with_command_runs_it():
    r, log = router()
    assert await r.on_final("Meow. Turn the volume down.") == "command"
    assert log["tasks"] == [("Turn the volume down.", "en-IN")]


async def test_bare_meow_arms_then_next_sentence_runs():
    r, log = router()
    assert await r.on_final("Meow") == "armed" and log["acks"] == 1 and r.armed
    assert await r.on_final("lock my screen") == "command"
    assert log["tasks"] == [("lock my screen", "en-IN")] and not r.armed


async def test_ambient_speech_ignored():
    r, log = router()
    assert await r.on_final("so what are we having for lunch") == "ignored"
    assert log["tasks"] == []


async def test_confirm_answer_needs_no_wake_word():
    r, log = router(pending=True)
    assert await r.on_final("yes") == "confirm" and log["confirms"] == ["yes"]
    assert await r.on_final("Meow, yes") == "confirm" and log["confirms"][-1] == "yes"


def test_server_wake_mode_end_to_end(client):  # noqa: F811
    state = client.app_state
    with client.websocket_connect("/audio") as ws:
        ws.send_text(json.dumps({"type": "wake", "action": "on"}))
        assert json.loads(ws.receive_text())["type"] == "wake_state"
        ws.send_text(json.dumps({"type": "wake_text", "text": "what is for lunch"}))
        ws.send_text(json.dumps({"type": "wake_text", "text": "Meow"}))
        assert json.loads(ws.receive_text()) == {"type": "wake_ack"}
        ws.send_text(json.dumps({"type": "wake_text", "text": "volume kam karo"}))
        assert wait(lambda: any(e.stage == "done" for e in state.rt.bus.recent))
    finals = [
        e.payload["final"]
        for e in state.rt.bus.recent
        if e.stage == "listen" and "final" in e.payload
    ]
    assert finals == ["volume kam karo"]  # lunch talk never shown
