---
name: decompose-epic
description: How the verifi planner breaks an epic into small, ordered, dependency-linked task issues that meet the Definition of Ready, grounded strictly in docs/architecture, with spikes for missing decisions.
---

# Decompose an epic

## 1. Gather

```bash
gh issue view <epic> --comments
gh api repos/{owner}/{repo}/issues/<epic>/sub_issues --jq '.[] | {number, title, state}'
gh issue list --state all --label "phase:<p>" --limit 200 --json number,title,state,labels
```

Read the epic's "Scope" list, `docs/roadmap.md`, and every architecture doc the epic references.

## 2. Find the gap

List each scope bullet and mark it: covered by an existing task (open or closed), or unplanned. Only plan unplanned bullets. If nothing is unplanned, comment on the epic "fully planned" and stop.

## 3. Missing decisions become spikes, not guesses

If a bullet requires a choice not written in `docs/architecture/` or `docs/adr/` (a library, a protocol, a formula, a security default), create **one** spike:

- title `Spike: <decision>`, labels `type:spike,needs:human,phase:<p>,area:<a>`
- body: question, options with trade-offs, recommendation, what doc or ADR the answer should update

Then stop planning that bullet.

## 4. Slice into tasks

Good task:

- one observable behavior, testable with fakes, size s (under 150 lines) or m (under 400 lines),
- lands in the order of the layers (models, then service, then operation/CLI, then e2e),
- has a precise "Tests to write first" list with file paths and test names,
- names the exact module paths and public names from `interfaces.md`.

Split by behavior, not by file. "Loader parses minimal spec" plus "loader reports errors with JSON pointers" beats "loader.py part 1/2".

## 5. Create each task

You cannot write files. Pass the body (exact section order from `docs/process/definition-of-ready.md`) on stdin with a quoted heredoc:

```bash
gh issue create --title "<area>: <behavior>" --label "type:task,phase:<p>,area:<a>,risk:<r>,size:<s>,needs:triage" --milestone "<milestone title>" --body-file - <<'EOF'
...full body...
EOF
id=$(gh api repos/{owner}/{repo}/issues/<new> --jq .id)
gh api -X POST repos/{owner}/{repo}/issues/<epic>/sub_issues -F sub_issue_id=$id
python scripts/agent/agentctl.py promote <new>
```

Metadata `seq`: continue after the highest existing seq in the phase, in dependency order. `depends-on` only lists issues that must be *merged* first.

## 6. Limits

- At most 8 tasks per session.
- Never create tasks for later phases while an earlier phase has unplanned scope.
- Never edit docs or code. If a doc is wrong, create a `type:docs` issue with `needs:human`.
