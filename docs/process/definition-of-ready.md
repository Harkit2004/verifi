# Definition of Ready (issue format)

An issue may carry `agent:ready` only if `python scripts/agent/agentctl.py promote <n>` accepts it. Write
issues so that **a literal-minded, weaker model** can finish them without guessing.

## Task body template (exact section order)

```markdown
## Context
Why this exists, in 2-5 sentences. Link the epic and relevant ADRs.

## Goal
One sentence: the observable behavior after this issue.

## Read first
- docs/architecture/interfaces.md § <section>
- docs/architecture/<doc>.md § <section>
- src/verifi/<closest existing example>.py (once it exists)

## Tests to write first
- `tests/unit/<area>/test_<module>.py::test_<behavior>`: <what it asserts>
- ... (every acceptance criterion maps to at least one test)

## Implementation notes
- Create `src/verifi/<area>/<module>.py` with <names from interfaces.md>.
- Register operation `<name>` in `src/verifi/<area>/operations.py` (if user-facing).
- Constraints, edge cases, algorithms (reference docs; don't restate them differently).

## Acceptance criteria
- [ ] <observable, testable statement>
- [ ] `python scripts/verify.py` passes

## Out of scope
- <tempting adjacent work that belongs to other issues (#refs)>

## Verification
```bash
uv run pytest -q tests/unit/<area>
uv run verifi <group> <verb> ... --json   # expected: ok=true, data.<field> == ...
python scripts/verify.py
```

<!-- verifi-agent
phase: <0-4>
seq: <int, unique within phase, dependency order>
depends-on: <#n, #m or empty>
risk: <low|high>
size: <s|m>
epic: <#n>
-->
```

## Checklist

- [ ] Exactly one `type:*`, one `risk:*`, one `size:*`, one `phase:*`, ≥1 `area:*` label; milestone set.
- [ ] Metadata block present with phase and seq; `depends-on` lists only issues that must be *merged* first.
- [ ] Every acceptance criterion is observable and has a named test.
- [ ] Module paths and public names match `docs/architecture/interfaces.md` (or the issue explicitly adds a field).
- [ ] No step needs network, secrets, paid APIs, or a human decision.
- [ ] Size: s ≤ 150 changed lines, m ≤ 400. Otherwise split.
- [ ] Tests needing Docker are marked `docker`, and the issue says so in Verification.

## Risk rules

`risk:high` if the change touches: sandbox provider settings or network modes, broker enforcement or audit ordering, evidence trust or `EvidenceView`, detectors, score/gate logic, run hashing/verification, private-pack redaction, honeytoken generation, MCP exposure, anything executing untrusted content. Everything else `risk:low`.

## Epic body template

```markdown
## Outcome
## Scope
- bullet per capability (the planner maps bullets to tasks)
## Architecture references
## Exit criteria
- [ ] ...

<!-- verifi-agent
phase: <n>
seq: <n>
-->
```

## Spike body template

```markdown
## Question
## Options (with trade-offs)
## Recommendation
## Output
Which ADR/doc gets written or updated.
```
Spikes carry `type:spike` + `needs:human`. An agent may work on one only if a human adds `human:approved`; the deliverable is a docs PR (which touches protected paths, so it also needs `human:approved`).
