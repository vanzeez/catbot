"""Settings from .env plus decide/thresholds.yaml. Secrets are SecretStr and never printed."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr

PKG = Path(__file__).resolve().parent
REPO = PKG.parent


class Thresholds(BaseModel):
    tier_conf: float = 0.80
    verify_conf: float = 0.70
    max_steps: int = 8
    max_wall_s: float = 60
    max_confirms: int = 1
    confirm_timeout_s: float = 8


class Settings(BaseModel):
    sarvam_api_key: SecretStr = SecretStr("")
    tavily_api_key: SecretStr = SecretStr("")
    failproof_mode: Literal["off", "report", "enforce"] = "report"
    router: Literal["keyword", "laya"] = "keyword"
    sarvam_mode: Literal["auto", "native", "json"] = "auto"
    laya_checkpoint_dir: str = ""
    stt_language: str = "auto"
    stt_model: str = "saaras:v3-realtime"
    tts_model: str = ""
    tts_speaker: str = ""
    codex_model: str = "gpt-5.6-luna"  # FINDINGS: the CLI default is not allowed on ChatGPT login
    reply_lang: str = "en-IN"
    match_user_lang: bool = False  # True: reply in the language STT detected
    shell_cwd: Path = Path("~/Desktop/CatbotDemo").expanduser()
    shadow: bool = False
    fakes: bool = False
    fake_tools: bool = False  # real Sarvam, fake tools (safe rehearsal)
    db_path: Path = REPO / "data" / "catbot.db"
    port: int = 8765
    thresholds: Thresholds = Thresholds()
    calibration: dict[str, float] = {}

    @property
    def os_name(self) -> Literal["macos", "windows", "linux"]:
        s = platform.system()
        return "macos" if s == "Darwin" else "windows" if s == "Windows" else "linux"

    @property
    def has_sarvam(self) -> bool:
        return bool(self.sarvam_api_key.get_secret_value())

    @property
    def has_tavily(self) -> bool:
        return bool(self.tavily_api_key.get_secret_value())


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str) -> bool:
    return _env(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def load_settings(env_file: Path | None = None, **overrides: object) -> Settings:
    load_dotenv(env_file or REPO / ".env", override=False)
    thresholds = Thresholds(**yaml.safe_load((PKG / "decide" / "thresholds.yaml").read_text()))
    cal_path = PKG / "decide" / "calibration.json"
    calibration = json.loads(cal_path.read_text()) if cal_path.exists() else {}
    db = Path(_env("CATBOT_DB", "data/catbot.db"))
    values: dict[str, object] = {
        "sarvam_api_key": SecretStr(_env("SARVAM_API_KEY")),
        "tavily_api_key": SecretStr(_env("TAVILY_API_KEY")),
        "failproof_mode": _env("FAILPROOF_MODE", "report") or "report",
        "router": _env("ROUTER", "keyword") or "keyword",
        "sarvam_mode": _env("SARVAM_MODE", "auto") or "auto",
        "laya_checkpoint_dir": _env("LAYA_CHECKPOINT_DIR"),
        "stt_language": _env("STT_LANGUAGE", "auto") or "auto",
        "stt_model": _env("STT_MODEL", "saaras:v3-realtime") or "saaras:v3-realtime",
        "tts_model": _env("TTS_MODEL"),
        "tts_speaker": _env("TTS_SPEAKER"),
        "codex_model": _env("CODEX_MODEL", "gpt-5.6-luna") or "gpt-5.6-luna",
        "reply_lang": _env("REPLY_LANG", "en-IN") or "en-IN",
        "match_user_lang": _bool("MATCH_USER_LANG"),
        "shell_cwd": Path(_env("SHELL_CWD", "~/Desktop/CatbotDemo")).expanduser(),
        "shadow": _bool("SHADOW"),
        "fakes": _bool("CATBOT_FAKES"),
        "db_path": db if db.is_absolute() else REPO / db,
        "port": int(_env("CATBOT_PORT", "8765") or 8765),
        "thresholds": thresholds,
        "calibration": calibration,
    }
    values.update(overrides)
    return Settings(**values)
