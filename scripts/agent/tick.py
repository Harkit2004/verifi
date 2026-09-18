#!/usr/bin/env python3
"""tick: one iteration of verifi's perpetual software engineer.

A scheduler (cron, Windows Task Scheduler, GitHub Actions) runs this every N
minutes. Each tick does AT MOST ONE agent session, in this priority order:

  1. housekeeping  merge green low-risk agent PRs, flag high-risk ones, close finished epics
  2. resume-pr     fix an agent PR with failing CI / requested changes / conflicts
  3. resume-issue  continue an in-progress issue whose last session ended without a PR
  4. work          claim the next agent:ready issue and implement it
  5. triage        promote/complete needs:triage issues
  6. plan          decompose the next epic when the ready queue is empty (max once per 24h)

The LLM work is done by opencode (never Claude Code). All GitHub state changes
go through agentctl so they stay machine-readable.

  python scripts/agent/tick.py --dry-run     # show what would happen
  python scripts/agent/tick.py               # do it
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agentctl as ac  # noqa: E402

ROOT = ac.ROOT
AGENT_DIR = ROOT / ".agent"
RUNS_DIR = AGENT_DIR / "runs"
STATE_FILE = AGENT_DIR / "state.json"
LOCK_FILE = AGENT_DIR / "tick.lock"
SESSION_TIMEOUT_S = int(os.environ.get("VERIFI_AGENT_TIMEOUT", "5400"))
PLAN_INTERVAL = timedelta(hours=24)
SESSION_RE = re.compile(r'"sessionID"\s*:\s*"(ses_[A-Za-z0-9]+)"')
UNATTENDED_MESSAGE = "Execute the task described in the attached file exactly. You are unattended: never wait for a human reply."


class TickError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[tick {datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def git(*args: str, check: bool = True) -> str:
    return ac.run(["git", *args], check=check).strip()


class Lock:
    def __enter__(self) -> "Lock":
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < SESSION_TIMEOUT_S + 1800:
                raise TickError(f"another tick is running (lock age {int(age)}s): {LOCK_FILE}")
            log("removing stale lock")
            LOCK_FILE.unlink()
        LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "at": ac.now_iso()}), encoding="utf-8")
        return self

    def __exit__(self, *exc: object) -> None:
        LOCK_FILE.unlink(missing_ok=True)


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


class Tick:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.dry = args.dry_run
        self.decisions: list[dict[str, Any]] = []
        self.opencode = shutil.which("opencode")

    # -- utilities ---------------------------------------------------------- #

    def decide(self, action: str, **detail: Any) -> None:
        entry = {"action": action, **detail}
        self.decisions.append(entry)
        log(f"{'(dry) ' if self.dry else ''}{action} {json.dumps(detail, default=str)}")

    def preflight(self) -> None:
        missing = [tool for tool in ("git", "gh") if not shutil.which(tool)]
        if not self.opencode and not self.dry:
            missing.append("opencode")
        if missing:
            raise TickError(f"missing tools: {', '.join(missing)} (run scripts/agent/bootstrap.py)")
        if git("status", "--porcelain"):
            raise TickError("working tree is dirty; refusing to run (a human or crashed session left changes)")
        if self.dry:
            return
        git("fetch", "origin", "--prune")
        git("checkout", "main")
        git("pull", "--ff-only", "origin", "main")

    def run_opencode(self, *, agent: str, prompt: str, title: str, session: str | None = None) -> tuple[int, str | None, Path]:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base = RUNS_DIR / f"{stamp}-{agent}-{ac.slugify(title, 30)}"
        prompt_path = base.with_suffix(".prompt.md")
        log_path = base.with_suffix(".jsonl")
        prompt_path.write_text(prompt, encoding="utf-8")
        argv = [self.opencode or "opencode", "run", UNATTENDED_MESSAGE, "--file", str(prompt_path), "--agent", agent, "--format", "json", "--title", title]
        model = self.args.model or os.environ.get("VERIFI_AGENT_MODEL")
        if model:
            argv += ["--model", model]
        if session:
            argv += ["--session", session]
        if self.dry:
            self.decide("would-run-opencode", agent=agent, title=title, session=session, prompt=str(prompt_path))
            return 0, session, log_path
        env = os.environ.copy()
        env.update({"OPENCODE_DISABLE_CLAUDE_CODE": "1", "VERIFI_AGENT": "1"})
        log(f"opencode session starting (agent={agent}, timeout={SESSION_TIMEOUT_S}s, log={log_path.name})")
        with log_path.open("w", encoding="utf-8") as out:
            proc = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT, env=env)
            try:
                code = proc.wait(timeout=SESSION_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = 124
        text = log_path.read_text(encoding="utf-8", errors="replace")
        ids = SESSION_RE.findall(text)
        return code, (ids[-1] if ids else session), log_path

    def checkout_branch(self, branch: str) -> None:
        if self.dry:
            return
        remote = git("ls-remote", "--heads", "origin", branch)
        if remote:
            git("checkout", "-B", branch, f"origin/{branch}")
        else:
            git("checkout", "-B", branch, "main")

    def return_to_main(self) -> None:
        if self.dry:
            return
        if git("status", "--porcelain"):
            log("session left uncommitted changes on the branch; they were checkpointed or will block the next tick")
            return
        git("checkout", "main", check=False)

    # -- 1. housekeeping ---------------------------------------------------- #

    def agent_prs(self) -> list[dict[str, Any]]:
        prs = ac.gh_json(
            "pr", "list", "--state", "open", "--limit", "100", "--json",
            "number,title,headRefName,headRefOid,labels,reviewDecision,mergeable,statusCheckRollup,isDraft,body",
        ) or []
        return [pr for pr in prs if pr["headRefName"].startswith("agent/")]

    def housekeeping(self) -> dict[str, Any] | None:
        resume_candidate = None
        for pr in self.agent_prs():
            comments = (ac.gh_json("pr", "view", str(pr["number"]), "--json", "comments") or {}).get("comments")
            attempts = ac.count_markers(comments, "resume")
            last = ac.last_marker(comments, "resume") or {}
            action = ac.evaluate_pr(pr, attempts=attempts, last_resume_sha=last.get("sha"))
            issue = ac.issue_number_from_branch(pr["headRefName"])
            if action == "merge":
                self.decide("merge-pr", pr=pr["number"], issue=issue)
                if not self.dry:
                    ac.run(["gh", "pr", "merge", str(pr["number"]), "--squash", "--delete-branch"])
            elif action == "needs-human" and ac.NEEDS_HUMAN not in ac.labels_of(pr):
                self.decide("flag-pr-for-human", pr=pr["number"], reason="risk:high or unknown risk; human must review")
                if not self.dry:
                    ac.edit_labels(pr["number"], add=(ac.NEEDS_HUMAN,), pr=True)
                    ac.post_comment(pr["number"], "<!-- verifi-agent:needs-human -->\nCI is green. This PR is `risk:high` (or has no risk label), so a human must review it. Add `human:approved` to let the runner merge it.", pr=True)
            elif action == "escalate":
                self.decide("escalate-pr", pr=pr["number"], issue=issue, attempts=attempts)
                if not self.dry:
                    ac.edit_labels(pr["number"], add=(ac.NEEDS_HUMAN,), pr=True)
                    ac.post_comment(pr["number"], f"<!-- verifi-agent:escalation -->\nThe agent tried {attempts} times to fix CI/review feedback without success. A human needs to look.", pr=True)
                    if issue:
                        ac.edit_labels(issue, add=(ac.BLOCKED, ac.NEEDS_HUMAN))
            elif action == "resume" and resume_candidate is None:
                resume_candidate = {**pr, "_attempts": attempts, "_comments": comments}
        if not self.dry:
            self.close_finished_epics()
        return resume_candidate

    def close_finished_epics(self) -> None:
        repo = ac.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
        epics = ac.gh_json("issue", "list", "--state", "open", "--label", ac.EPIC, "--limit", "100", "--json", "number,title") or []
        for epic in epics:
            children = ac.gh_json("api", f"repos/{repo}/issues/{epic['number']}/sub_issues", "--paginate") or []
            if children and all(child.get("state") == "closed" for child in children):
                self.decide("close-epic", epic=epic["number"])
                ac.run(["gh", "issue", "close", str(epic["number"]), "--comment", "All sub-issues are closed. Epic complete."])

    # -- 2. resume a PR ----------------------------------------------------- #

    def resume_pr(self, pr: dict[str, Any]) -> None:
        number, branch = pr["number"], pr["headRefName"]
        issue = ac.issue_number_from_branch(branch)
        attempt = pr["_attempts"] + 1
        checks = ac.run(["gh", "pr", "checks", str(number)], check=False)
        reviews = ac.gh_json("pr", "view", str(number), "--json", "reviews") or {}
        feedback = [
            f"- {r.get('state')} by {(r.get('author') or {}).get('login')}: {(r.get('body') or '').strip()[:1500]}"
            for r in (reviews.get("reviews") or [])[-5:]
        ]
        issue_comments = ac.get_issue(issue).get("comments") if issue else []
        session = ac.last_session_id(pr["_comments"]) or ac.last_session_id(issue_comments)
        self.decide("resume-pr", pr=number, issue=issue, attempt=attempt, session=session)
        prompt = render_prompt(
            "resume-pr",
            pr=number,
            issue=issue,
            branch=branch,
            attempt=attempt,
            max_attempts=ac.MAX_ATTEMPTS,
            mergeable=pr.get("mergeable"),
            checks=checks.strip()[:4000] or "(no check output)",
            feedback="\n".join(feedback) or "(no reviews)",
        )
        self.checkout_branch(branch)
        try:
            code, session_id, log_path = self.run_opencode(agent="implementer", prompt=prompt, title=f"PR #{number} fix attempt {attempt}", session=session)
            if not self.dry:
                head = git("rev-parse", "HEAD")
                ac.post_comment(number, f"<!-- verifi-agent:resume attempt={attempt} sha={head} session={session_id or 'none'} exit={code} -->\nAgent fix attempt {attempt}/{ac.MAX_ATTEMPTS} finished (exit {code}). Log: `.agent/runs/{log_path.name}`", pr=True)
        finally:
            self.return_to_main()

    # -- 3/4. work an issue ------------------------------------------------- #

    def orphaned_in_progress(self, open_issues: list[dict[str, Any]], pr_issue_numbers: set[int]) -> dict[str, Any] | None:
        for issue in sorted(open_issues, key=lambda i: i["number"]):
            labels = ac.labels_of(issue)
            if ac.IN_PROGRESS in labels and not labels & {ac.BLOCKED, ac.NEEDS_HUMAN} and issue["number"] not in pr_issue_numbers:
                return issue
        return None

    def work_issue(self, issue: dict[str, Any], *, resume: bool) -> None:
        number = issue["number"]
        full = ac.get_issue(number)
        comments = full.get("comments") or []
        attempts = ac.count_markers(comments, "session-start")
        if attempts >= ac.MAX_ATTEMPTS:
            self.decide("escalate-issue", issue=number, attempts=attempts)
            if not self.dry:
                ac.post_comment(number, ac.render_escalation(
                    question=f"The agent ran {attempts} sessions on this issue without producing a PR. Should it be split, clarified, or taken over?",
                    context="See the handoff comments above and the session logs referenced in them.",
                    options=["Split into smaller issues", "Clarify acceptance criteria", "Human implements it"],
                    recommendation="Split it; repeated failure usually means the issue is too large or ambiguous.",
                ))
                ac.edit_labels(number, add=(ac.BLOCKED, ac.NEEDS_HUMAN), remove=(ac.IN_PROGRESS,), current=ac.labels_of(full))
            return
        branch = ac.branch_for(number, issue["title"])
        if not resume:
            self.decide("claim", issue=number, branch=branch)
            if not self.dry and ac.main(["claim", str(number)]) != 0:
                raise TickError(f"could not claim #{number}")
        attempt = attempts + 1
        last_handoff = next((c.get("body") for c in reversed(comments) if "verifi-agent:handoff" in (c.get("body") or "") or "verifi-agent:session-end" in (c.get("body") or "")), None)
        prev_handoff = ac.last_marker(comments, "handoff") or {}
        # Continue the previous session only if it ended mid-task (partial); otherwise start fresh with the handoff as context.
        session = ac.last_session_id(comments) if resume and prev_handoff.get("status") == "partial" else None
        self.decide("work-issue", issue=number, attempt=attempt, resume=resume, session=session)
        prompt = render_prompt(
            "work-issue",
            issue=number,
            title=issue["title"],
            branch=branch,
            attempt=attempt,
            max_attempts=ac.MAX_ATTEMPTS,
            handoff=last_handoff or "(none: this is the first session on this issue)",
        )
        if not self.dry:
            ac.post_comment(number, f"<!-- verifi-agent:session-start attempt={attempt} -->\nAgent session {attempt}/{ac.MAX_ATTEMPTS} starting on `{branch}`.")
        self.checkout_branch(branch)
        try:
            code, session_id, log_path = self.run_opencode(agent="implementer", prompt=prompt, title=f"#{number} {issue['title']}"[:80], session=session)
            if not self.dry:
                self.after_issue_session(number, branch, code, session_id, log_path)
        finally:
            self.return_to_main()

    def after_issue_session(self, number: int, branch: str, code: int, session_id: str | None, log_path: Path) -> None:
        prs = ac.gh_json("pr", "list", "--head", branch, "--state", "open", "--json", "number") or []
        issue = ac.get_issue(number)
        labels = ac.labels_of(issue)
        if prs:
            pr_number = prs[0]["number"]
            risk = ac.RISK_HIGH if ac.RISK_HIGH in labels or ac.RISK_LOW not in labels else ac.RISK_LOW
            ac.edit_labels(pr_number, add=(ac.REVIEW, risk), pr=True)
            ac.edit_labels(number, add=(ac.REVIEW,), remove=(ac.IN_PROGRESS,), current=labels)
            outcome = f"pr={pr_number}"
        elif labels & {ac.BLOCKED, ac.NEEDS_HUMAN}:
            outcome = "escalated"
        else:
            if git("status", "--porcelain"):
                git("add", "-A")
                git("commit", "-m", f"wip(#{number}): checkpoint from unattended session", check=False)
            if git("rev-list", "--count", f"main..{branch}", check=False) not in ("", "0"):
                git("push", "-u", "origin", branch, check=False)
            outcome = "no-pr"
        ac.post_comment(number, f"<!-- verifi-agent:session-end session={session_id or 'none'} exit={code} outcome={outcome} -->\nAgent session ended (exit {code}, outcome `{outcome}`). Log on runner: `.agent/runs/{log_path.name}`")

    # -- 5/6. triage & plan -------------------------------------------------- #

    def triage(self, issues: list[dict[str, Any]]) -> None:
        numbers = [i["number"] for i in issues]
        self.decide("triage", issues=numbers)
        self.run_opencode(agent="triager", prompt=render_prompt("triage", issues=", ".join(f"#{n}" for n in numbers)), title="triage " + " ".join(f"#{n}" for n in numbers[:5]))

    def plan(self, epics: list[dict[str, Any]]) -> None:
        state = load_state()
        last = state.get("last_plan_at")
        if last and datetime.now(timezone.utc) - datetime.fromisoformat(last) < PLAN_INTERVAL:
            self.decide("idle", reason="queue empty and planner ran within 24h")
            return
        self.decide("plan", epics=[e["number"] for e in epics])
        self.run_opencode(agent="planner", prompt=render_prompt("plan", epics=", ".join(f"#{e['number']} {e['title']}" for e in epics)), title="plan next epic")
        if not self.dry:
            state["last_plan_at"] = datetime.now(timezone.utc).isoformat()
            save_state(state)

    # -- main flow ---------------------------------------------------------- #

    def paused(self) -> str | None:
        if (AGENT_DIR / "PAUSE").exists():
            return f"{AGENT_DIR / 'PAUSE'} exists"
        if os.environ.get("VERIFI_AGENT_PAUSED") == "1":
            return "VERIFI_AGENT_PAUSED=1"
        if ac.gh_json("issue", "list", "--state", "open", "--label", ac.PAUSE, "--json", "number"):
            return f"an open issue is labeled {ac.PAUSE}"
        return None

    def run(self) -> None:
        reason = self.paused()
        if reason:
            self.decide("paused", reason=reason)
            return
        self.preflight()
        only = self.args.only
        if only in ("auto", "merge", "resume"):
            candidate = self.housekeeping()
            if only == "merge":
                return
            if candidate:
                self.resume_pr(candidate)
                return
        if only == "resume":
            return

        open_issues = ac.list_open_issues()
        pr_issue_numbers = {ac.issue_number_from_branch(pr["headRefName"]) for pr in self.agent_prs()}
        if only in ("auto", "work"):
            if self.args.issue:
                forced = next((i for i in open_issues if i["number"] == self.args.issue), None)
                if not forced:
                    raise TickError(f"issue #{self.args.issue} is not open")
                self.work_issue(forced, resume=ac.IN_PROGRESS in ac.labels_of(forced))
                return
            orphan = self.orphaned_in_progress(open_issues, {n for n in pr_issue_numbers if n})
            if orphan:
                self.work_issue(orphan, resume=True)
                return
            issue, skipped = ac.select_next(open_issues)
            if issue:
                self.work_issue(issue, resume=False)
                return
            self.decide("no-ready-issue", skipped=len(skipped))
        if only in ("auto", "triage"):
            triage = [i for i in open_issues if ac.NEEDS_TRIAGE in ac.labels_of(i) and ac.NEEDS_HUMAN not in ac.labels_of(i)]
            if triage:
                self.triage(triage[:10])
                return
        if only in ("auto", "plan"):
            epics = [i for i in open_issues if ac.EPIC in ac.labels_of(i) and ac.NEEDS_HUMAN not in ac.labels_of(i)]
            if epics:
                self.plan(sorted(epics, key=lambda e: (ac.parse_meta(e.get("body"))["phase"], e["number"]))[:3])
                return
        self.decide("idle", reason="nothing to do")


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def render_prompt(name: str, **values: Any) -> str:
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="decide and print, change nothing, run no agent")
    parser.add_argument("--only", choices=("auto", "merge", "resume", "work", "triage", "plan"), default="auto")
    parser.add_argument("--issue", type=int, help="force work on this issue number")
    parser.add_argument("--model", help="provider/model for opencode (default: $VERIFI_AGENT_MODEL or opencode config)")
    args = parser.parse_args(argv)

    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        print("Refusing to run: the perpetual engineer is opencode-only. Claude Code sessions must not run the tick loop (see CLAUDE.md).", file=sys.stderr)
        return 4

    tick = Tick(args)
    status = 0
    try:
        with Lock():
            tick.run()
    except (TickError, ac.AgentCtlError) as exc:
        tick.decide("error", message=str(exc))
        status = 1
    finally:
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        (AGENT_DIR / "ticks").mkdir(exist_ok=True)
        record = {"at": ac.now_iso(), "dry_run": args.dry_run, "decisions": tick.decisions}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (AGENT_DIR / "ticks" / f"{stamp}.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return status


if __name__ == "__main__":
    sys.exit(main())
