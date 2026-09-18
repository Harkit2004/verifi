---
description: Run the verification gate and explain any failures. Usage: /verify [extra verify.py args]
agent: implementer
---

Run `python scripts/verify.py --label manual $ARGUMENTS` and load the skill `verification-run`.
If the result is FAIL, read the failing stage logs listed in the summary and explain the root cause of each failure in one or two sentences. Do not change code unless I ask you to.
