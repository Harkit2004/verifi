---
name: fix-ci-or-review
description: Procedure for a session resumed on an existing verifi agent PR - reproduce failing CI locally, resolve merge conflicts by merging main, address review comments within scope, push without force, and reply with run ids.
---

# Fix CI or review feedback

You are on an existing PR branch. The prompt contains the check output and review feedback.

## 1. Classify each problem

| Problem | Go to |
|---|---|
| A CI check failed | section 2 |
| `mergeable: CONFLICTING` | section 3 |
| Review requested changes | section 4 |

## 2. Failing CI

```bash
gh pr checks <pr>
gh run list --branch <branch> --limit 3
gh run view <run-id> --log-failed | tail -n 120
```

Reproduce locally with the same stage: `python scripts/verify.py --stage <stage> --label repro`.

- Fails locally: fix it (skill `tdd-cycle`: if it's a real bug, add or adjust a test that captures it).
- Passes locally, fails in CI: look for OS differences (paths, line endings, Docker availability, timezone). Fix the non-determinism; do not add CI-only skips.
- Failure caused by infrastructure (runner down, network): do nothing to code; hand off with `--status blocked`.

## 3. Merge conflicts

```bash
git fetch origin
git merge origin/main          # never rebase a pushed branch; never force-push
# resolve conflicts, keeping both sides' intent; re-run tests
python scripts/verify.py --label merge
git commit                     # merge commit
```

If a conflict involves someone else's semantics you don't understand, escalate.

## 4. Review comments

```bash
gh pr view <pr> --comments
gh api repos/{owner}/{repo}/pulls/<pr>/comments --jq '.[] | {path, line, body}'
```

For each comment:

- **In scope and correct:** fix it; add a test if behavior changes.
- **Out of scope:** reply explaining it is out of scope and `agentctl register` a follow-up; link it.
- **Conflicts with docs, or you believe it is wrong on architectural grounds:** escalate; do not argue in circles.

## 5. Finish

```bash
python scripts/verify.py --label fix
git push origin <branch>
gh pr comment <pr> --body "Addressed: <bullets>. Verification: <run id>."
```

Then stop. Maximum 3 fix attempts per PR; after that the runner hands it to a human.
