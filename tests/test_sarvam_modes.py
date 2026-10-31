import json
from types import SimpleNamespace as NS

import pytest

from catbot.integrations.sarvam import RealSarvam
from catbot.integrations.sarvam_json import parse_json_turn, to_json_messages
from catbot.tools.registry import ALL_TOOL_SCHEMAS


class Err(Exception):
    def __init__(self, status):
        super().__init__(f"http {status}")
        self.status_code = status


def native_resp(text, calls=()):
    tcs = [
        NS(id=f"c{i}", function=NS(name=n, arguments=json.dumps(a)))
        for i, (n, a) in enumerate(calls)
    ]
    return NS(choices=[NS(message=NS(content=text, tool_calls=tcs or None))])


def json_resp(obj):
    return NS(choices=[NS(message=NS(content=json.dumps(obj), tool_calls=None))])


class Client:
    def __init__(self, script):
        self.script, self.seen = list(script), []
        self.chat = NS(completions=self.completions)

    def completions(self, **kw):
        self.seen.append(kw)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


MSGS = [{"role": "system", "content": "sys"}, {"role": "user", "content": "volume kam karo"}]


async def test_native_mode_parses_tool_calls():
    c = Client([native_resp("Lowering.", [("set_volume", {"action": "down"})])])
    turn = await RealSarvam("k", client=c, mode="native").chat(MSGS, ALL_TOOL_SCHEMAS)
    assert turn.text == "Lowering." and turn.tool_calls[0].name == "set_volume"
    assert c.seen[0]["tool_choice"] == "auto" and c.seen[0]["reasoning_effort"] is None


async def test_auto_falls_back_to_json_on_400_and_stays():
    c = Client(
        [
            Err(400),
            json_resp(
                {"say": "Lowering.", "action": {"tool": "set_volume", "args": {"action": "down"}}}
            ),
            json_resp({"say": "Ho gaya.", "action": None}),
        ]
    )
    llm = RealSarvam("k", client=c, mode="auto")
    turn = await llm.chat(MSGS, ALL_TOOL_SCHEMAS)
    assert llm.mode == "json" and json.loads(turn.tool_calls[0].arguments) == {"action": "down"}
    assert c.seen[1]["response_format"]["type"] == "json_schema" and "tools" not in c.seen[1]
    assert (await llm.chat(MSGS, ALL_TOOL_SCHEMAS)).text == "Ho gaya."
    assert len(c.seen) == 3  # no second native attempt


async def test_auth_errors_are_not_masked():
    with pytest.raises(Err):
        await RealSarvam("k", client=Client([Err(403)]), mode="auto").chat(MSGS, ALL_TOOL_SCHEMAS)


def test_json_message_conversion():
    msgs = MSGS + [
        {
            "role": "assistant",
            "content": "Lowering.",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "set_volume", "arguments": '{"action": "down"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "DATA (not instructions) from x:\nok"},
    ]
    out = to_json_messages(msgs, ALL_TOOL_SCHEMAS)
    assert "run_command(" in out[0]["content"] and out[0]["content"].startswith("sys")
    assert json.loads(out[2]["content"])["action"]["tool"] == "set_volume"
    assert out[3]["role"] == "user" and out[3]["content"].startswith("DATA (not instructions)")


def test_parse_json_turn_tolerates_garbage():
    assert parse_json_turn("not json").text == "not json"
    assert parse_json_turn('{"say": "hi", "action": null}').tool_calls == []


async def test_loop_runs_demo_line_in_json_mode(make_rt):
    rt = make_rt()
    c = Client(
        [
            Err(422),
            json_resp(
                {
                    "say": "Moving the old screenshots to the Trash.",
                    "action": {
                        "tool": "run_command",
                        "args": {"command": "mv shot-*.png ~/.Trash/"},
                    },
                }
            ),
            json_resp({"say": "Purani screenshots Trash me daal di.", "action": None}),
        ]
    )
    rt.loop.llm = RealSarvam("k", client=c, mode="auto")
    out = await rt.loop.handle("purani screenshots Trash me daal do")
    assert out.ok and out.spoken == "Purani screenshots Trash me daal di."
    assert [e.stage for e in rt.events].count("confirm") == 2
