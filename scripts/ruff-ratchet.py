#!/usr/bin/env python3
"""Reject Ruff regressions in touched fork-owned Python modules."""

from __future__ import annotations

import argparse
import collections
import fnmatch
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED_PATTERNS = (
    "src/main/python/custom_*.py",
    "src/main/python/editor/halcyon*.py",
    "src/main/python/protocol/rgb_profiles.py",
    "src/main/python/protocol/halcyon*.py",
)


def run(
    *args: str,
    cwd: Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def changed_owned_files(base: str) -> list[str]:
    output = run(
        "git",
        "diff",
        "--name-only",
        "--diff-filter=AMR",
        base,
        "HEAD",
        "--",
        "*.py",
    ).stdout
    return sorted(
        path
        for path in output.splitlines()
        if any(fnmatch.fnmatch(path, pattern) for pattern in OWNED_PATTERNS)
    )


def ruff_diagnostics(
    repository: Path,
    paths: list[str],
) -> collections.Counter[tuple[str, str, str]]:
    existing = [path for path in paths if (repository / path).is_file()]
    if not existing:
        return collections.Counter()

    command = [
        "ruff",
        "check",
        "--config",
        str(repository / "pyproject.toml"),
        "--output-format=json",
        "--exit-zero",
        *existing,
    ]
    result = run(*command, cwd=repository)
    diagnostics = json.loads(result.stdout)
    counter: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for diagnostic in diagnostics:
        filename = Path(diagnostic["filename"])
        try:
            normalized = filename.resolve().relative_to(repository.resolve()).as_posix()
        except ValueError:
            normalized = filename.as_posix()
        counter[(normalized, diagnostic["code"], diagnostic["message"])] += 1
    return counter


def baseline_diagnostics(
    base: str,
    paths: list[str],
) -> collections.Counter[tuple[str, str, str]]:
    with tempfile.TemporaryDirectory(prefix="vial-gui-ruff-") as parent:
        worktree = Path(parent) / "base"
        run("git", "worktree", "add", "--detach", str(worktree), base)
        try:
            shutil.copy2(ROOT / "pyproject.toml", worktree / "pyproject.toml")
            return ruff_diagnostics(worktree, paths)
        finally:
            run("git", "worktree", "remove", "--force", str(worktree), check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    args = parser.parse_args()

    paths = changed_owned_files(args.base)
    if not paths:
        print("No changed fork-owned Python modules require Ruff.")
        return 0

    print("Strict Ruff ratchet targets:")
    for path in paths:
        print(f"  {path}")

    head = ruff_diagnostics(ROOT, paths)
    baseline = baseline_diagnostics(args.base, paths)

    regressions: list[tuple[tuple[str, str, str], int, int]] = []
    for signature, head_count in head.items():
        baseline_count = baseline[signature]
        if head_count > baseline_count:
            regressions.append((signature, baseline_count, head_count))

    if regressions:
        print("Ruff regressions introduced by this change:")
        for (path, code, message), before, after in sorted(regressions):
            print(f"  {path}: {code}: {message} ({before} -> {after})")
        return 1

    print(
        f"Ruff strict ratchet: clean ({sum(baseline.values())} baseline diagnostics; "
        f"{sum(head.values())} on head)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
