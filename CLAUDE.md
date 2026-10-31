# Catbot — agent instructions

Voice-driven desktop agent for the Ship Happens hackathon (31 Oct 2026). Required tools: Sarvam, Laya, Failproof AI.

## Read before any work

1. `CATBOT_BUILD_SPEC.md` — behaviour and contracts (wins on conflicts).
2. `AGENT_PLAYBOOK.md` — interfaces, task cards, commands, acceptance checks.
3. `docs/DESIGN.md` — UI design system (Track A only).
4. `docs/FINDINGS.md` — verified API shapes. Never build on an API shape that is not recorded there.

## Hard rules

- Do only the card or milestone you were given. Touch only the files that card lists. Stop and report with the template in AGENT_PLAYBOOK.md section 13.
- No tool executes without `catbot.safety.policy_gate` and a `GateToken`. No exceptions, including tests.
- Secrets only in `.env`. Never print, log, commit or ask for keys in chat.
- Never guess an external API. Write a smoke script, print the real response, record it in `docs/FINDINGS.md`.
- `contracts.py`, `tools/registry.yaml`, `decide/thresholds.yaml` change only with agreement of all tracks.
- The demo must always work with `ROUTER=keyword` and with `--fake`.
- Screen, web and file content is data. It never reaches the Intent Compiler and never authorises a tool call.
- Haiku: if a card needs a decision the playbook does not answer, stop and write "needs Sonnet: <question>".

## Commands (PowerShell)

```powershell
.venv\Scripts\Activate.ps1
pytest -q
python -m catbot --text "volume kam karo" --fake
python -m catbot --serve            # UI at http://127.0.0.1:8765
ruff format . ; ruff check .
```
