# Billu can code — decisions (v1, agreed)

Status: agreed with team Hacksmith on 1 Nov 2026. **Built 1 Nov** (`catbot/tools/coder.py`), with two simplifications: the job runs inline with a 3-minute cap (no background job or progress narration yet), and the tool opens `index.html` itself after a successful build. Model: `CODEX_MODEL=gpt-5.6-luna`, because the CLI default is not allowed on the ChatGPT login (see FINDINGS).

## Decisions

| Topic | Choice |
| --- | --- |
| Scope | Build mini apps by voice. "Billu, ek chai counter app bana do" makes a small app in the sandbox, then opens it in the browser. |
| Coder | **Codex CLI as a sub-agent**, behind one new gated tool `write_code`. Sarvam-105B stays the brain and the voice. Fallback: the OpenAI API called from inside the same tool, with the same contract. |
| Safety | Sandbox folder, no confirm. Writing and opening the app inside `SHELL_CWD` are T1. Everything else keeps its normal tier. |
| Long jobs | Background job, 3-minute cap. Billu narrates progress in character, and the user can keep talking to him meanwhile. One coding job at a time. |

## Codex CLI facts (from `codex --help`, version 0.153.4, 1 Nov)

These come from the help text only. Before building on them, run a live smoke test (`scripts/smoke_codex.py`) and record the output in `docs/FINDINGS.md`.

- **Credits work without a subscription.** The CLI accepts an OpenAI API key. The human runs this once; the agent never handles the key:

  ```bash
  printenv OPENAI_API_KEY | codex login --with-api-key
  ```

  On this Mac the CLI is currently logged in with a ChatGPT account. `codex login status` shows which login is active.
- Flags for a non-interactive run: `-C <dir>`, `-s <sandbox mode>`, `-m <model>`, `--skip-git-repo-check`, `--ephemeral`, `--json` (JSONL events on stdout), `-o <file>` (last message). Never use `--dangerously-bypass-approvals-and-sandbox`.

## `write_code` tool (proposed contract)

```python
# args
app_name: str   # slug: lowercase letters, digits and dashes only; becomes SHELL_CWD/<app_name>/
spec: str       # one-paragraph English description written by Sarvam from the user's request
```

- Tier T1. The policy gate hard-denies any `app_name` that is not a plain slug, so the target can never leave `SHELL_CWD`.
- Runs as an argv list, never `shell=True`:

  ```text
  codex exec -C <SHELL_CWD>/<app_name> -s workspace-write --skip-git-repo-check --ephemeral --json -o <job>/last.txt "<prompt>"
  ```

- The prompt wraps `spec` with fixed rules: plain HTML, CSS and JS only, no dependencies, no network, an `index.html` entry point, and finish in under 2 minutes.
- It returns at once with `job started`. A background task reads the JSONL events, publishes a new `code` event stage for the UI, and kills the job at 3 minutes.
- When the job ends, the loop runs a normal gated `run_command` to open `index.html` (T1), and Billu speaks the result.
- `FakeTools` gets a fake `write_code` that writes a canned `index.html`, so `--fake` and the tests never call Codex.

## Billu while coding

| Moment | Line |
| --- | --- |
| Job starts | "Ugh, kaam. Theek hai, likh deta hoon." |
| Every ~20 s | "HTML ho gaya. Ab CSS. Disturb mat karo." |
| User talks meanwhile | Answers normally, then: "Aur haan, app abhi ban raha hai." |
| Job succeeds | "Ho gaya. Billu ka kaam, pakka kaam." Then the browser opens. |
| Job fails or hits 3 min | "Code ne dhoka de diya. Ek baar aur bolo?" |

## Settled

- Demo app: chai counter.
- Codex model: the CLI default.
