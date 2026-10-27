#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPILER = ROOT / "compiler.py"
TESTS = Path(__file__).resolve().parent


def run_case(source: Path, expected: Path, should_succeed: bool,
             semantic: bool = False) -> str | None:
    with tempfile.TemporaryDirectory(prefix="epistula-error-") as directory:
        output = Path(directory) / "rejected.ll"
        command = ([sys.executable, str(COMPILER), str(source), str(output)]
                   if semantic else
                   [sys.executable, str(COMPILER), "--ast", str(source)])
        completed = subprocess.run(
            command, cwd=ROOT, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        if semantic and output.exists():
            return "compiler left an output file after a semantic error"
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


def run_end_to_end(source: Path) -> str | None:
    expected = source.with_suffix(".expected")
    if not expected.exists():
        return f"missing {expected.name}"
    input_file = source.with_suffix(".in")
    input_data = input_file.read_bytes() if input_file.exists() else b""
    with tempfile.TemporaryDirectory(prefix="epistula-e2e-") as directory:
        temporary = Path(directory)
        llvm_file = temporary / "program.ll"
        object_file = temporary / "program.o"
        executable = temporary / "program"
        commands = [
            [sys.executable, str(COMPILER), str(source), str(llvm_file)],
            ["llc", "-relocation-model=pic", "-filetype=obj",
             str(llvm_file), "-o", str(object_file)],
            ["clang", str(object_file), "-o", str(executable)],
        ]
        for command in commands:
            try:
                completed = subprocess.run(command, cwd=ROOT, capture_output=True,
                                           timeout=15, check=False)
            except FileNotFoundError:
                return f"tool not found: {command[0]}"
            if completed.returncode:
                return (f"{command[0]} failed ({completed.returncode}): "
                        f"{completed.stderr.decode('utf-8', 'replace').strip()}")
        completed = subprocess.run([str(executable)], input=input_data,
                                   capture_output=True, timeout=15, check=False)
        exit_file, stderr_file = source.with_suffix(".exit"), source.with_suffix(".stderr")
        expected_exit = int(exit_file.read_text()) if exit_file.exists() else 0
        expected_stderr = stderr_file.read_bytes() if stderr_file.exists() else b""
        if completed.returncode != expected_exit:
            return f"expected exit {expected_exit}, got {completed.returncode}: {completed.stderr!r}"
        if completed.stdout != expected.read_bytes():
            return (f"output differs: expected {expected.read_bytes()!r}, "
                    f"got {completed.stdout!r}")
        if completed.stderr != expected_stderr:
            return f"stderr differs: expected {expected_stderr!r}, got {completed.stderr!r}"
    return None


def main() -> int:
    failures: list[str] = []
    total = 0
    for directory_name, suffix, should_succeed, semantic in (
        ("valid", ".ast", True, False),
        ("invalid", ".err", False, False),
        ("semantic_invalid", ".err", False, True),
    ):
        directory = TESTS / directory_name
        sources = sorted(directory.glob("*.em"))
        if directory_name in ("valid", "invalid") and len(sources) < 15:
            failures.append(f"{directory_name}: fewer than 15 source tests")
        for source in sources:
            total += 1
            expected = source.with_suffix(suffix)
            if not expected.exists():
                failures.append(f"{source.name}: missing {expected.name}")
                continue
            try:
                failure = run_case(source, expected, should_succeed, semantic)
            except subprocess.TimeoutExpired:
                failure = "compiler exceeded the 10-second test timeout"
            if failure is not None:
                failures.append(f"{source.name}: {failure}")

    end_to_end = sorted((TESTS / "e2e").glob("*.em"))
    if len(end_to_end) < 10:
        failures.append("e2e: fewer than 10 executable source tests")
    if not any(source.with_suffix(".in").exists() for source in end_to_end):
        failures.append("e2e: no input test with a .in file")
    for source in end_to_end + sorted((TESTS / "runtime_invalid").glob("*.em")):
        total += 1
        try:
            failure = run_end_to_end(source)
        except subprocess.TimeoutExpired:
            failure = "compile or run exceeded the 15-second timeout"
        if failure is not None:
            failures.append(f"{source.name}: {failure}")
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if failures:
        print(f"FAILED: {len(failures)} of {total} file tests")
        for failure in failures:
            print(f"- {failure}")
    else:
        print(f"OK: {total} file tests passed")
    return 0 if not failures and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
