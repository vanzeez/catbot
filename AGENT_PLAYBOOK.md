# Catbot Agent Playbook — v2 note

v2 replaces the three-track, 54-card v1 playbook. One agent (Opus) builds serially.

1. Behaviour and contracts: `CATBOT_BUILD_SPEC.md` (v2). It wins on any conflict.
2. Rules for the executing agent: spec section 0.
3. Phases P0–P7, hours and acceptance checks: spec section 9.
4. Phase report template: spec section 10. Post it at the end of every phase.
5. Verified external API shapes: `docs/FINDINGS.md`. Never build on a shape not recorded there.
6. Old facts about Sarvam, Laya, Failproof: `docs/SPEC_V1.md` section 3.
7. v1 playbook (interfaces, task cards) kept for reference only: `docs/PLAYBOOK_V1.md`.
8. UI design system: `docs/DESIGN.md` (with the spec 8.2 edits applied in P5).
