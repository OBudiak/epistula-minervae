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
from epistula.optimizer import optimize


def compile_ast(path: Path, optimized: bool = False) -> str:
    try:
        source = path.read_bytes()
    except OSError as exc:
        raise CompilationError(1, 1, "Fasciculus legi non potest.") from exc
    tokens = Lexer(source).scan()
    parser = Parser(tokens)
    try:
        program = parser.parse_program()
        OverflowChecker().check(program)
        if optimized:
            semantics = SemanticAnalyzer().analyze(program)
            optimize(program, semantics)
        return program.dump()
    except RecursionError as exc:
        token = tokens[min(parser.index, len(tokens) - 1)]
        raise CompilationError(
            token.line, token.column, "Structura nimis profunda est."
        ) from exc


def compile_ir(path: Path, optimized: bool = False) -> str:
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
        if optimized:
            semantics = optimize(program, semantics)
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
    class CompilerArgumentParser(argparse.ArgumentParser):
        def error(self, message: str) -> None:
            raise CompilationError(1, 1, "Argumenta CLI invalida sunt.")

    argument_parser = CompilerArgumentParser(
        description="Epistula Minervae compiler"
    )
    argument_parser.add_argument(
        "--ast",
        metavar="INPUT",
        type=Path,
        help="parse INPUT and print its AST",
    )
    argument_parser.add_argument("--optimize", action="store_true",
                                 help="optimize the checked tree")
    argument_parser.add_argument("input", nargs="?", type=Path)
    argument_parser.add_argument("output", nargs="?", type=Path)
    try:
        arguments = argument_parser.parse_intermixed_args(argv)
        if arguments.ast is not None:
            if arguments.input is not None or arguments.output is not None:
                raise CompilationError(1, 1, "Argumenta CLI invalida sunt.")
            output = compile_ast(arguments.ast, arguments.optimize)
            sys.stdout.write(output)
        else:
            if arguments.input is None or arguments.output is None:
                raise CompilationError(1, 1, "Duo nomina fasciculorum exspectantur.")
            if arguments.input.resolve() == arguments.output.resolve():
                raise CompilationError(1, 1, "Fasciculus fontis et output diversi esse debent.")
            try:
                arguments.output.unlink(missing_ok=True)
            except OSError as exc:
                raise CompilationError(1, 1, "Fasciculus scribi non potest.") from exc
            output = compile_ir(arguments.input, arguments.optimize)
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
