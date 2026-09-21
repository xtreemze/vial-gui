#!/usr/bin/env python3
"""Reject Ruff regressions in touched fork-owned Python modules."""

from __future__ import annotations

import argparse
import collections
import fnmatch
import json
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


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
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


def ruff_diagnostics(paths: list[Path]) -> collections.Counter[tuple[str, str, str]]:
    if not paths:
        return collections.Counter()

    command = [
        "ruff",
        "check",
        "--config",
        str(ROOT / "pyproject.toml"),
        "--output-format=json",
        "--exit-zero",
        *[str(path) for path in paths],
    ]
    result = run(*command)
    diagnostics = json.loads(result.stdout)
    counter: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for diagnostic in diagnostics:
        filename = Path(diagnostic["filename"])
        marker = "src/main/python/"
        normalized = filename.as_posix()
        if marker in normalized:
            normalized = marker + normalized.split(marker, 1)[1]
        counter[(normalized, diagnostic["code"], diagnostic["message"])] += 1
    return counter


def materialize_base(base: str, paths: list[str], directory: Path) -> list[Path]:
    materialized: list[Path] = []
    for relative in paths:
        shown = run("git", "show", f"{base}:{relative}", check=False)
        if shown.returncode != 0:
            continue
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(shown.stdout, encoding="utf-8")
        materialized.append(destination)
    return materialized


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

    head = ruff_diagnostics([ROOT / path for path in paths])
    with tempfile.TemporaryDirectory(prefix="vial-gui-ruff-base-") as temp:
        base_paths = materialize_base(args.base, paths, Path(temp))
        baseline = ruff_diagnostics(base_paths)

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
