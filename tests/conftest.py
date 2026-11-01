import pytest

from catbot.config import load_settings
from catbot.core.confirm import TextConfirm
from catbot.core.events import EventBus
from catbot.core.runtime import build
from catbot.core.store import Store


class SilentSpeaker:
    def __init__(self):
        self.said = []

    async def speak(self, text, lang):
        self.said.append((text, lang))


@pytest.fixture
def make_rt(tmp_path, monkeypatch):
    monkeypatch.setenv("FAILPROOF_MODE", "off")

    def _make(auto="haan", **over):
        over = {"reply_lang": "hi-IN", "match_user_lang": False, **over}
        s = load_settings(
            fakes=True,
            failproof_mode="off",
            router="keyword",
            shadow=False,
            shell_cwd=tmp_path / "demo",
            **over,
        )
        store = Store(":memory:")
        rt = build(
            s, confirm=TextConfirm(auto), speaker=SilentSpeaker(), store=store, bus=EventBus(store)
        )
        rt.events = []
        rt.bus.listen(rt.events.append)
        return rt

    return _make


def stages(events):
    out = []
    for e in events:
        tag = e.stage
        if e.stage == "gate":
            tag += f":{e.payload['verdict']['verdict']}:{e.payload['verdict']['policy']}"
        if e.stage == "execute":
            tag += f":{e.payload['tool']}"
        out.append(tag)
    return out
