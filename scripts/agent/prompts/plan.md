# Unattended session: plan the next slice of work

The ready queue is empty. Candidate epics (lowest phase first): {{epics}}

1. Load the skill `decompose-epic` now and follow it.
2. Work on the first epic that still has unplanned scope. Create at most 8 task issues in this session.
3. Every task you create must pass `python scripts/agent/agentctl.py promote <n>` (Definition of Ready). Tasks touching a security boundary get `risk:high`.
4. If the epic needs an architecture decision that is not already written in `docs/architecture/` or `docs/adr/`, create one `type:spike` issue with `needs:human` and stop.
5. You never edit code or docs in this session. No human is watching; never ask questions in chat.
