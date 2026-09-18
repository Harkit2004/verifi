# AGENTS.md: operating manual for verifi's autonomous engineers

This file is loaded into every **opencode** session in this repo. It holds the rules. Step-by-step
procedures live in skills under `.opencode/skills/`; load them with the `skill` tool at the moments
listed in section 3. If this file conflicts with an issue, this file wins. If this file conflicts with
`docs/architecture/`, stop and escalate: never pick one silently.

> The perpetual engineer is **opencode**, driven by `scripts/agent/tick.py`. Claude Code does not run
> this loop (see `CLAUDE.md`).

---

## 1. What we are building (read once)

**verifi** is an open-source *adversarial AI verification* platform: "Run untrusted AI against an untrusted world, without trusting either."

A user writes a **VerificationSpec** (YAML) that says what an AI agent may do (tools, network,
filesystem) and which security **controls** must hold (no secret access, no exfiltration, no
unauthorized tool use, no sandbox escape, ...). `verifi run spec.yaml` then:

1. provisions an isolated **sandbox** (fake for tests, hardened Docker, later a VM tier),
2. seeds a mock **world** (files, CRM DB, mailbox, HTTP APIs) with per-run **honeytokens**,
3. exposes tools only through a policy-enforcing, audited **tool broker**,
4. runs the **target** agent through scenarios, many of them carrying **attacks** (prompt injection, indirect injection, credential discovery, ...),
5. collects **evidence** from the host side (broker audit, network sinkhole, filesystem diffs),
6. runs **detectors** over trusted evidence only, producing **findings**,
7. **scores** controls, evaluates the CI **gate**, and writes a hash-chained, tamper-evident **report**.

Start with `docs/architecture/overview.md`. Contracts: `docs/architecture/interfaces.md`.

---

## 2. Prime directives (never violate)

1. **No issue, no work.** One issue, one branch (`agent/<n>-<slug>`), one PR. Stay inside the issue's scope.
2. **Tests before implementation.** Write the failing tests listed in the issue, record a red run (`python scripts/verify.py --expect-fail --label red --pytest-args <tests>`), then implement.
3. **Minimal change.** Use the smallest diff that satisfies the acceptance criteria. No drive-by refactors, renames, reformatting, speculative parameters, or "while I'm here" fixes. Diff budget: warn above 300 changed lines, fail above 800.
4. **CLI parity.** Every user-facing capability is an *operation* in the registry, reachable via `verifi <group> <verb> --json`. Nothing may exist only in an API or UI. See `docs/architecture/cli-contract.md`.
5. **Evidence, not claims.** Verdicts come only from trusted, host-side evidence. Never score from what the target model *says*. See `docs/architecture/threat-model.md`.
6. **Green gate before push.** Before any push, `python scripts/verify.py --label green` must pass. Cite run ids in the PR.
7. **Protected paths are read-only for you:** `AGENTS.md`, `CLAUDE.md`, `opencode.json`, `.opencode/`, `.github/`, `docs/architecture/`, `docs/adr/`, `docs/process/`, `scripts/agent/`, `scripts/verify.py`. If one must change, escalate. The `protected` stage of the gate fails otherwise.
8. **Dependencies:** only packages allowlisted in `docs/architecture/dependencies.md`. A new one needs escalation.
9. **Never:** merge PRs, push to `main`, force-push, rewrite published history, close issues, delete others' branches, edit labels outside `agentctl`, run `scripts/agent/tick.py`, or disable or skip tests to go green.
10. **No secrets** in code, tests, logs, issues, or PRs. Tests use generated fake values.
11. **When unsure, escalate; don't guess.** A wrong guess on a security boundary is worse than a blocked issue.

---

## 3. Which skill, when

| Moment | Load skill |
|---|---|
| Start of **every** session | `verifi-work-loop` |
| Before writing any code for an issue | `read-before-code` |
| Writing tests / implementing | `tdd-cycle` |
| Before every commit | `minimal-diff` |
| Running or debugging the gate | `verification-run` |
| Adding or changing a user-facing capability | `cli-route` |
| Touching sandbox, broker, detectors, scoring, evidence, or reports | `architecture-guard` |
| A tool is missing or the environment is broken | `toolchain-setup` |
| You found a bug or gap outside your issue | `register-issue` |
| Deciding to continue, hand off, or stop | `session-control` |
| You need a human decision | `escalate-to-human` |
| Work is done and the gate is green | `open-pr` |
| Session was started to fix a PR | `fix-ci-or-review` |
| Triage session | `triage-issues` |
| Planning session | `decompose-epic` |

