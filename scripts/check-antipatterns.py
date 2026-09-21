#!/usr/bin/env python3
"""Enforce fork-owned Vial GUI safety and architecture invariants."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNED_PATTERNS = (
    "src/main/python/custom_*.py",
    "src/main/python/editor/halcyon*.py",
    "src/main/python/protocol/rgb_profiles.py",
    "src/main/python/protocol/halcyon*.py",
)
SUPPRESSION = re.compile(
    r"(?:#\s*noqa\b|#\s*type:\s*ignore\b|#\s*pylint:\s*disable\b|#\s*ruff:\s*noqa\b)",
    re.IGNORECASE,
)
NONDETERMINISTIC_CALLS = {
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "random.random",
    "random.randrange",
    "random.randint",
    "time.time",
    "uuid.uuid4",
}
DANGEROUS_CALLS = {
    "eval",
    "exec",
    "compile",
    "os.system",
    "os.popen",
    "pickle.loads",
    "pickle.load",
}
PROTOCOL_FORBIDDEN_IMPORT_PREFIXES = (
    "PyQt5",
    "PySide",
    "qtpy",
    "editor",
    "main_window",
    "widgets",
)


def iter_owned_files() -> list[Path]:
    return sorted(
        {
            path
            for pattern in OWNED_PATTERNS
            for path in ROOT.glob(pattern)
            if path.is_file()
        }
    )


def qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def mutable_default(node: ast.AST) -> bool:
    return isinstance(node, (ast.Dict, ast.List, ast.Set)) or (
        isinstance(node, ast.Call)
        and qualified_name(node.func) in {"dict", "list", "set", "defaultdict"}
    )


class PolicyVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[tuple[int, str, str]] = []

    def add(self, node: ast.AST, rule: str, message: str) -> None:
        self.violations.append((getattr(node, "lineno", 1), rule, message))

    def visit_Import(self, node: ast.Import) -> None:
        if "/protocol/" in self.path.as_posix():
            for alias in node.names:
                if alias.name.startswith(PROTOCOL_FORBIDDEN_IMPORT_PREFIXES):
                    self.add(
                        node,
                        "protocol-ui-leakage",
                        "Protocol modules must remain UI/framework independent.",
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if any(alias.name == "*" for alias in node.names):
            self.add(node, "wildcard-import", "Wildcard imports are forbidden.")
        if "/protocol/" in self.path.as_posix() and module.startswith(
            PROTOCOL_FORBIDDEN_IMPORT_PREFIXES
        ):
            self.add(
                node,
                "protocol-ui-leakage",
                "Protocol modules must remain UI/framework independent.",
            )
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.add(
            node,
            "global-mutation",
            "Mutable module-global ownership is forbidden; keep state on explicit owners.",
        )

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.add(
            node,
            "nonlocal-mutation",
            "Hidden closure mutation is forbidden; make ownership explicit.",
        )

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add(node, "bare-except", "Bare except handlers are forbidden.")
        else:
            caught = qualified_name(node.type)
            if caught in {"Exception", "BaseException"}:
                self.add(
                    node,
                    "broad-except",
                    "Catch the concrete failure modes at the boundary instead of Exception/BaseException.",
                )
        self.generic_visit(node)

    def _check_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        defaults = [*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]]
        for default in defaults:
            if mutable_default(default):
                self.add(
                    default,
                    "mutable-default",
                    "Mutable default arguments are forbidden.",
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_defaults(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = qualified_name(node.func)
        if name in DANGEROUS_CALLS:
            self.add(
                node,
                "dynamic-or-unsafe-execution",
                f"{name} is forbidden in fork-owned GUI code.",
            )
        if name in NONDETERMINISTIC_CALLS:
            self.add(
                node,
                "ambient-nondeterminism",
                f"{name} is forbidden in domain/state code; inject clocks/entropy explicitly.",
            )
        if name == "time.sleep":
            self.add(
                node,
                "blocking-ui-sleep",
                "Blocking sleeps are forbidden in GUI code; use event/timer-driven coordination.",
            )
        if name in {"subprocess.run", "subprocess.call", "subprocess.Popen"}:
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    self.add(
                        node,
                        "shell-true",
                        "subprocess shell=True is forbidden.",
                    )
        self.generic_visit(node)


def main() -> int:
    violations: list[str] = []
    for path in iter_owned_files():
        relative = path.relative_to(ROOT)
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            if SUPPRESSION.search(line):
                violations.append(
                    f"{relative}:{line_number}: lint-suppression: inline lint/type suppressions are forbidden"
                )

        try:
            tree = ast.parse(source, filename=str(relative))
        except SyntaxError as error:
            violations.append(
                f"{relative}:{error.lineno or 1}: syntax-error: {error.msg}"
            )
            continue

        visitor = PolicyVisitor(path)
        visitor.visit(tree)
        violations.extend(
            f"{relative}:{line}: {rule}: {message}"
            for line, rule, message in visitor.violations
        )

    if violations:
        print("Vial GUI anti-pattern policy violations:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return 1

    print("Vial GUI anti-pattern policy: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
