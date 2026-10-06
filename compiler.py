#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epistula.checks import OverflowChecker
from epistula.errors import CompilationError
from epistula.lexer import Lexer
from epistula.parser import Parser


def compile_ast(path: Path) -> str:
    try:
        source = path.read_bytes()
    except OSError as exc:
        raise CompilationError(1, 1, "Fasciculus legi non potest.") from exc
    tokens = Lexer(source).scan()
    parser = Parser(tokens)
    try:
        program = parser.parse_program()
        OverflowChecker().check(program)
        return program.dump()
    except RecursionError as exc:
        token = tokens[min(parser.index, len(tokens) - 1)]
        raise CompilationError(
            token.line, token.column, "Structura nimis profunda est."
        ) from exc


def main(argv: list[str] | None = None) -> int:
    # Stable UTF-8 output even on Windows or an ASCII system locale.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    argument_parser = argparse.ArgumentParser(
        description="Epistula Minervae stage-1 lexer and parser"
    )
    argument_parser.add_argument(
        "--ast",
        metavar="INPUT",
        type=Path,
        required=True,
        help="parse INPUT and print its AST",
    )
    arguments = argument_parser.parse_args(argv)

    try:
        output = compile_ast(arguments.ast)
    except CompilationError as error:
        print(error.formatted(), file=sys.stderr)
        return 1

    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
