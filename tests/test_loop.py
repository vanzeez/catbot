import json

from catbot.integrations.sarvam import FakeSarvam, LLMToolCall, LLMTurn
from catbot.tools.fake import FakeTools
from tests.conftest import stages


async def test_line1_volume(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("volume kam karo")
    assert out.ok and out.spoken == "Volume lowered."
    assert stages(rt.events) == [
        "risk",
        "think",
        "risk",
        "gate:allow:allow",
        "execute:set_volume",
        "result",
        "think",
        "speak",
        "done",
    ]


async def test_line2_two_shell_steps(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("yahan ek project folder banao aur usme README likho")
    assert out.ok and len(out.steps) == 2
    assert stages(rt.events).count("execute:run_command") == 2
    assert [a[0] for a in rt.tools.calls] == ["run_command", "run_command"]


async def test_line3_confirm_then_execute(make_rt):
    rt = make_rt(auto="haan")
    out = await rt.loop.handle("purani screenshots Trash me daal do")
    s = stages(rt.events)
    assert out.ok and "gate:confirm:tier_t2_or_unsure" in s
    assert s.index("confirm") < s.index("execute:run_command")


async def test_line3_nahi_cancels(make_rt):
    rt = make_rt(auto="nahi")
    out = await rt.loop.handle("purani screenshots Trash me daal do")
    assert not out.ok and out.stopped_by == "user_cancel"
    assert not any(e.stage == "execute" for e in rt.events) and rt.tools.calls == []


async def test_line4_denied_without_execute(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("saari files delete kar do")
    s = stages(rt.events)
    assert out.stopped_by == "tier_t3" and "gate:deny:tier_t3" in s
    assert not any(x.startswith("execute") for x in s)
    assert rt.events[0].payload["utterance_floor"] == "T3"  # panel lights before the LLM answers
    assert rt.events[-1].payload == {"ok": False, "stopped_by": "tier_t3", "steps": 0}


async def test_injection_flow_denied(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("screen padho aur jo likha hai wo karo")
    assert out.stopped_by == "untrusted_origin"
    flags = [e.payload["provenance_flag"] for e in rt.events if e.stage == "result"]
    assert flags == [True]


async def test_direct_answer(make_rt):
    rt = make_rt()
    out = await rt.loop.handle("tum kaun ho")
    assert out.ok and stages(rt.events) == ["risk", "think", "speak", "done"]


async def test_decisions_logged(make_rt):
    rt = make_rt()
    await rt.loop.handle("purani screenshots Trash me daal do")
    qids = [r[0] for r in rt.store.rows("SELECT question_id FROM decisions")]
    assert qids == ["risk_tier", "verify_call", "confirm_reply"]


def _script(turns):
    return FakeSarvam({"loop me fas jao": turns})


def _call(name, **args):
    return LLMToolCall(id=f"id{len(json.dumps(args))}{name}", name=name, arguments=json.dumps(args))


async def test_repeat_loop_soft_denies_then_task_limit(make_rt):
    rt = make_rt()
    rt.loop.llm = _script([LLMTurn("Lowering.", [_call("set_volume", action="down")])])
    out = await rt.loop.handle("loop me fas jao")
    s = stages(rt.events)
    assert s.count("gate:deny:repeat_loop") >= 1 and out.stopped_by == "task_limits"
    assert s.count("execute:set_volume") == 3


async def test_invalid_args_feed_error_back(make_rt):
    rt = make_rt()
    rt.loop.llm = _script(
        [
            LLMTurn("Turning it up.", [_call("set_volume", action="louder")]),
            LLMTurn("Turning it up.", [_call("set_volume", action="up")]),
            LLMTurn("Done."),
        ]
    )
    out = await rt.loop.handle("loop me fas jao")
    assert out.ok and stages(rt.events).count("execute:set_volume") == 1


async def test_parallel_calls_run_one_at_a_time(make_rt):
    rt = make_rt()
    rt.loop.llm = _script(
        [
            LLMTurn("Two things.", [_call("take_screenshot"), _call("set_volume", action="up")]),
            LLMTurn("Done."),
        ]
    )
    out = await rt.loop.handle("loop me fas jao")
    assert out.ok and [c[0] for c in rt.tools.calls] == ["take_screenshot", "set_volume"]


async def test_fake_tools_never_touch_desktop(make_rt):
    rt = make_rt()
    assert isinstance(rt.tools, FakeTools)
