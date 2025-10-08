#!/usr/bin/env python3
"""Bootstrap local development prerequisites for Ultimate MCP."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
VENV_PATH = BACKEND_DIR / ".venv"


def run(command: list[str], cwd: Path | None = None) -> None:
    cwd = cwd or REPO_ROOT
    print(f"→ Running {' '.join(command)} (cwd={cwd})")
    subprocess.run(command, cwd=str(cwd), check=True)


def ensure_virtualenv(python: str) -> None:
    if not VENV_PATH.exists():
        run([python, "-m", "venv", str(VENV_PATH)])
    pip = VENV_PATH / "bin" / "pip"
    run([str(pip), "install", "--upgrade", "pip"], cwd=BACKEND_DIR)
    run([str(pip), "install", "-r", "requirements.txt"], cwd=BACKEND_DIR)


def ensure_node_modules(use_ci: bool) -> None:
    package_lock = FRONTEND_DIR / "package-lock.json"
    npm_command = ["npm", "ci" if package_lock.exists() else "install"]
    if use_ci:
        npm_command = ["npm", "ci"]
    run(npm_command, cwd=FRONTEND_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup development tooling")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for the backend venv")
    parser.add_argument("--ci", action="store_true", help="Force deterministic installs (npm ci)")
    args = parser.parse_args()

    ensure_virtualenv(args.python)
    ensure_node_modules(args.ci)
    print("✔ Setup complete. Activate the backend venv with 'source backend/.venv/bin/activate'.")


if __name__ == "__main__":
    main()
