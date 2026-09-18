---
name: triage-issues
description: How the verifi triager turns needs:triage issues (often agent-discovered) into Definition-of-Ready tasks - reproduce/validate, dedupe, add tests/acceptance/metadata, set risk and size, promote via agentctl, or escalate.
---

# Triage issues

For each `needs:triage` issue, oldest first:

## 1. Validate

```bash
python scripts/agent/agentctl.py context <n>
gh issue list --state all --search "<key words> in:title" --limit 20
```

- **Duplicate:** comment `Duplicate of #x`, add `needs:human` with a note asking a human to close it (you cannot close issues). Next issue.
- **Not a real problem / cannot understand:** comment with what is unclear, add `needs:human`. Next issue.
- **Security concern:** set `risk:high`. If it implies an architecture change, make it a spike (`type:spike`, `needs:human`).

## 2. Complete the body to the Definition of Ready

You cannot write files. Pass the new body on stdin with a quoted heredoc:

```bash
gh issue edit <n> --body-file - <<'EOF'
...full body...
EOF
```

Required sections, in this order (see `docs/process/definition-of-ready.md`):

```
## Context
## Goal
## Read first
## Tests to write first
## Implementation notes
## Acceptance criteria
- [ ] ...
## Out of scope
## Verification

<!-- verifi-agent
phase: <phase of the related epic, or current lowest open phase>
seq: <place after its dependencies; use 900+ for discovered bugs so planned order is preserved>
depends-on: <#numbers or empty>
risk: low|high
size: s|m
epic: <#epic or empty>
-->
```

Keep the reporter's original summary and evidence at the bottom under `## Original report`.

## 3. Labels

- exactly one `type:*`, one `risk:*`, one `size:*`, one `phase:*`, at least one `area:*`
- risk:high if it touches sandbox, broker enforcement, detectors, evidence trust, scoring/gate, hashing, or private-pack handling
- size m maximum; if bigger, split into multiple issues (each DoR-complete) and link them

```bash
gh issue edit <n> --add-label "type:bug,risk:low,size:s,phase:1,area:detectors"
```

## 4. Promote

```bash
python scripts/agent/agentctl.py promote <n>
```

If it prints problems, fix them and retry. Never add `agent:ready` by hand.

## 5. Sub-issue link (if part of an epic)

```bash
id=$(gh api repos/{owner}/{repo}/issues/<n> --jq .id)
gh api -X POST repos/{owner}/{repo}/issues/<epic>/sub_issues -F sub_issue_id=$id
```
