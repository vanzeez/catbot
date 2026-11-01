# Catbot

A voice-driven desktop agent for Hindi, Hinglish, Tamil and English speakers. Built for the Ship Happens hackathon (31 Oct 2026) with **Sarvam**, **Laya** and **Failproof AI**.

Meet **Billu**, the cat who runs it. Say "meow" (or "Billu") and then "volume kam karo". Billu talks back in Delhi-style Hinglish, in Bulbul's `ratan_hi_social` voice. Sarvam transcribes it, Sarvam-105B decides what to do, a safety gate reviews every single action, the action runs, and Bulbul answers you out loud.

## How it works

```text
 mic ──► Sarvam STT (saaras realtime) ──► utterance ──► utterance floor (T2/T3 words light the panel red)
                                                │
                    ┌───────────────────────────▼───────────────────────────┐
                    │  ReAct loop (max 8 steps · 60 s · 1 confirmation)     │
                    │  Sarvam-105B native tool call ──► risk: Laya / keyword │
                    │        ▲                         ──► policy_gate       │
                    │        │                              allow │ confirm │ deny
                    │  "DATA (not instructions)"            │       │ ask   └► spoken reason
                    │        └──── tool result ◄── executor (GateToken only)  │
                    └───────────────────────────┬───────────────────────────┘
                                                ▼
                                   Bulbul TTS ──► speaker   (barge-in stops it)
```

Six tools: `run_command` (one shell command in `SHELL_CWD`), `set_volume`, `lock_screen`, `take_screenshot`, `read_screen`, `web_search`.

Every tool call passes `policy_gate` and needs a single-use `GateToken`; the executor raises without one. Tiers: T0 reads, T1 easy to undo, T2 hard to undo (asks you first), T3 destructive or touches money and credentials (never runs). Text from the screen, the web or command output is data: if it contains instructions, any non-read action after it is denied.

## Where each sponsor tool is used

| Tool | Use |
| --- | --- |
| **Sarvam** | Sarvam-105B runs the tool-calling loop (`catbot/integrations/sarvam.py`). Saaras realtime STT and Bulbul v4 Flash TTS power the voice path (`catbot/integrations/sarvam_audio.py`). Sarvam also generates fine-tune data when a key is present (`data/gen_laya_data.py --source sarvam`). |
| **Laya** | A checkpoint fine-tuned for Catbot answers three typed decisions on every step: `risk_tier`, `verify_call`, `confirm_reply` (`catbot/decide/laya_gate.py`), in about 50 ms. Training data comes from Sarvam (`data/gen_laya_data.py`); every decision and every UI correction is logged for retraining. |
| **Failproof AI** | Every event is mirrored into Failproof through `failproofai-sdk` (tool use, tool result, gate decision, human confirmation, task end) in `catbot/safety/failproof_bridge.py`. |

## Honest status

- **Laya decides, with a regex safety floor.** A Laya checkpoint fine-tuned on this Mac (`data/finetune_local.py`, 49 min) passes every bar on held-out data: risk tier 0.985, verify 0.969, confirm reply 0.927 (`docs/EVAL.md`). It still under-tiers some dangerous commands (credential reads, `curl … | sh`), so the keyword tier stays as a floor: Laya can raise risk, never lower it. The checkpoint is gitignored; without it, set `ROUTER=keyword` (and `SHADOW=1` to show zero-shot Laya beside it).
- **Failproof reports, it does not gate.** Its docs say the SDK for custom agents "does not enforce policies on its own" (`docs/FINDINGS.md`). Catbot writes every event to the Failproof spool; seeing them in Failproof Cloud needs `failproofai config` (sudo plus a browser login).
- **Sarvam is verified live** (31 Oct): native multi-turn tool calling, Saaras realtime STT with push-to-talk, and Bulbul v4 Flash TTS. `scripts/demo.py` passed 3× in a row on real Sarvam and real tools, and a full voice round trip (speech in, action, spoken reply) took about 4.3 s. Details in `docs/FINDINGS.md`.
- **Line 2 is usually 2 steps, not always.** Sarvam sometimes chains `mkdir … && echo … > README.md` into one command; the result is the same and the gate scores every chained part.
- **Untested on Windows.** The Windows paths (PowerShell argv, `pycaw` volume, `rundll32` lock) are written and unit-tested for their argv only.
- **Web search is off** (no `TAVILY_API_KEY`); `web_search` returns a clean error.

## Setup

macOS:

```bash
uv venv && uv pip install -e ".[dev,laya]"
cp .env.example .env            # then fill SARVAM_API_KEY and TAVILY_API_KEY
npm --prefix electron install
```

Windows (PowerShell):

```powershell
uv venv ; uv pip install -e ".[dev,win32,laya]"
copy .env.example .env
npm --prefix electron install
```

macOS notes: `lock_screen` uses `pmset displaysleepnow`, which only locks if System Settings › Lock Screen asks for the password immediately. `read_screen` needs Screen Recording permission, and the mic needs Microphone permission for Electron (asked once).

## Run

```bash
python -m catbot --text "volume kam karo" --fake     # text mode, fake Sarvam and fake tools
python -m catbot --serve --voice                     # server + UI at http://127.0.0.1:8765
./scripts/start_catbot.sh                            # desktop app (own mic/screen permissions; logs in data/catbot.log)
npm --prefix electron start                          # same app, but inherits the terminal's macOS permissions
CATBOT_VIEW=billu ./scripts/start_catbot.sh          # simple Billu mode: just the cat, no technical cards
pytest -q
```

Useful flags: `--yes` / `--no` auto-answer confirmations, `--router keyword|laya`, `--lang hi-IN`. Electron passes extra sidecar flags from `CATBOT_SIDECAR_ARGS`, for example `--fake`.

## Demo

```bash
python scripts/demo.py --runs 3      # with the server running; seeds SHELL_CWD first
```

The four lines are in `docs/DEMO.md`.

## Repo map

`catbot/core` loop, events, store, confirm · `catbot/decide` keyword and Laya gates · `catbot/safety` policy gate, patterns, provenance, Failproof · `catbot/tools` registry, executor, real and fake tools · `catbot/server` FastAPI and voice · `catbot/ui` the UI · `electron/` desktop shell · `data/` Laya data, fine-tune and eval · `scripts/` smoke tests, seed, demo.

Spec: `CATBOT_BUILD_SPEC.md`. API facts: `docs/FINDINGS.md`. Design: `docs/DESIGN.md`.
