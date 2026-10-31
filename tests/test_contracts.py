from catbot.config import load_settings
from catbot.contracts import (
    Answer,
    Event,
    GateToken,
    PolicyVerdict,
    RiskDecision,
    TaskOutcome,
    ToolCall,
    ToolResult,
    max_tier,
)


def test_models_roundtrip():
    call = ToolCall(
        task_id="abc",
        step=1,
        call_id="c1",
        tool="set_volume",
        args={"action": "down"},
        request_en="lower the volume",
    )
    assert call.last_origin == "user" and call.last_origin_flagged is False
    risk = RiskDecision(
        tier=Answer(choice="T1", confidence=1.0, source="keyword"),
        verify=Answer(choice="execute", confidence=0.9, source="keyword"),
        latency_ms=3,
    )
    v = PolicyVerdict(verdict="allow", policy="allow", reason="ok")
    tok = GateToken(call_id=call.call_id, verdict=v)
    assert tok.confirmed is False and v.hard is True
    r = ToolResult(ok=True, summary="done")
    assert r.origin == "command_output"
    e = Event(ts="t", task_id="abc", stage="risk", payload={"tier": risk.tier.model_dump()})
    assert Event.model_validate_json(e.model_dump_json()) == e
    assert Event(ts="t", task_id="x", stage="done").payload == {}
    assert TaskOutcome(task_id="abc", ok=True, spoken="hi").steps == []


def test_max_tier():
    assert max_tier("T1", None, "T2") == "T2"
    assert max_tier(None) == "T0"
    assert max_tier("T3", "T0") == "T3"


def test_settings_hide_secrets(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "sk-should-not-leak")
    s = load_settings()
    assert "sk-should-not-leak" not in repr(s) and "sk-should-not-leak" not in s.model_dump_json()
    assert s.thresholds.tier_conf == 0.80 and s.thresholds.max_steps == 8
    assert s.calibration["risk_tier"] == 1.0
