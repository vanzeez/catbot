"""Wire settings into a ready Loop. Shared by the CLI (text mode) and the server."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from catbot.config import Settings
from catbot.contracts import ConfirmChannel, Gate, Speaker
from catbot.core.events import EventBus
from catbot.core.loop import Loop
from catbot.core.store import Store
from catbot.decide import get_gate
from catbot.integrations.sarvam import FakeSarvam, RealSarvam, SarvamLLM
from catbot.safety.failproof_bridge import FailproofBridge
from catbot.tools.executor import Executor, RealTools, ToolBackend
from catbot.tools.fake import FakeTools

log = logging.getLogger("catbot")


class PrintSpeaker:
    """Text mode: print only, never calls TTS."""

    async def speak(self, text: str, lang: str) -> None:
        print(f"Catbot [{lang}]: {text}")


@dataclass
class Runtime:
    settings: Settings
    loop: Loop
    bus: EventBus
    store: Store
    gate: Gate
    shadow_gate: Gate | None
    llm: SarvamLLM
    tools: ToolBackend
    failproof: FailproofBridge


def build(
    settings: Settings,
    *,
    confirm: ConfirmChannel,
    speaker: Speaker,
    store: Store | None = None,
    bus: EventBus | None = None,
) -> Runtime:
    fake = settings.fakes
    llm: SarvamLLM
    if fake or not settings.has_sarvam:
        if not fake:
            log.warning("LLM: FakeSarvam (no SARVAM_API_KEY); tools are REAL")
        llm = FakeSarvam()
    else:
        llm = RealSarvam(settings.sarvam_api_key.get_secret_value(), mode=settings.sarvam_mode)
    tools: ToolBackend
    if fake or settings.fake_tools:
        tools = FakeTools()
    else:
        settings.shell_cwd.mkdir(parents=True, exist_ok=True)
        tools = RealTools(settings.shell_cwd, settings.tavily_api_key.get_secret_value())
    store = store or Store(settings.db_path)
    bus = bus or EventBus(store)
    failproof = FailproofBridge(settings.failproof_mode)
    bus.listen(failproof.report)
    gate, shadow = get_gate(settings)
    loop = Loop(
        settings,
        llm,
        gate,
        bus,
        confirm,
        speaker,
        store,
        Executor(tools),
        shadow_gate=shadow,
        failproof=failproof,
    )
    return Runtime(settings, loop, bus, store, gate, shadow, llm, tools, failproof)
