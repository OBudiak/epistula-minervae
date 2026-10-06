#!/usr/bin/env python3
"""Maintainer helper: regenerate golden files after an intentional AST change."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TESTS = Path(__file__).resolve().parent
COMPILER = ROOT / "compiler.py"


def main() -> int:
    for directory_name, suffix, expected_success in (
        ("valid", ".ast", True),
        ("invalid", ".err", False),
    ):
        for source in sorted((TESTS / directory_name).glob("*.em")):
            completed = subprocess.run(
                [sys.executable, str(COMPILER), "--ast", str(source)],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
            if (completed.returncode == 0) != expected_success:
                stream = completed.stderr or completed.stdout
                print(f"cannot generate {source.name}: {stream.decode('utf-8')}", end="")
                return 1
            output = completed.stdout if expected_success else completed.stderr
            source.with_suffix(suffix).write_bytes(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
