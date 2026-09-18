#!/usr/bin/env python3
"""bootstrap: check (and optionally install) the toolchain the agent needs.

  python scripts/agent/bootstrap.py            # report only (JSON)
  python scripts/agent/bootstrap.py --install  # install what is safely installable

Required: git, gh (authenticated), uv, Python 3.12 (via uv), opencode.
Optional: docker (needed only for tests marked `docker` and Tier-1 sandboxes).

Only tools in this file may be installed by an agent. Anything else: escalate.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_VERSION = "3.12"
IS_WINDOWS = platform.system() == "Windows"

INSTALLERS = {
    "uv": (
        ["powershell", "-ExecutionPolicy", "ByPass", "-c", "irm https://astral.sh/uv/install.ps1 | iex"]
        if IS_WINDOWS
        else ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"]
    ),
    "opencode": ["npm", "install", "-g", "opencode-ai"],
}
MANUAL = {
    "git": "https://git-scm.com/downloads",
    "gh": "https://cli.github.com/ (then: gh auth login)",
    "docker": "https://docs.docker.com/get-docker/ (optional)",
}


def probe(argv: list[str]) -> tuple[bool, str]:
    exe = shutil.which(argv[0])
    if not exe:
        return False, "not found"
    proc = subprocess.run([exe, *argv[1:]], capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = (proc.stdout or proc.stderr).strip().splitlines()
    return proc.returncode == 0, text[0] if text else ""


def check() -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for name, argv in {
        "git": ["git", "--version"],
        "gh": ["gh", "--version"],
        "uv": ["uv", "--version"],
        "opencode": ["opencode", "--version"],
        "docker": ["docker", "info", "--format", "{{.ServerVersion}}"],
    }.items():
        ok, detail = probe(argv)
        report[name] = {"ok": ok, "detail": detail, "required": name != "docker"}
    ok, detail = probe(["gh", "auth", "status"])
    report["gh-auth"] = {"ok": ok, "detail": detail or "run: gh auth login", "required": True}
    if report["uv"]["ok"]:
        ok, detail = probe(["uv", "python", "find", PYTHON_VERSION])
        report["python"] = {"ok": ok, "detail": detail or f"run: uv python install {PYTHON_VERSION}", "required": True}
    labels_ok, detail = probe([sys.executable, str(ROOT / "scripts/agent/setup_labels.py"), "--check"])
    report["github-labels"] = {"ok": labels_ok, "detail": detail or "run: python scripts/agent/setup_labels.py --apply", "required": True}
    return report


def install(report: dict[str, dict[str, object]]) -> list[str]:
    actions = []
    for name, argv in INSTALLERS.items():
        if not report.get(name, {}).get("ok") and shutil.which(argv[0]):
            actions.append(f"install {name}")
            subprocess.run(argv, check=False)
    if shutil.which("uv"):
        subprocess.run(["uv", "python", "install", PYTHON_VERSION], check=False)
        actions.append(f"uv python install {PYTHON_VERSION}")
        if (ROOT / "pyproject.toml").exists():
            subprocess.run(["uv", "sync"], cwd=ROOT, check=False)
            actions.append("uv sync")
    for directory in (".agent", ".verification"):
        (ROOT / directory).mkdir(exist_ok=True)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    report = check()
    actions: list[str] = []
    if args.install:
        actions = install(report)
        report = check()
    missing = [name for name, item in report.items() if item["required"] and not item["ok"]]
    print(json.dumps({"ok": not missing, "missing": missing, "manual_install": {k: v for k, v in MANUAL.items() if k in missing}, "actions": actions, "tools": report}, indent=2))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
