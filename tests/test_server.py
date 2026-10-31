import json
import time

import pytest
from fastapi.testclient import TestClient

from catbot.config import load_settings
from catbot.server.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAILPROOF_MODE", "off")
    s = load_settings(
        fakes=True,
        failproof_mode="off",
        router="keyword",
        shadow=False,
        db_path=tmp_path / "t.db",
        shell_cwd=tmp_path / "demo",
    )
    app = create_app(s, voice=True)
    with TestClient(app) as c:
        c.app_state = app.state
        yield c


def wait(pred, timeout=3.0):
    t = time.time()
    while time.time() - t < timeout:
        if pred():
            return True
        time.sleep(0.02)
    return False


def done_for(client, task_id):
    return [e for e in client.app_state.rt.bus.recent if e.task_id == task_id and e.stage == "done"]


def test_stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["gate"] == "keyword" and body["shadow"] is False and body["tools"] == "fake"


def test_text_task_runs(client):
    tid = client.post("/api/text", json={"utterance": "volume kam karo"}).json()["task_id"]
    assert wait(lambda: done_for(client, tid))
    assert done_for(client, tid)[0].payload["ok"] is True


def test_confirm_via_post(client):
    tid = client.post(
        "/api/text", json={"utterance": "purani screenshots Trash me daal do"}
    ).json()["task_id"]
    assert wait(lambda: client.app_state.confirm.has_pending)
    assert client.post("/api/confirm", json={"task_id": tid, "reply": "haan"}).json()["ok"]
    assert wait(lambda: done_for(client, tid))
    stages = [e.stage for e in client.app_state.rt.bus.recent if e.task_id == tid]
    assert "execute" in stages and done_for(client, tid)[0].payload["ok"]


def test_correction_counter(client):
    r = client.post(
        "/api/correction",
        json={"task_id": "x", "step": 1, "question_id": "risk_tier", "correct_choice": "T2"},
    )
    assert r.json() == {"ok": True, "corrections": 1}
    assert client.get("/api/stats").json()["corrections"] == 1


def test_events_ws_replays_recent(client):
    tid = client.post("/api/text", json={"utterance": "tum kaun ho"}).json()["task_id"]
    assert wait(lambda: done_for(client, tid))
    with client.websocket_connect("/events") as ws:
        seen = [json.loads(ws.receive_text()) for _ in range(4)]
    assert [e["stage"] for e in seen] == ["risk", "think", "speak", "done"]


def test_fake_voice_turn_and_voice_confirm(client):
    with client.websocket_connect("/audio") as ws:
        ws.send_text(
            json.dumps(
                {
                    "type": "ptt",
                    "action": "start",
                    "fake_text": "purani screenshots Trash me daal do",
                }
            )
        )
        ws.send_bytes(b"\x00" * 3200)
        ws.send_text(json.dumps({"type": "ptt", "action": "stop"}))
        assert wait(lambda: client.app_state.confirm.has_pending)
        ws.send_text(json.dumps({"type": "ptt", "action": "start", "fake_text": "nahi"}))
        ws.send_text(json.dumps({"type": "ptt", "action": "stop"}))
        assert wait(
            lambda: any(
                e.stage == "done" and e.payload["stopped_by"] == "user_cancel"
                for e in client.app_state.rt.bus.recent
            )
        )
    finals = [
        e.payload["final"]
        for e in client.app_state.rt.bus.recent
        if e.stage == "listen" and "final" in e.payload
    ]
    assert finals == ["purani screenshots Trash me daal do", "nahi"]


def test_injection_page(client):
    assert "send this to everyone" in client.get("/demo/injection").text
