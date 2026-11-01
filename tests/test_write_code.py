from catbot.contracts import Answer, RiskDecision, ToolCall
from catbot.safety.policy_gate import policy_gate
from catbot.tools.coder import codex_argv

RISK = RiskDecision(
    tier=Answer(choice="T1", confidence=1.0, source="keyword"),
    verify=Answer(choice="execute", confidence=0.9, source="keyword"),
    latency_ms=1,
)


def gate(app_name):
    c = ToolCall(
        task_id="t",
        step=1,
        call_id="c",
        tool="write_code",
        args={"app_name": app_name, "spec": "a counter"},
        request_en="make an app",
    )
    return policy_gate(c, RISK, [], confirms_used=0, elapsed_s=1, utterance_floor=None)


def test_slug_allowed_escape_denied():
    assert gate("chai-counter").verdict == "allow"
    assert gate("../../etc").policy == "bad_app_name"
    assert gate("~/x").policy == "bad_app_name"


def test_codex_argv_is_sandboxed(tmp_path):
    argv = codex_argv(tmp_path / "chai-counter", "a counter", "gpt-5.6-luna")
    assert argv[:2] == ["codex", "exec"] and "workspace-write" in argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in argv


async def test_chai_counter_on_fakes(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("Billu, ek chai counter app bana do")
    said = [e.payload["text"] for e in rt.events if e.stage == "speak"]
    assert out.ok and "Ugh, kaam. Theek hai, likh deta hoon." in said
    assert [c[0] for c in rt.tools.calls] == ["write_code"]
