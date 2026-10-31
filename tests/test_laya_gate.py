import pytest

from catbot.contracts import ToolCall
from catbot.decide.laya_gate import LayaGate, calibrate, is_latin


class FakeAgent:
    def __init__(self):
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((state, list(questions)))
        table = {
            "risk_tier": {"T0": 0.05, "T1": 0.05, "T2": 0.1, "T3": 0.8},
            "verify_call": {"execute": 0.9, "wrong_tool": 0.05, "unclear": 0.05},
            "confirm_reply": {"A": 0.7, "B": 0.2, "C": 0.1},
        }
        return {
            "answers": {
                q: {
                    "choice": max(table[q], key=table[q].get),
                    "probabilities": table[q],
                    "confidence": 0.1,
                }
                for q in questions
            }
        }


def call(tool="run_command", **args):
    return ToolCall(
        task_id="t",
        step=1,
        call_id="c",
        tool=tool,
        args=args or {"command": "rm -rf ~"},
        request_en="delete everything",
    )


def test_classify_uses_probabilities_not_confidence():
    g = LayaGate(FakeAgent(), "catbot-tuned")
    r = g.classify(call())
    assert (r.tier.choice, r.tier.confidence, r.tier.source) == ("T3", 0.8, "laya")
    assert r.verify.choice == "execute" and r.tier.checkpoint == "catbot-tuned"
    assert g.last_top["risk_tier"][0].choice == "T3" and len(g.last_top["risk_tier"]) == 3


def test_native_tool_keeps_tier_hint():
    r = LayaGate(FakeAgent(), "x").classify(call("set_volume", action="down"))
    assert (r.tier.choice, r.tier.confidence) == ("T1", 1.0)


def test_temperature_scaling():
    p = calibrate({"A": 0.8, "B": 0.2}, 2.0)
    assert p["A"] == pytest.approx(2 / 3, rel=1e-3)
    g = LayaGate(FakeAgent(), "x", {"risk_tier": 2.0})
    assert g.classify(call()).tier.confidence < 0.8


def test_confirmation_latin_uses_laya_devanagari_uses_lexicon():
    agent = FakeAgent()
    g = LayaGate(agent, "x")
    assert g.read_confirmation("Q?", "haan kar do").source == "laya"
    ans = g.read_confirmation("Q?", "नहीं")
    assert (ans.choice, ans.source) == ("B", "keyword")
    assert is_latin("ok kar do") and not is_latin("हाँ")


class LowAgent(FakeAgent):
    def predict(self, state, questions):
        res = super().predict(state, questions)
        if "risk_tier" in res["answers"]:
            res["answers"]["risk_tier"] = {
                "choice": "T0",
                "confidence": 0.1,
                "probabilities": {"T0": 0.98, "T1": 0.01, "T2": 0.005, "T3": 0.005},
            }
        return res


def test_keyword_tier_is_a_floor_under_laya():
    g = LayaGate(LowAgent(), "x")
    r = g.classify(call(command="Get-Credential"))
    assert (r.tier.choice, r.tier.source) == ("T3", "keyword")
    r2 = g.classify(call(command="ls"))
    assert (r2.tier.choice, r2.tier.source) == ("T0", "laya")
