# Unattended session: triage

Issues waiting for triage: {{issues}}

1. Load the skill `triage-issues` now and follow it for each issue, oldest first.
2. You may only change issues (labels, comments, bodies) through `gh issue edit`/`gh issue comment` and `python scripts/agent/agentctl.py`. You never edit code.
3. Promote an issue only with `agentctl promote <n>`, which enforces the Definition of Ready.
4. No human is watching. Anything needing a human decision gets `agentctl escalate`.
