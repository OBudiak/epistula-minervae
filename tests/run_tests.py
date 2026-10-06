#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "compiler.py"
TESTS = Path(__file__).resolve().parent


def run_case(source: Path, expected: Path, should_succeed: bool) -> str | None:
    completed = subprocess.run(
        [sys.executable, str(COMPILER), "--ast", str(source)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
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
        for source in sorted(directory.glob("*.em")):
            total += 1
            expected = source.with_suffix(suffix)
            if not expected.exists():
                failures.append(f"{source.name}: missing {expected.name}")
                continue
            failure = run_case(source, expected, should_succeed)
            if failure is not None:
                failures.append(f"{source.name}: {failure}")

    if failures:
        print(f"FAILED: {len(failures)} of {total} tests")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"OK: {total} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

