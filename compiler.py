#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from epistula.checks import OverflowChecker
from epistula.codegen import CodeGenerator
from epistula.errors import CompilationError
from epistula.lexer import Lexer
from epistula.parser import Parser
from epistula.semantics import SemanticAnalyzer


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


def compile_ir(path: Path) -> str:
    try:
        source = path.read_bytes()
    except OSError as exc:
        raise CompilationError(1, 1, "Fasciculus legi non potest.") from exc
    tokens = Lexer(source).scan()
    parser = Parser(tokens)
    try:
        program = parser.parse_program()
        OverflowChecker().check(program)
        semantics = SemanticAnalyzer().analyze(program)
        return CodeGenerator(semantics).generate(program)
    except RecursionError as exc:
        token = tokens[min(parser.index, len(tokens) - 1)]
        raise CompilationError(token.line, token.column,
                               "Structura nimis profunda est.") from exc


def main(argv: list[str] | None = None) -> int:
    # Stable UTF-8 output even on Windows or an ASCII system locale.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    argument_parser = argparse.ArgumentParser(
        description="Epistula Minervae compiler"
    )
    argument_parser.add_argument(
        "--ast",
        metavar="INPUT",
        type=Path,
        help="parse INPUT and print its AST",
    )
    argument_parser.add_argument("input", nargs="?", type=Path)
    argument_parser.add_argument("output", nargs="?", type=Path)
    arguments = argument_parser.parse_args(argv)

    try:
        if arguments.ast is not None:
            if arguments.input is not None or arguments.output is not None:
                raise CompilationError(1, 1, "Argumenta CLI invalida sunt.")
            output = compile_ast(arguments.ast)
            sys.stdout.write(output)
        else:
            if arguments.input is None or arguments.output is None:
                raise CompilationError(1, 1, "Duo nomina fasciculorum exspectantur.")
            output = compile_ir(arguments.input)
            try:
                arguments.output.write_text(output, encoding="utf-8")
            except OSError as exc:
                raise CompilationError(1, 1, "Fasciculus scribi non potest.") from exc
    except CompilationError as error:
        print(error.formatted(), file=sys.stderr)
        return 1
    except Exception:
        print(CompilationError(1, 1, "Generatio codicis defecit.").formatted(),
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
