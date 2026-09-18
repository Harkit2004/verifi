#!/usr/bin/env python3
"""verifi verification gate. The ONE command that decides if work is acceptable.

Runs every quality stage, stores full logs under .verification/<run-id>/, and
writes summary.json + summary.md. Agents cite the run id in PRs and handoffs.

  python scripts/verify.py                         # full gate (what CI runs)
  python scripts/verify.py --stage tests --pytest-args tests/unit/spec
  python scripts/verify.py --expect-fail --label red --pytest-args tests/unit/spec/test_x.py
  python scripts/verify.py --list 5                # recent runs
  python scripts/verify.py --show latest           # print a stored summary

Stdlib only; works before the Python package exists (harness stage only).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / ".verification"

# Paths an agent branch may not touch without the human:approved label.
PROTECTED_PREFIXES = (
    "AGENTS.md",
    "CLAUDE.md",
    "opencode.json",
    ".opencode/",
    ".github/",
    "docs/architecture/",
    "docs/adr/",
    "docs/process/",
    "scripts/agent/",
    "scripts/verify.py",
)
# Generated/lock files do not count toward the minimal-diff budget.
DIFF_EXCLUDE_PREFIXES = ("uv.lock", "schemas/", "tests/golden/")
DIFF_WARN_LINES = 300
DIFF_FAIL_LINES = 800
STAGE_ORDER = ("harness", "sync", "format", "lint", "types", "tests", "diff", "protected")
TAIL_LINES = 60


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #


def parse_numstat(text: str) -> dict[str, Any]:
    files: list[str] = []
    added = removed = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, r, path = parts
        path = path.strip()
        if "=>" in path:  # rename: keep destination
            path = path.split("=>")[-1].strip(" {}")
        if path in files:
            continue
        files.append(path)
        if path.startswith(DIFF_EXCLUDE_PREFIXES) or a == "-" or r == "-":
            continue
        added += int(a)
        removed += int(r)
    return {"files": files, "added": added, "removed": removed, "changed_lines": added + removed}


def protected_violations(paths: list[str]) -> list[str]:
    return [p for p in paths if p.replace("\\", "/").startswith(PROTECTED_PREFIXES)]


def diff_verdict(changed_lines: int) -> str:
    if changed_lines > DIFF_FAIL_LINES:
        return "fail"
    if changed_lines > DIFF_WARN_LINES:
        return "warn"
    return "ok"


def red_run_ok(exit_code: int) -> bool:
    """A red (expected-failure) test run is valid only if tests ran and failed
    (pytest 1) or could not import the not-yet-written code (pytest 2)."""
    return exit_code in (1, 2)


def run_id(sha: str, label: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{sha[:7] or 'nogit'}-{label}"


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    except FileNotFoundError:
        return ""


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    proc = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True)
    return proc.returncode == 0


def base_ref() -> str | None:
    for ref in ("origin/main", "main"):
        if git("rev-parse", "--verify", "--quiet", ref):
            return ref
    return None


def collect_diff() -> dict[str, Any]:
    ref = base_ref()
    if not ref:
        return parse_numstat("")
    merge_base = git("merge-base", ref, "HEAD") or ref
    committed = git("diff", "--numstat", merge_base, "HEAD")
    working = git("diff", "--numstat", "HEAD")
    untracked = git("ls-files", "--others", "--exclude-standard")
    extra = "\n".join(f"0\t0\t{p}" for p in untracked.splitlines() if p)
    return parse_numstat("\n".join([committed, working, extra]))


class Gate:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.sha = git("rev-parse", "HEAD")
        # In PR CI the checkout is a detached merge ref; GITHUB_HEAD_REF holds the real branch.
        self.branch = os.environ.get("GITHUB_HEAD_REF") or git("rev-parse", "--abbrev-ref", "HEAD")
        self.id = run_id(self.sha, args.label)
        self.dir = OUT_ROOT / self.id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.has_package = (ROOT / "pyproject.toml").exists()
        self.results: list[dict[str, Any]] = []

    def stages(self) -> list[str]:
        if self.args.expect_fail:
            return ["tests"]
        wanted = self.args.stage or list(STAGE_ORDER)
        return [s for s in STAGE_ORDER if s in wanted]

    def command_for(self, stage: str) -> list[str] | None:
        uv = shutil.which("uv") or "uv"
        if stage == "harness":
            return [sys.executable, "-m", "unittest", "discover", "-s", "scripts/agent/tests", "-p", "test_*.py"]
        if not self.has_package:
            return None
        if stage == "sync":
            return [uv, "sync", "--locked"] if self.args.ci and (ROOT / "uv.lock").exists() else [uv, "sync"]
        if stage == "format":
            return [uv, "run", "ruff", "format", "--check", "."]
        if stage == "lint":
            return [uv, "run", "ruff", "check", "."]
        if stage == "types":
            return [uv, "run", "mypy"]
        if stage == "tests":
            use_docker = self.args.docker == "on" or (self.args.docker == "auto" and docker_available())
            marker = [] if use_docker else ["-m", "not docker"]
            extra = shlex.split(self.args.pytest_args) if self.args.pytest_args else []
            return [uv, "run", "pytest", "-q", *marker, f"--junitxml={self.dir / 'junit.xml'}", *extra]
        return None

    def run_process_stage(self, stage: str, argv: list[str]) -> dict[str, Any]:
        log_path = self.dir / f"{stage}.log"
        started = time.monotonic()
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            output, code = (proc.stdout or "") + (proc.stderr or ""), proc.returncode
        except FileNotFoundError as exc:
            output, code = f"{exc}\nTool missing. Run: python scripts/agent/bootstrap.py --install\n", 127
        log_path.write_text(f"$ {' '.join(argv)}\n\n{output}", encoding="utf-8")
        passed = red_run_ok(code) if (stage == "tests" and self.args.expect_fail) else code == 0
        result = {
            "name": stage,
            "command": " ".join(argv),
            "exit_code": code,
            "status": "pass" if passed else "fail",
            "duration_s": round(time.monotonic() - started, 2),
            "log": str(log_path.relative_to(ROOT)).replace("\\", "/"),
        }
        if stage == "tests" and self.args.expect_fail and code == 5:
            result["note"] = "no tests were collected: a red run needs a failing test"
        if not passed:
            result["tail"] = output.splitlines()[-TAIL_LINES:]
        return result

    def run_diff_stage(self) -> dict[str, Any]:
        diff = collect_diff()
        (self.dir / "diff.json").write_text(json.dumps(diff, indent=2), encoding="utf-8")
        verdict = diff_verdict(diff["changed_lines"])
        status = "fail" if verdict == "fail" and not self.args.allow_large_diff else ("warn" if verdict != "ok" else "pass")
        return {
            "name": "diff",
            "status": status,
            "changed_lines": diff["changed_lines"],
            "files": len(diff["files"]),
            "note": f"warn > {DIFF_WARN_LINES}, fail > {DIFF_FAIL_LINES} changed lines (lock/schema/golden excluded)",
        }

    def run_protected_stage(self) -> dict[str, Any]:
        if not self.branch.startswith("agent/"):
            return {"name": "protected", "status": "skip", "note": "only enforced on agent/* branches"}
        violations = protected_violations(collect_diff()["files"])
        allowed = os.environ.get("VERIFI_ALLOW_PROTECTED") == "1"
        status = "pass" if not violations or allowed else "fail"
        result: dict[str, Any] = {"name": "protected", "status": status, "violations": violations}
        if violations and not allowed:
            result["note"] = "agent branches may not edit these paths; escalate instead (skill: escalate-to-human)"
        return result

    def run(self) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        for stage in self.stages():
            if stage == "diff":
                self.results.append(self.run_diff_stage())
            elif stage == "protected":
                self.results.append(self.run_protected_stage())
            else:
                argv = self.command_for(stage)
                if argv is None:
                    self.results.append({"name": stage, "status": "skip", "note": "no pyproject.toml yet"})
                    continue
                result = self.run_process_stage(stage, argv)
                self.results.append(result)
                if stage == "sync" and result["status"] == "fail":
                    break
        failed = [r["name"] for r in self.results if r["status"] == "fail"]
        summary = {
            "schema": "verifi.verification-run/v1",
            "id": self.id,
            "label": self.args.label,
            "mode": "red" if self.args.expect_fail else "gate",
            "result": "pass" if not failed else "fail",
            "failed_stages": failed,
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git": {"sha": self.sha, "branch": self.branch, "dirty": bool(git("status", "--porcelain"))},
            "host": {"os": platform.system(), "python": platform.python_version(), "ci": self.args.ci},
            "pytest_args": self.args.pytest_args,
            "stages": self.results,
        }
        (self.dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (self.dir / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
        (OUT_ROOT / "latest").write_text(self.id, encoding="utf-8")
        return summary


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"### Verification run `{summary['id']}`: **{summary['result'].upper()}** ({summary['mode']})",
        "",
        f"commit `{summary['git']['sha'][:10]}` on `{summary['git']['branch']}`" + (" (dirty tree)" if summary["git"]["dirty"] else ""),
        "",
        "| stage | status | detail |",
        "|---|---|---|",
    ]
    for stage in summary["stages"]:
        detail = stage.get("note") or (f"exit {stage['exit_code']}, {stage['duration_s']}s" if "exit_code" in stage else "")
        if stage["name"] == "diff":
            detail = f"{stage['changed_lines']} lines in {stage['files']} files"
        lines.append(f"| {stage['name']} | {stage['status']} | {detail} |")
    return "\n".join(lines) + "\n"


def list_runs(count: int) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(OUT_ROOT.glob("*/summary.json"), reverse=True)[:count]:
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append({k: data[k] for k in ("id", "mode", "result", "failed_stages")})
    return runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", action="append", choices=STAGE_ORDER, help="run only these stages (repeatable)")
    parser.add_argument("--label", default="gate", help="suffix for the run id, e.g. red / green / ci")
    parser.add_argument("--expect-fail", action="store_true", help="record a TDD red run: passes only if tests fail")
    parser.add_argument("--pytest-args", default="", help="extra pytest args, e.g. a test path")
    parser.add_argument("--docker", choices=("auto", "on", "off"), default="auto")
    parser.add_argument("--allow-large-diff", action="store_true", help="humans only; agents must split work instead")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--json", action="store_true", help="print summary JSON only")
    parser.add_argument("--list", type=int, metavar="N", help="show the N most recent runs")
    parser.add_argument("--show", metavar="RUN_ID", help="print a stored summary ('latest' works)")
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps(list_runs(args.list), indent=2))
        return 0
    if args.show:
        run = (OUT_ROOT / "latest").read_text(encoding="utf-8").strip() if args.show == "latest" else args.show
        print((OUT_ROOT / run / ("summary.json" if args.json else "summary.md")).read_text(encoding="utf-8"))
        return 0

    summary = Gate(args).run()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_markdown(summary))
        for stage in summary["stages"]:
            if stage["status"] == "fail" and stage.get("tail"):
                print(f"--- {stage['name']} (last lines; full log: {stage['log']}) ---")
                print("\n".join(stage["tail"]))
        print(f"\nstored: .verification/{summary['id']}/summary.json")
    return 0 if summary["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
