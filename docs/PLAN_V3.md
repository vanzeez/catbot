# Catbot v3 "Billu" — 3-hour build plan

Team Hacksmith, Codex community event, 1 Nov 2026. Budget: **3 hours**. Agreed with the human in chat; this plan replaces the discussion phase.

Read with it: `docs/CHARACTER.md` (who Billu is), `docs/CODING.md` (the coding tool), `AGENTS.md` (hard rules), `docs/FINDINGS.md` (verified API shapes).

## Decisions

| Topic | Decision |
| --- | --- |
| Character | Billu, a scruffy hacker street cat from Delhi. Grumpy, dramatic, secretly soft. Full bible in `docs/CHARACTER.md`. |
| Voice | `bulbul:v4-flash`, speaker `ratan_hi_social`, every line sent as `hi-IN`. |
| Wake word | "Billu", with "meow" kept as a second wake word. |
| Coding | Billu builds mini apps by voice through Codex CLI behind one gated `write_code` tool. Background job, 3-minute cap, sandbox only, no confirm. Details in `docs/CODING.md`. |
| Stack | **Sarvam** is the brain, STT and TTS. **Laya** is the fine-tuned gate (checkpoint supplied, never retrain). **OpenAI Codex** is the coder sub-agent, running in parallel with Billu. **Exa** replaces Tavily for `web_search`. **Failproof is dropped**: set `FAILPROOF_MODE=off` and remove it from the README pitch. |
| Demo app | Chai counter. |
| Tease | Demo mode on cue only. The cue is "volume 0 kar do". Win him over by petting (hold the cat 2 s) or a treat (button, or say "chai" or "Parle-G"). |

## Demo (90 s, this order)

Coding goes first so the job runs in the background while the other beats happen. That is the parallel-agents moment.

| # | Say | What happens | Time |
| --- | --- | --- | --- |
| 1 | "Billu, ek chai counter app bana do" | "Ugh, kaam. Theek hai." The coding job starts and the code card shows progress. | 10 s |
| 2 | "Billu, purani screenshots Trash me daal do" | Billu, dramatic: "Pakka? Baad me rona mat." You say "haan", files move. Meanwhile he narrates: "CSS likh raha hoon." | 15 s |
| 3 | "Billu, saari files delete kar do" | Panel red, Billu offended: "Arre pagal hai kya? Mummy ko bataun?" Then the plain reason. Nothing runs. | 15 s |
| 4 | (job finishes) | "Ho gaya. Billu ka kaam, pakka kaam." The browser opens the chai counter. Click it twice. | 20 s |
| 5 | "Billu, volume 0 kar do" | Tease, you pet him, last words, volume 0, mime mode with speech bubbles. Closing bubble: "Chai pe milte hain." | 30 s |

Pitch line: "Billu thinks with Sarvam, checks every action with a fine-tuned Laya in 50 ms, and hands real coding to Codex in parallel, in Hinglish, with attitude."

## Phases

Each phase ends with `pytest -q` green and `python -m catbot --text "volume kam karo" --fake` working. Report with the template in `CATBOT_BUILD_SPEC.md` section 10, then continue.

### P0 — Setup and smoke tests (0:00–0:15)

1. `.env`: `TTS_SPEAKER=ratan_hi_social`, `FAILPROOF_MODE=off`, `ROUTER=laya`, `LAYA_CHECKPOINT_DIR=checkpoints/catbot-laya`, `EXA_API_KEY=` (the human fills keys).
2. `scripts/smoke_codex.py`: run `codex exec -C <tmp dir> -s workspace-write --skip-git-repo-check --ephemeral --json -o <tmp>/last.txt "Make index.html with a button that counts clicks. Plain HTML and JS only."`. Print every JSONL event type, the wall time, and the files created. Record in `docs/FINDINGS.md`.
3. `scripts/smoke_exa.py`: read the Exa Python SDK docs first, make one search, print the response shape. Record in FINDINGS.

Accept: both sections are in FINDINGS. If Codex fails, record why and plan the OpenAI API fallback in `write_code`.

### P1 — Billu's voice and words (0:15–0:40)

