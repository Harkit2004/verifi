# Operating the perpetual engineer

## 1. Prerequisites (runner machine)

```bash
python scripts/agent/bootstrap.py --install     # git, gh, uv, python 3.12, opencode
gh auth login                                   # account with repo + workflow scopes
opencode auth login                             # provider credentials for the model you will use
python scripts/agent/setup_labels.py --apply    # labels + milestones (once per repo)
```

Choose a model with solid tool use. Set it once:

```bash
export VERIFI_AGENT_MODEL="provider/model"      # PowerShell: $env:VERIFI_AGENT_MODEL = "provider/model"
```

Docker is optional on the runner (docker-marked tests skip), but recommended from Phase 1 sandbox epics on. CI runs them on Linux regardless.

Use a **dedicated clone** for the runner. The tick refuses to run on a dirty tree and switches branches.

## 2. Dry run

```bash
python scripts/agent/tick.py --dry-run
python scripts/agent/agentctl.py next --explain
python scripts/agent/agentctl.py pr-status
```

Decisions are printed and saved to `.agent/ticks/<stamp>.json`.

## 3. Schedule it

One tick at a time (a lock file prevents overlap). Every 20-30 minutes is reasonable.

**Windows Task Scheduler**
```powershell
schtasks /Create /TN "verifi-agent-tick" /SC MINUTE /MO 30 /F `
  /TR "cmd /c cd /d C:\path\to\verifi-runner && python scripts\agent\tick.py >> .agent\tick.log 2>&1"
```

**Linux/macOS cron**
```cron
*/30 * * * * cd /srv/verifi-runner && VERIFI_AGENT_MODEL=provider/model python3 scripts/agent/tick.py >> .agent/tick.log 2>&1
```

**GitHub Actions:** `.github/workflows/agent-tick.yml` (manual dispatch; uncomment `schedule` to enable). Requires secrets:
- `AGENT_GH_TOKEN`: fine-grained PAT with contents, issues, pull-requests write. PRs opened with the default `GITHUB_TOKEN` do **not** trigger CI, so a PAT is required for the merge policy to work.
- provider API key(s) for opencode (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) and repository variable `VERIFI_AGENT_MODEL`.

## 4. Monitor

| Question | Command |
|---|---|
| What is it doing? | `ls -t .agent/ticks | head`, `tail .agent/tick.log` |
| What will it pick next? | `python scripts/agent/agentctl.py next --explain` |
| PR states | `python scripts/agent/agentctl.py pr-status` |
| Needs me | `gh issue list --label needs:human` and `gh pr list --label needs:human` |
| Session transcript | `.agent/runs/<stamp>-implementer-*.jsonl` or `opencode session list` |
| Gate history | `python scripts/verify.py --list 20` |

## 5. Control

| Action | How |
|---|---|
| Pause everything | `touch .agent/PAUSE`, or open an issue labeled `agent:pause` (works remotely) |
| Force a specific issue | `python scripts/agent/tick.py --issue 42` |
| Only merge/housekeep | `python scripts/agent/tick.py --only merge` |
| Unblock an issue | answer, then remove `needs:human` + `agent:blocked`, add `agent:ready` |
| Approve a high-risk PR | review, then add label `human:approved` (runner merges when green) |
| Stop a runaway session | kill the `opencode` process; the next tick sees the in-progress issue and resumes or escalates |

## 6. Recommended repository settings

- Branch protection on `main`: require status check `verify`, require linear history (squash), disallow force pushes.
- CODEOWNERS for protected paths (`.github/CODEOWNERS`).
- Settings: allow squash merge only; automatically delete head branches.
- Actions: allow GitHub Actions to create PRs (only if using the Actions runner).

## 7. Why not Claude Code for the loop?

By design (ADR-0008): the unattended worker is opencode so it can use any provider or model and so the loop's behavior is defined entirely by `AGENTS.md` + skills + scripts in this repo. Claude Code is used interactively by maintainers for architecture and harness work; `tick.py` refuses to run inside a Claude Code session.
