#!/usr/bin/env python3
"""agentctl: deterministic control plane for verifi's autonomous agents.

Every change an agent makes to the GitHub task queue (claiming, handing off,
escalating, registering new issues) goes through this script, so labels,
markers and comment formats stay machine-readable for the next session.

Stdlib only. Run from anywhere:  python scripts/agent/agentctl.py --help
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# Labels. Keep in sync with scripts/agent/setup_labels.py.
READY = "agent:ready"
IN_PROGRESS = "agent:in-progress"
REVIEW = "agent:review"
BLOCKED = "agent:blocked"
DISCOVERED = "agent:discovered"
NEEDS_HUMAN = "needs:human"
NEEDS_TRIAGE = "needs:triage"
HUMAN_APPROVED = "human:approved"
EPIC = "type:epic"
SPIKE = "type:spike"
RISK_LOW = "risk:low"
RISK_HIGH = "risk:high"
PAUSE = "agent:pause"

NOT_SELECTABLE = (IN_PROGRESS, REVIEW, BLOCKED, NEEDS_HUMAN, NEEDS_TRIAGE)
MAX_ATTEMPTS = 3

# Machine-readable issue metadata block:  <!-- verifi-agent\nphase: 1\nseq: 3\n... -->
META_RE = re.compile(r"<!--\s*verifi-agent\s*\n(.*?)-->", re.S)
# Event markers in comments:  <!-- verifi-agent:handoff status=partial session=ses_x -->
MARKER_RE = re.compile(r"<!--\s*verifi-agent:(?P<kind>[a-z-]+)(?P<attrs>[^>]*?)-->")
ATTR_RE = re.compile(r"([a-z_]+)=(\S+)")


class AgentCtlError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested in scripts/agent/tests)
# --------------------------------------------------------------------------- #


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_meta(body: str | None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "phase": 99,
        "seq": 9999,
        "depends_on": [],
        "risk": None,
        "size": None,
        "epic": None,
        "has_block": False,
    }
    if not body:
        return meta
    match = META_RE.search(body)
    if not match:
        return meta
    meta["has_block"] = True
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().replace("-", "_")
        value = value.strip()
        if key in ("phase", "seq", "epic"):
            digits = re.findall(r"\d+", value)
            if digits:
                meta[key] = int(digits[0])
        elif key == "depends_on":
            meta["depends_on"] = [int(n) for n in re.findall(r"\d+", value)]
        elif key in ("risk", "size"):
            meta[key] = value.lower() or None
    return meta


def labels_of(item: dict[str, Any]) -> set[str]:
    return {lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in item.get("labels") or []}


def select_next(open_issues: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[tuple[int, str]]]:
    """Pick the next issue to work on. Returns (issue or None, [(number, why skipped)])."""
    open_numbers = {issue["number"] for issue in open_issues}
    candidates: list[tuple[int, int, int, dict[str, Any]]] = []
    skipped: list[tuple[int, str]] = []
    for issue in open_issues:
        number = issue["number"]
        labels = labels_of(issue)
        if EPIC in labels:
            continue
        if READY not in labels:
            skipped.append((number, "not labeled agent:ready"))
            continue
        blocking = sorted(labels.intersection(NOT_SELECTABLE))
        if blocking:
            skipped.append((number, "has " + ", ".join(blocking)))
            continue
        meta = parse_meta(issue.get("body"))
        if meta["size"] == "l" or "size:l" in labels:
            skipped.append((number, "size l must be split first"))
            continue
        open_deps = [dep for dep in meta["depends_on"] if dep in open_numbers]
        if open_deps:
            skipped.append((number, "waiting on " + ", ".join(f"#{d}" for d in open_deps)))
            continue
        candidates.append((meta["phase"], meta["seq"], number, issue))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    return (candidates[0][3] if candidates else None), skipped


def slugify(title: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "work"


def branch_for(number: int, title: str) -> str:
    return f"agent/{number}-{slugify(title)}"


def issue_number_from_branch(branch: str) -> int | None:
    match = re.match(r"agent/(\d+)-", branch or "")
    return int(match.group(1)) if match else None


def find_markers(text: str | None) -> list[tuple[str, dict[str, str]]]:
    return [(m.group("kind"), dict(ATTR_RE.findall(m.group("attrs")))) for m in MARKER_RE.finditer(text or "")]


def comment_bodies(comments: list[dict[str, Any]] | None) -> list[str]:
    return [c.get("body") or "" for c in comments or []]


def count_markers(comments: list[dict[str, Any]] | None, kind: str) -> int:
    return sum(1 for body in comment_bodies(comments) for k, _ in find_markers(body) if k == kind)


def last_marker(comments: list[dict[str, Any]] | None, kind: str) -> dict[str, str] | None:
    found = None
    for body in comment_bodies(comments):
        for k, attrs in find_markers(body):
            if k == kind:
                found = attrs
    return found


def last_session_id(comments: list[dict[str, Any]] | None) -> str | None:
    session = None
    for body in comment_bodies(comments):
        for _, attrs in find_markers(body):
            if attrs.get("session", "").startswith("ses"):
                session = attrs["session"]
    return session


def check_state(rollup: list[dict[str, Any]] | None) -> str:
    """Collapse a PR statusCheckRollup into none|pending|failure|success."""
    if not rollup:
        return "none"
    states = []
    for check in rollup:
        if "conclusion" not in check and "state" in check:  # StatusContext
            state = (check.get("state") or "").upper()
            states.append({"SUCCESS": "success", "PENDING": "pending", "EXPECTED": "pending"}.get(state, "failure"))
            continue
        if (check.get("status") or "").upper() != "COMPLETED":
            states.append("pending")
            continue
        conclusion = (check.get("conclusion") or "").upper()
        states.append("success" if conclusion in ("SUCCESS", "NEUTRAL", "SKIPPED") else "failure")
    if "failure" in states:
        return "failure"
    if "pending" in states:
        return "pending"
    return "success"


def evaluate_pr(pr: dict[str, Any], *, attempts: int, last_resume_sha: str | None) -> str:
    """Decide what the runner does with an agent PR.

    Returns one of: merge | resume | escalate | needs-human | wait.
    Unknown risk is treated as high risk. Nothing unverified is ever merged.
    """
    labels = labels_of(pr)
    if NEEDS_HUMAN in labels:
        return "needs-human"
    if pr.get("isDraft"):
        return "wait"
    checks = check_state(pr.get("statusCheckRollup"))
    review = (pr.get("reviewDecision") or "").upper()
    conflicting = (pr.get("mergeable") or "").upper() == "CONFLICTING"
    changes_requested = review == "CHANGES_REQUESTED"
    if changes_requested and not conflicting and checks != "failure" and pr.get("headRefOid") == last_resume_sha:
        return "wait"  # already addressed in the last resume; waiting for re-review
    if checks == "failure" or changes_requested or conflicting:
        return "escalate" if attempts >= MAX_ATTEMPTS else "resume"
    if checks in ("pending", "none"):
        return "wait"
    if HUMAN_APPROVED not in labels and (RISK_HIGH in labels or RISK_LOW not in labels):
        return "needs-human"
    if (pr.get("mergeable") or "").upper() != "MERGEABLE":
        return "wait"
    return "merge"


def _tokens(title: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", title.lower()) if len(t) > 2}


def similar_titles(a: str, b: str, threshold: float = 0.7) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return a.strip().lower() == b.strip().lower()
    return len(ta & tb) / len(ta | tb) >= threshold


def definition_of_ready(issue: dict[str, Any]) -> list[str]:
    """Return the reasons an issue is NOT ready for an agent (empty list == ready)."""
    problems: list[str] = []
    labels = labels_of(issue)
    body = issue.get("body") or ""
    meta = parse_meta(body)
    if EPIC in labels:
        problems.append("epics are never worked directly; decompose into tasks")
    if SPIKE in labels and HUMAN_APPROVED not in labels:
        problems.append("spikes need a human decision (label human:approved to allow an agent)")
    if not meta["has_block"]:
        problems.append("missing <!-- verifi-agent --> metadata block")
    if meta["phase"] == 99 or meta["seq"] == 9999:
        problems.append("metadata block needs phase and seq")
    if len(labels & {RISK_LOW, RISK_HIGH}) != 1:
        problems.append("needs exactly one of risk:low / risk:high")
    if meta["size"] not in ("s", "m"):
        problems.append("size must be s or m (split anything larger)")
    if not re.search(r"^##\s+Acceptance criteria", body, re.M | re.I) or "- [ ]" not in body:
        problems.append("missing '## Acceptance criteria' checklist")
    if not re.search(r"^##\s+Tests to write first", body, re.M | re.I):
        problems.append("missing '## Tests to write first' section")
    if not re.search(r"^##\s+Verification", body, re.M | re.I):
        problems.append("missing '## Verification' section")
    return problems


def render_handoff(
    *,
    status: str,
    done: str,
    next_step: str,
    notes: str = "",
    session: str = "",
    branch: str = "",
    verification: str = "",
) -> str:
    attrs = f" status={status}" + (f" session={session}" if session else "")
    lines = [
        f"<!-- verifi-agent:handoff{attrs} -->",
        f"### Agent handoff: {status}",
        f"**Session:** `{session or 'n/a'}` · **Branch:** `{branch or 'n/a'}` · **Verification run:** `{verification or 'n/a'}`",
        "",
        "**Done so far**",
        done.strip() or "_nothing_",
        "",
        "**Exact next step**",
        next_step.strip() or "_none_",
    ]
    if notes.strip():
        lines += ["", "**Notes / risks**", notes.strip()]
    lines += ["", f"_Posted {now_iso()} via scripts/agent/agentctl.py_"]
    return "\n".join(lines)


def render_escalation(*, question: str, context: str, options: list[str], recommendation: str, session: str = "") -> str:
    attrs = f" session={session}" if session else ""
    lines = [
        f"<!-- verifi-agent:escalation{attrs} -->",
        "### Agent needs a human decision",
        "",
        "**Question**",
        question.strip(),
        "",
        "**Context**",
        context.strip() or "_none given_",
    ]
    if options:
        lines += ["", "**Options**"] + [f"{i}. {opt}" for i, opt in enumerate(options, 1)]
    if recommendation.strip():
        lines += ["", "**Agent recommendation**", recommendation.strip()]
    lines += [
        "",
        "To unblock: answer in a comment, then remove `needs:human` and `agent:blocked` and add `agent:ready`.",
        f"_Posted {now_iso()} via scripts/agent/agentctl.py_",
    ]
    return "\n".join(lines)


def render_discovered(*, kind: str, summary: str, evidence: str, suggested: str, found_while: int | None) -> str:
    lines = [
        f"<!-- verifi-agent:discovered kind={kind}" + (f" found_while={found_while}" if found_while else "") + " -->",
        "## Summary",
        summary.strip(),
        "",
        "## Evidence",
        evidence.strip() or "_none_",
        "",
        "## Suggested fix",
        suggested.strip() or "_unknown_",
        "",
    ]
    if found_while:
        lines += [f"Found while working on #{found_while}.", ""]
    lines += [
        "_Registered by an autonomous agent. A triager must add tests/acceptance criteria and the metadata block before `agent:ready`._"
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# GitHub access (via gh CLI)
# --------------------------------------------------------------------------- #


def run(argv: list[str], *, input_text: str | None = None, check: bool = True, cwd: Path = ROOT) -> str:
    exe = shutil.which(argv[0]) or argv[0]
    proc = subprocess.run(
        [exe, *argv[1:]],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )
    if check and proc.returncode != 0:
        raise AgentCtlError(f"`{' '.join(argv[:4])}` failed ({proc.returncode}): {proc.stderr.strip()[:2000]}")
    return proc.stdout


def gh_json(*args: str) -> Any:
    out = run(["gh", *args]).strip()
    return json.loads(out) if out else None


ISSUE_FIELDS = "number,title,body,labels,state,assignees"


def list_open_issues(limit: int = 500) -> list[dict[str, Any]]:
    return gh_json("issue", "list", "--state", "open", "--limit", str(limit), "--json", ISSUE_FIELDS)


def get_issue(number: int) -> dict[str, Any]:
    return gh_json("issue", "view", str(number), "--json", ISSUE_FIELDS + ",comments,url")


def edit_labels(number: int, *, add: tuple[str, ...] = (), remove: tuple[str, ...] = (), current: set[str] | None = None, pr: bool = False) -> None:
    add_l = [label for label in add if current is None or label not in current]
    remove_l = [label for label in remove if current is None or label in current]
    if not add_l and not remove_l:
        return
    argv = ["gh", "pr" if pr else "issue", "edit", str(number)]
    if add_l:
        argv += ["--add-label", ",".join(add_l)]
    if remove_l:
        argv += ["--remove-label", ",".join(remove_l)]
    run(argv)


def post_comment(number: int, body: str, *, pr: bool = False) -> None:
    run(["gh", "pr" if pr else "issue", "comment", str(number), "--body-file", "-"], input_text=body)


def emit(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, indent=2, default=str))


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def cmd_next(args: argparse.Namespace) -> int:
    issue, skipped = select_next(list_open_issues())
    data: dict[str, Any] = {"next": None, "skipped": [{"number": n, "reason": r} for n, r in skipped] if args.explain else None}
    if issue:
        meta = parse_meta(issue.get("body"))
        data["next"] = {
            "number": issue["number"],
            "title": issue["title"],
            "branch": branch_for(issue["number"], issue["title"]),
            "phase": meta["phase"],
            "seq": meta["seq"],
            "risk": meta["risk"],
        }
    emit(data, True)
    return 0 if issue else 2


def cmd_claim(args: argparse.Namespace) -> int:
    issue = get_issue(args.issue)
    labels = labels_of(issue)
    problems = []
    if issue.get("state") != "OPEN":
        problems.append("issue is not open")
    if READY not in labels:
        problems.append("issue is not agent:ready")
    problems += [f"issue has {label}" for label in NOT_SELECTABLE if label in labels]
    if problems and not args.force:
        emit({"ok": False, "problems": problems}, True)
        return 1
    edit_labels(args.issue, add=(IN_PROGRESS,), remove=(READY,), current=labels)
    run(["gh", "issue", "edit", str(args.issue), "--add-assignee", "@me"], check=False)
    branch = branch_for(issue["number"], issue["title"])
    post_comment(args.issue, f"<!-- verifi-agent:claim at={now_iso()} -->\nClaimed by the autonomous agent. Working branch: `{branch}`.")
    emit({"ok": True, "issue": args.issue, "branch": branch}, True)
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    issue = get_issue(args.issue)
    labels = labels_of(issue)
    target = READY if args.to == "ready" else BLOCKED
    edit_labels(args.issue, add=(target,), remove=(IN_PROGRESS, REVIEW), current=labels)
    post_comment(args.issue, f"<!-- verifi-agent:release to={args.to} -->\nReleased by the agent: {args.reason}")
    emit({"ok": True, "issue": args.issue, "now": target}, True)
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    issue = get_issue(args.issue)
    body = render_handoff(
        status=args.status,
        done=args.done,
        next_step=args.next,
        notes=args.notes,
        session=args.session,
        branch=args.branch,
        verification=args.verification,
    )
    post_comment(args.issue, body)
    if args.status == "blocked":
        edit_labels(args.issue, add=(BLOCKED,), remove=(IN_PROGRESS,), current=labels_of(issue))
    emit({"ok": True, "issue": args.issue, "status": args.status}, True)
    return 0


def cmd_escalate(args: argparse.Namespace) -> int:
    issue = get_issue(args.issue)
    body = render_escalation(
        question=args.question,
        context=args.context,
        options=args.option or [],
        recommendation=args.recommendation,
        session=args.session,
    )
    post_comment(args.issue, body)
    edit_labels(args.issue, add=(BLOCKED, NEEDS_HUMAN), remove=(IN_PROGRESS, READY, REVIEW), current=labels_of(issue))
    emit({"ok": True, "issue": args.issue, "labels_added": [BLOCKED, NEEDS_HUMAN]}, True)
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    existing = gh_json("issue", "list", "--state", "open", "--limit", "500", "--json", "number,title")
    for item in existing or []:
        if similar_titles(item["title"], args.title):
            note = render_discovered(kind=args.type, summary=args.summary, evidence=args.evidence, suggested=args.suggested_fix, found_while=args.found_while)
            post_comment(item["number"], "Possible duplicate report from an agent:\n\n" + note)
            emit({"ok": True, "duplicate_of": item["number"], "created": None}, True)
            return 0
    labels = [f"type:{args.type}", DISCOVERED, NEEDS_TRIAGE]
    if args.area:
        labels.append(f"area:{args.area}")
    body = render_discovered(kind=args.type, summary=args.summary, evidence=args.evidence, suggested=args.suggested_fix, found_while=args.found_while)
    url = run(["gh", "issue", "create", "--title", args.title, "--label", ",".join(labels), "--body-file", "-"], input_text=body).strip()
    number = int(url.rstrip("/").rsplit("/", 1)[-1]) if url else None
    if args.found_while and number:
        post_comment(args.found_while, f"<!-- verifi-agent:registered issue={number} -->\nRegistered follow-up #{number} (out of scope for this issue).")
    emit({"ok": True, "created": number, "url": url}, True)
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    issue = get_issue(args.issue)
    meta = parse_meta(issue.get("body"))
    deps = []
    for dep in meta["depends_on"]:
        info = gh_json("issue", "view", str(dep), "--json", "number,title,state")
        deps.append(info)
    comments = issue.get("comments") or []
    data = {
        "number": issue["number"],
        "title": issue["title"],
        "url": issue.get("url"),
        "state": issue.get("state"),
        "labels": sorted(labels_of(issue)),
        "meta": meta,
        "branch": branch_for(issue["number"], issue["title"]),
        "dependencies": deps,
        "attempts": count_markers(comments, "session-start"),
        "last_session": last_session_id(comments),
        "body": issue.get("body"),
        "recent_comments": [{"author": (c.get("author") or {}).get("login"), "body": c.get("body")} for c in comments[-args.comments :]],
    }
    if args.json:
        emit(data, True)
        return 0
    print(f"# #{data['number']} {data['title']}\n")
    print(f"labels: {', '.join(data['labels'])}\nbranch: {data['branch']}\nattempts so far: {data['attempts']}  last session: {data['last_session']}")
    for dep in deps:
        print(f"depends on #{dep['number']} [{dep['state']}] {dep['title']}")
    print("\n" + (data["body"] or ""))
    for c in data["recent_comments"]:
        print(f"\n---\n**{c['author']}**:\n{c['body']}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    issue = get_issue(args.issue)
    problems = definition_of_ready(issue)
    labels = labels_of(issue)
    if NEEDS_HUMAN in labels:
        problems.append("issue is waiting on needs:human")
    if problems:
        emit({"ok": False, "issue": args.issue, "problems": problems}, True)
        return 1
    edit_labels(args.issue, add=(READY,), remove=(NEEDS_TRIAGE, DISCOVERED), current=labels)
    emit({"ok": True, "issue": args.issue, "now": READY}, True)
    return 0


def cmd_pr_status(args: argparse.Namespace) -> int:
    prs = gh_json(
        "pr", "list", "--state", "open", "--limit", "100", "--json",
        "number,title,headRefName,headRefOid,labels,reviewDecision,mergeable,statusCheckRollup,isDraft",
    )
    out = []
    for pr in prs or []:
        if not pr["headRefName"].startswith("agent/"):
            continue
        comments = (gh_json("pr", "view", str(pr["number"]), "--json", "comments") or {}).get("comments")
        attempts = count_markers(comments, "resume")
        last = last_marker(comments, "resume") or {}
        out.append({
            "number": pr["number"],
            "title": pr["title"],
            "branch": pr["headRefName"],
            "issue": issue_number_from_branch(pr["headRefName"]),
            "checks": check_state(pr.get("statusCheckRollup")),
            "review": pr.get("reviewDecision"),
            "resume_attempts": attempts,
            "action": evaluate_pr(pr, attempts=attempts, last_resume_sha=last.get("sha")),
        })
    emit(out, True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentctl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("next", help="print the next workable issue as JSON (exit 2 if none)")
    p.add_argument("--explain", action="store_true", help="also list skipped issues and why")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("claim", help="mark an issue in-progress and assign it to yourself")
    p.add_argument("issue", type=int)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("release", help="give an issue back to the queue or mark it blocked")
    p.add_argument("issue", type=int)
    p.add_argument("--to", choices=("ready", "blocked"), required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("handoff", help="post a structured handoff so the next session can continue")
    p.add_argument("issue", type=int)
    p.add_argument("--status", choices=("partial", "blocked", "done"), required=True)
    p.add_argument("--done", required=True, help="what is finished (markdown bullets)")
    p.add_argument("--next", required=True, help="the single exact next step")
    p.add_argument("--notes", default="")
    p.add_argument("--session", default="")
    p.add_argument("--branch", default="")
    p.add_argument("--verification", default="", help="latest .verification run id")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("escalate", help="ask a human; labels the issue blocked + needs:human")
    p.add_argument("issue", type=int)
    p.add_argument("--question", required=True)
    p.add_argument("--context", default="")
    p.add_argument("--option", action="append", help="repeatable")
    p.add_argument("--recommendation", default="")
    p.add_argument("--session", default="")
    p.set_defaults(func=cmd_escalate)

    p = sub.add_parser("register", help="register a newly discovered problem as an issue (deduplicated)")
    p.add_argument("--type", choices=("bug", "task", "chore", "spike", "docs"), required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--evidence", default="")
    p.add_argument("--suggested-fix", default="")
    p.add_argument("--found-while", type=int)
    p.add_argument("--area")
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("context", help="everything a session needs to know about an issue")
    p.add_argument("issue", type=int)
    p.add_argument("--comments", type=int, default=6)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("promote", help="triage: move an issue to agent:ready if it meets the Definition of Ready")
    p.add_argument("issue", type=int)
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("pr-status", help="list agent PRs with the action the runner would take")
    p.set_defaults(func=cmd_pr_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except AgentCtlError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
