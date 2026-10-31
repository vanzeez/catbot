import pytest

from catbot.contracts import GateToken, PolicyVerdict, ToolCall
from catbot.safety.policy_gate import issue_token
from catbot.tools.executor import Executor
from catbot.tools.fake import FakeTools

CALL = ToolCall(
    task_id="t",
    step=1,
    call_id="x1",
    tool="run_command",
    args={"command": "ls"},
    request_en="list files",
)
ALLOW = PolicyVerdict(verdict="allow", policy="allow", reason="ok")
CONFIRM = PolicyVerdict(verdict="confirm", policy="tier_t2_or_unsure", reason="ask")


async def test_no_token_raises():
    with pytest.raises(PermissionError):
        await Executor(FakeTools()).execute(CALL, None)


async def test_forged_token_raises():
    with pytest.raises(PermissionError):
        await Executor(FakeTools()).execute(CALL, GateToken(call_id="x1", verdict=ALLOW))


async def test_issued_token_runs_once():
    ex = Executor(FakeTools())
    tok = issue_token(CALL, ALLOW)
    argv, res = await ex.execute(CALL, tok)
    assert res.ok and argv[-1] == "ls"
    with pytest.raises(PermissionError):
        await ex.execute(CALL, tok)


async def test_token_for_other_call_rejected():
    other = CALL.model_copy(update={"call_id": "x2"})
    tok = issue_token(other, ALLOW)
    with pytest.raises(PermissionError):
        await Executor(FakeTools()).execute(CALL, tok)


def test_no_token_for_deny_or_unconfirmed():
    with pytest.raises(PermissionError):
        issue_token(CALL, PolicyVerdict(verdict="deny", policy="tier_t3", reason="no"))
    with pytest.raises(PermissionError):
        issue_token(CALL, CONFIRM)
    assert issue_token(CALL, CONFIRM, confirmed=True).confirmed
