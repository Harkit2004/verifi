---
name: open-pr
description: Final step of a verifi issue - commit conventions, pushing the agent branch, opening the PR with the template (Closes #n, red/green run ids, acceptance checklist), and what happens after (runner merges low-risk PRs when CI is green).
---

# Open the PR

## Preconditions (all true)

- `python scripts/verify.py --label green` passed on the current HEAD (`--show latest` shows PASS and the same sha as `git rev-parse HEAD`).
- A `red` run exists for this issue's tests (`python scripts/verify.py --list 20`).
- The reviewer subagent returned APPROVE, or you fixed its blocking findings.
- The working tree is clean (`git status --short` prints nothing).

## Commits

Conventional commits, with the issue number at the end:

```
test(spec): failing tests for VerificationSpec loader (#12)
feat(spec): load and validate VerificationSpec files (#12)
fix(detectors): ... (#12)
```

Types: feat, fix, test, refactor (only inside your issue), docs, chore.

## Push and create

```bash
git push -u origin <branch>
gh pr create --base main --head <branch> --title "<type>(<area>): <summary> (#<issue>)" --body-file .agent/pr-body.md
```

Write `.agent/pr-body.md` (git-ignored) following `.github/pull_request_template.md`:

```markdown
Closes #<issue>

## What changed
- <1-5 bullets, behavior not files>

## Acceptance criteria
- [x] AC1 ... (tests/unit/spec/test_loader.py::test_minimal_spec_parses)
- [x] AC2 ...

## Verification
- Red run: `<red run id>`
- Green run: `<green run id>`

<paste .verification/<green id>/summary.md table>

## Out of scope / follow-ups
- #<registered issue> <title>   (or "none")

## Risk
risk:<low|high> (copied from the issue)

<!-- verifi-agent:pr issue=<issue> -->
```

## After opening

- Do not merge. Do not request reviewers. Do not add labels (the runner adds `agent:review` and the risk label).
- **Stop the session.** The runner merges `risk:low` PRs when CI is green, flags `risk:high` PRs for a human, and starts a fix session if CI fails or changes are requested.
