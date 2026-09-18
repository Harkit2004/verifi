# Unattended session: implement issue #{{issue}}

- Issue: #{{issue}} "{{title}}"
- Branch (already checked out for you): `{{branch}}`
- Attempt: {{attempt}} of {{max_attempts}} (after the last attempt a human takes over)

## Previous handoff on this issue

{{handoff}}

## What to do

1. Load the skill `verifi-work-loop` now and follow it step by step. It tells you which other skills to load and when.
2. Read the issue with: `python scripts/agent/agentctl.py context {{issue}}`
3. If a previous handoff exists, start from its **Exact next step**. Do not redo finished work; check `git log main..HEAD` first.
4. Your session MUST end in exactly one of these outcomes:
   - **PR opened** for `{{branch}}` (skill `open-pr`) with the red and green verification run ids in the body.
   - **Handoff posted** (skill `session-control`) after committing and pushing your partial work, when you are running out of steps/context or the remaining work is clear but long.
   - **Escalation posted** (skill `escalate-to-human`) when a human decision is needed.
5. No human is watching this session. Never ask a question in chat and never wait for a reply: escalate instead.
6. Work only on #{{issue}}. Anything else you notice goes into a new issue via `agentctl register` (skill `register-issue`).