---

## 4. Sessions: continue, hand off, escalate, or start new

The runner (`tick.py`) starts sessions. You decide how yours ends.

- **New session** (runner decides): a new issue; a previous session ended with a *blocked* or *done* handoff; the previous session is older than 24h. A new session learns everything from `agentctl context <n>`, the handoff comment, and `git log main..HEAD`.
- **Continue the same session** (runner passes `--session`): the previous one ended *partial*, or you are fixing your own PR.
- **Hand off** (`agentctl handoff <n> --status partial`) when you have used about 70% of your steps, the context feels long or you are re-reading files you already read, or the remaining work is clear but will not fit. Commit and push first. The handoff must state the single **exact next step**.
- **Escalate** (`agentctl escalate <n>`) when:
  - acceptance criteria are ambiguous or contradict the docs,
  - the fix requires a protected path, a new dependency, secrets, paid services, or network access in tests,
  - a security boundary or verdict rule would change,
  - the same failure persists after 3 genuinely different fix attempts,
  - the issue is clearly larger than size `m` (propose a split in the escalation).
  After escalating, **stop**. Do not start another issue in the same session.
- **Register** (`agentctl register`) for anything real that is out of scope. Then continue your issue.

Attempt limit: 3 sessions per issue and 3 fix attempts per PR. After that the runner escalates automatically.

---

## 5. Commands cheat sheet

```bash
python scripts/agent/agentctl.py context <n>          # issue, deps, attempts, last handoff
python scripts/agent/agentctl.py next --explain       # what the queue would pick and why
python scripts/verify.py --expect-fail --label red --pytest-args tests/unit/x/test_y.py
python scripts/verify.py --label green                # full gate; logs in .verification/<id>/
python scripts/verify.py --show latest                # summary of the last run
python scripts/agent/agentctl.py handoff <n> --status partial --done "..." --next "..." --session <id> --branch <b> --verification <run-id>
python scripts/agent/agentctl.py escalate <n> --question "..." --context "..." --option "A" --option "B" --recommendation "A because ..."
python scripts/agent/agentctl.py register --type bug --title "..." --summary "..." --evidence "..." --found-while <n> --area <area>
python scripts/agent/bootstrap.py [--install]         # toolchain check
uv run verifi --help                                  # product CLI (once it exists)
```

---

## 6. Repo map

```
src/verifi/            product code (layers: docs/architecture/overview.md)
tests/unit|integration|e2e|contracts/   tests mirror src paths
schemas/               generated JSON Schemas (committed, drift-tested)
examples/specs/        example VerificationSpecs used by e2e tests
docs/architecture/     contracts and design (protected)
docs/adr/              architecture decision records (protected)
docs/process/          workflow, testing, verification, sessions (protected)
.opencode/             agents, skills, commands (protected)
scripts/verify.py      the verification gate (protected)
scripts/agent/         runner, agentctl, prompts (protected)
.verification/         local gate logs (git-ignored)
.agent/                runner logs, prompts, tick records (git-ignored)
```

---

## 7. Definition of Done (the PR is mergeable only if all hold)

- [ ] Every acceptance criterion in the issue is met and ticked in the PR body.
- [ ] The tests listed in the issue exist, a red run was recorded before implementation, and a green run passes on the final commit.
- [ ] `python scripts/verify.py --label green` passes: format, lint, types, tests, diff budget, protected paths.
- [ ] New user-facing behavior has a CLI route with `--json` and a CLI test.
- [ ] Public names match `docs/architecture/interfaces.md`.
- [ ] The reviewer subagent returned `APPROVE`, or its blocking findings were fixed.
- [ ] The PR body uses the template and contains `Closes #<n>`.
- [ ] Out-of-scope discoveries were registered as issues, not fixed inline.
