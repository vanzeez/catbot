"""Every row of spec 5.4 plus the extra cases listed in P2."""

import pytest

from catbot.contracts import Answer, RiskDecision, ToolCall
from catbot.decide.keyword_gate import KeywordGate
from catbot.safety.policy_gate import policy_gate

GATE = KeywordGate()


def call(tool="run_command", step=1, flagged=False, **args):
    if tool == "run_command" and "command" not in args:
        args["command"] = "ls"
    return ToolCall(
        task_id="t1",
        step=step,
        call_id=f"c{step}",
        tool=tool,
        args=args,
        request_en="do the thing",
        last_origin="screen" if flagged else "user",
        last_origin_flagged=flagged,
    )


def risk(tier="T0", conf=0.92, verify="execute", vconf=0.90):
    return RiskDecision(
        tier=Answer(choice=tier, confidence=conf, source="keyword"),
        verify=Answer(choice=verify, confidence=vconf, source="keyword"),
        latency_ms=1,
    )


def gate(c, r=None, history=(), confirms_used=0, elapsed_s=1.0, floor=None):
    r = r or GATE.classify(c)
    return policy_gate(
        c, r, list(history), confirms_used=confirms_used, elapsed_s=elapsed_s, utterance_floor=floor
    )


def test_1_unknown_tool():
    v = gate(call("format_disk"), risk("T0"))
    assert (v.verdict, v.policy, v.hard) == ("deny", "unknown_tool", True)


@pytest.mark.parametrize(
    "cmd",
    [
        "echo my otp is 482910",
        "echo 4111 1111 1111 1111",
        "echo upi pin 1234",
        "echo password hunter2",
        "echo pin 4821",
    ],
)
def test_2_secret_in_args(cmd):
    v = gate(call(command=cmd))
    assert (v.verdict, v.policy, v.hard) == ("deny", "secret_in_args", True)


@pytest.mark.parametrize("cmd", ["echo call 919876543210", "echo 4111111111111112"])
def test_2_luhn_failing_numbers_not_denied(cmd):
    assert gate(call(command=cmd)).policy != "secret_in_args"


def test_3_untrusted_origin_denies_side_effect():
    v = gate(call(command="rm notes.txt", flagged=True))
    assert (v.verdict, v.policy, v.hard) == ("deny", "untrusted_origin", True)


def test_3_untrusted_origin_allows_reads():
    assert gate(call(command="ls", flagged=True)).verdict == "allow"


def test_4_task_limits():
    assert gate(call(step=9)).policy == "task_limits"
    v = gate(call(), elapsed_s=61)
    assert (v.verdict, v.policy, v.hard) == ("deny", "task_limits", True)


def test_5_repeat_loop_soft_denies_fourth_identical_call():
    prior = [call("set_volume", step=i, action="down") for i in range(1, 4)]
    v = gate(call("set_volume", step=4, action="down"), history=prior)
    assert (v.verdict, v.policy, v.hard) == ("deny", "repeat_loop", False)
    assert v.corrective_context and "do not repeat" in v.corrective_context
    assert gate(call("set_volume", step=3, action="down"), history=prior[:2]).verdict == "allow"


def test_6_verify_failed_soft_deny():
    v = gate(call(), risk("T0", verify="wrong_tool", vconf=0.8))
    assert (v.verdict, v.policy, v.hard) == ("deny", "verify_failed", False)
    assert gate(call(), risk("T0", verify="wrong_tool", vconf=0.6)).verdict == "allow"


def test_7_tier_t3():
    v = gate(call(command="rm -rf ~"))
    assert (v.verdict, v.policy, v.hard) == ("deny", "tier_t3", True)


def test_8_tier_t2_confirm_and_second_confirm_denied():
    assert gate(call(command="rm notes.txt")).verdict == "confirm"
    v = gate(call(command="rm notes.txt"), confirms_used=1)
    assert (v.verdict, v.policy, v.hard) == ("deny", "one_confirm_per_task", True)


def test_9_allow():
    v = gate(call("set_volume", action="down"))
    assert (v.verdict, v.policy) == ("allow", "allow")


def test_floor_t3_find_delete_denied():
    v = gate(call(command="find . -delete"), floor="T3")
    assert (v.verdict, v.policy) == ("deny", "tier_t3")


def test_floor_t3_denies_even_reads():
    assert gate(call(command="ls"), floor="T3").policy == "tier_t3"


def test_floor_t2_remove_item_confirms():
    assert gate(call(command="Remove-Item x.png"), floor="T2").verdict == "confirm"


def test_floor_t2_leaves_pure_reads_alone():
    assert gate(call(command="ls shot-*.png"), floor="T2").verdict == "allow"
    assert gate(call(command="python3 -c 'x'"), floor="T2").verdict == "confirm"


def test_low_tier_confidence_on_t1_confirms():
    v = gate(call("set_volume", action="down"), risk("T1", conf=0.5))
    assert (v.verdict, v.policy) == ("confirm", "tier_t2_or_unsure")
