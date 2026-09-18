# Unattended session: fix PR #{{pr}} (issue #{{issue}})

- Branch (already checked out for you): `{{branch}}`
- Fix attempt: {{attempt}} of {{max_attempts}} (after the last attempt a human takes over)
- Mergeable state: {{mergeable}}

## CI checks

```
{{checks}}
```

## Review feedback

{{feedback}}

## What to do

1. Load the skill `fix-ci-or-review` now and follow it exactly.
2. Fix only what the failing checks, merge conflicts, or review comments require. No new features, no unrelated cleanup.
3. Run `python scripts/verify.py --label fix` until it passes, then push to `{{branch}}` (never force-push).
4. Reply on the PR summarizing what changed and cite the verification run id.
5. If the feedback asks for something outside the issue's scope, or you disagree with it on architectural grounds, escalate (skill `escalate-to-human`) instead of guessing.
6. No human is watching this session. Never ask a question in chat.
