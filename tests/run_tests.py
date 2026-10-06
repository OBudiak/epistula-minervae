#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "compiler.py"
TESTS = Path(__file__).resolve().parent


def run_case(source: Path, expected: Path, should_succeed: bool) -> str | None:
    completed = subprocess.run(
        [sys.executable, str(COMPILER), "--ast", str(source)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )
    expected_text = expected.read_text(encoding="utf-8")

    if should_succeed:
        if completed.returncode != 0:
            return f"expected exit 0, got {completed.returncode}; stderr={completed.stderr!r}"
        if completed.stderr:
            return f"expected empty stderr, got {completed.stderr!r}"
        if completed.stdout != expected_text:
            return "AST output differs from the golden file"
    else:
        if completed.returncode == 0:
            return "expected non-zero exit code"
        if completed.stdout:
            return f"expected empty stdout, got {completed.stdout!r}"
        if (
            not completed.stderr.startswith("compilation error: line ")
            or not completed.stderr.endswith("\n")
            or completed.stderr.count("\n") != 1
        ):
            return "expected exactly one formatted compilation-error line"
        if completed.stderr != expected_text:
            return f"error differs: expected {expected_text!r}, got {completed.stderr!r}"
    return None


def main() -> int:
    failures: list[str] = []
    total = 0
    for directory_name, suffix, should_succeed in (
        ("valid", ".ast", True),
        ("invalid", ".err", False),
    ):
        directory = TESTS / directory_name
        sources = sorted(directory.glob("*.em"))
        if len(sources) < 15:
            failures.append(f"{directory_name}: fewer than 15 source tests")
        for source in sources:
            total += 1
            expected = source.with_suffix(suffix)
            if not expected.exists():
                failures.append(f"{source.name}: missing {expected.name}")
                continue
            try:
                failure = run_case(source, expected, should_succeed)
            except subprocess.TimeoutExpired:
                failure = "compiler exceeded the 10-second test timeout"
            if failure is not None:
                failures.append(f"{source.name}: {failure}")

    if failures:
        print(f"FAILED: {len(failures)} of {total} tests")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"OK: {total} tests passed")
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
