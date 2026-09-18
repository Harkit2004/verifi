#!/usr/bin/env python3
"""setup_labels: create/update the GitHub labels and milestones the agent workflow relies on.

  python scripts/agent/setup_labels.py --check   # exit 1 if anything is missing
  python scripts/agent/setup_labels.py --apply   # create or update
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agentctl as ac  # noqa: E402

LABELS: dict[str, tuple[str, str]] = {
    # agent state machine (see docs/process/workflow.md)
    "agent:ready": ("0e8a16", "Fully specified; the agent may pick it up once dependencies are closed"),
    "agent:in-progress": ("fbca04", "Claimed by an agent session"),
    "agent:review": ("1d76db", "Agent opened a PR; waiting on CI / review / merge"),
    "agent:blocked": ("b60205", "Agent cannot continue; see the latest escalation or handoff comment"),
    "agent:discovered": ("c5def5", "Registered by an agent while working on something else"),
    "needs:human": ("d93f0b", "A human decision or review is required"),
    "needs:triage": ("ededed", "Not yet meeting the Definition of Ready"),
    "agent:pause": ("000000", "Kill switch: while any open issue has this label, the runner does nothing"),
    "human:approved": ("5319e7", "A human approved: high-risk PR may merge / protected paths may change / spike may be worked"),
    # type
    "type:epic": ("3e4b9e", "Parent issue grouping tasks; never worked directly"),
    "type:task": ("0052cc", "Implementable unit of work"),
    "type:bug": ("d73a4a", "Defect"),
    "type:chore": ("bfdadc", "Maintenance / tooling"),
    "type:spike": ("f9d0c4", "Research or decision; output is an ADR or doc, needs a human decision"),
    "type:docs": ("0075ca", "Documentation only"),
    # risk
    "risk:low": ("c2e0c6", "Runner may auto-merge when CI is green"),
    "risk:high": ("e99695", "Touches a security boundary or verdict logic; human must review the PR"),
    # size
    "size:s": ("ededed", "Under ~150 changed lines"),
    "size:m": ("d4c5f9", "Under ~400 changed lines"),
    # phases
    "phase:0": ("f7f7f7", "Foundation"),
    "phase:1": ("f7f7f7", "Core verification loop"),
    "phase:2": ("f7f7f7", "Adversarial engine"),
    "phase:3": ("f7f7f7", "Adaptive attacker"),
    "phase:4": ("f7f7f7", "Platform (API/UI)"),
}
AREAS = ["harness", "cli", "core", "spec", "runs", "evidence", "sandbox", "world", "broker", "targets", "detectors", "scoring", "reports", "attacks", "adaptive", "api", "docs"]
for area in AREAS:
    LABELS[f"area:{area}"] = ("bfd4f2", f"Component: {area}")

MILESTONES = {
    "Phase 0: Foundation": "Package skeleton, CLI envelope, operation registry, run store primitives.",
    "Phase 1: Core verification loop": "Spec, fake+docker sandbox, broker, scripted target, host-side detectors, scoring, reports, `verifi run`.",
    "Phase 2: Adversarial engine": "Attack packs, injection vehicles, mutators, private packs, real targets.",
    "Phase 3: Adaptive attacker": "Search-based attack generation, exploit regression store, evaluation-integrity probes.",
    "Phase 4: Platform": "HTTP API from the operation registry, run index, UI (CLI parity required).",
}


def existing_labels() -> dict[str, dict[str, str]]:
    return {item["name"]: item for item in ac.gh_json("label", "list", "--limit", "300", "--json", "name,color,description") or []}


def existing_milestones(repo: str) -> set[str]:
    return {m["title"] for m in ac.gh_json("api", f"repos/{repo}/milestones?state=all&per_page=100") or []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    repo = ac.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()
    current = existing_labels()
    missing_labels = [name for name in LABELS if name not in current]
    missing_milestones = [title for title in MILESTONES if title not in existing_milestones(repo)]
    if args.check:
        print(json.dumps({"ok": not (missing_labels or missing_milestones), "missing_labels": missing_labels, "missing_milestones": missing_milestones}))
        return 0 if not (missing_labels or missing_milestones) else 1

    for name, (color, description) in LABELS.items():
        ac.run(["gh", "label", "create", name, "--color", color, "--description", description, "--force"])
    for title, description in MILESTONES.items():
        if title in missing_milestones:
            ac.run(["gh", "api", f"repos/{repo}/milestones", "-f", f"title={title}", "-f", f"description={description}"])
    print(json.dumps({"ok": True, "labels": len(LABELS), "milestones_created": missing_milestones}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