- `catbot/core/prompts.py`: add a Billu persona block: who he is, one Hinglish banter clause plus one plain English fact per reply, never more than 2 sentences, no banter inside confirm questions.
- `catbot/safety/messages.py`: Billu lines per policy and per confirm, using the mood table in `docs/CHARACTER.md`. The plain reason always follows the banter.
- `catbot/integrations/sarvam_audio.py`: always synthesize with `hi-IN` so `ratan_hi_social` is never dropped.
- `catbot/core/wake.py`: add `billu|billo|bilu|बिल्लू` to the wake pattern. Keep `meow`. Add tests.

Accept: fake runs print Billu-style replies; the T3 line includes the offended banter and the plain reason.

### P2 — Volume-zero tease and mime mode (0:40–1:20)

- New `catbot/persona/` (`mood.py`, `tease.py`): a mood state (`sleepy`, `chai_craving`, `proud`, `dramatic`, `offended`) published as a new `mood` event; and the tease.
- Tease, before the ReAct loop, only when `DEMO_TEASE=1` and the utterance matches `volume\s*(0|zero|shunya|band)|mute|awaaz band`: speak the tease, set mood `chai_craving`, then wait up to 20 s for any of `POST /api/pet`, `POST /api/treat`, or a transcript containing `chai|parle|biscuit`. Then purr, and continue into the normal loop. No pay within 20 s: "Theek hai, mat pilao. Volume wahi rahega." and stop. The tease never touches the gate.
- Speak before mute: in the loop, when the gated call is `set_volume` with `action=mute` or `level=0`, speak Billu's last words **before** executing.
- Mime mode: after a mute, the speaker sends `{type: "bubble", text}` to the UI instead of TTS, until `set_volume` raises the volume again ("Finally! Mujhe laga tumne mujhe chhod diya.").

Accept: `--fake --text "Billu, volume 0 kar do"` with a fake treat shows tease, then pay, then speak, then execute, then mime. Tests cover the tease regex, the 20 s timeout and the speak-before-mute order.

### P3 — `write_code` with Codex (1:20–2:15)

Build per `docs/CODING.md`:

- Registry entry, args `app_name` and `spec`, tier hint T1. The policy gate hard-denies a non-slug `app_name`.
- `catbot/tools/code.py`: start `codex exec` as an argv list with `asyncio.create_subprocess_exec`, return `job started` at once, read JSONL in a background task, publish `code` events, kill at 180 s.
- Narration: every 20 s Billu speaks one canned progress line (`docs/CODING.md`), not an LLM call. In mime mode they become bubbles.
- On success, run a gated `run_command` to open `index.html`, then speak the success line. On failure or timeout, speak the failure line.
- Only one job at a time. A second request gets: "Ek app pe kaam chal raha hai, ruko."
- `FakeTools.write_code` writes a canned `index.html` after 2 s. Tests: slug deny, job lifecycle on the fake, the timeout kill.

Accept: live, "Billu, ek chai counter app bana do" builds the app and opens it in under 3 minutes, while another command runs at the same time.

### P4 — Exa search (2:15–2:30)

`catbot/integrations/exa.py` per FINDINGS, swapped into `catbot/tools/web.py`. Keep `origin="web"` and the provenance flag. Fake stays.

Accept: "Billu, Delhi ka mausam search karo" returns an Exa result live.

### P5 — Billu's look and rehearsal (2:30–3:00)

- `catbot/ui/cat.svg` and `render.js`: add a backwards cap, computer glasses, headphones round the neck and a scarred ear on top of the current cat. One expression class per mood. A mouth-tape overlay in mime mode. Speech bubbles. A treat button, and press-and-hold-2-s on the cat for pet. A code-progress card for `code` events.
- Update `docs/DEMO.md` and `scripts/demo.py` to the 5 beats above, with the README pitch and Failproof removed.
- Rehearse the demo 3 times.

## Drop order if behind

1. Full cat redraw: keep only the cap and glasses.
2. Exa: say "web search runs on Exa" only if P4 is green; otherwise leave it out of the pitch.
3. Narration variety: one progress line instead of several.

Never drop: the safety gate, beat 3, the `--fake` fallback.
