---
description: Work one issue interactively with the same procedure the unattended runner uses. Usage: /work <issue-number>
agent: implementer
---

Work on issue #$1.

Load the skill `verifi-work-loop` and follow it step by step. Issue context:

!`python scripts/agent/agentctl.py context $1`
