# Epistula Minervae

**Epistula Minervae** is a small, statically typed educational language with Latin keywords, Roman integer literals, textual operator aliases and sentence-like punctuation. This repository contains stage 1 of the *Languages and Compilers Design* course project: the language design, a hand-written byte-state-machine lexer, a hand-written recursive-descent parser, an AST hierarchy and golden tests.

No third-party Python packages, lexer generators or parser generators are used.

## Requirements

- Python 3.10 or newer;
- a UTF-8 terminal for the `⬅` assignment operator.

There is no build step. From the repository root, run:

```bash
python3 compiler.py --ast path/to/program.em
```

The AST is written to standard output. On a lexical or syntax error, standard output stays empty, the process returns a non-zero code, and standard error contains one line:

```text
compilation error: line L:C: message
```

## Language overview

The complete specification is in [`docs/language-specification.md`](docs/language-specification.md), and the exact grammar is in [`grammar.ebnf`](grammar.ebnf).

### Types and declarations

The integer types are `32bitInt` and `64bitInt`; `sententia` is the boolean type. `variabilis` creates a mutable variable. `immutabilis` and `inaeternum` create an immutable variable.

```text
variabilis 32bitInt Count <- 100.
immutabilis 64bitInt Limen <- MMM.
inaeternum sententia Enabled <- Veritas.
```

Integers may use decimal or canonical Roman notation. `Veritas`, `Falsus` and `nihil` are literals. Constant integer initializers and assignments are checked against the declared 32-bit or 64-bit range.

### Assignment and arithmetic

`<-`, `⬅` and `aequalis` are equivalent assignment operators.

```text
Count <- XI.
Count ⬅ Count + I.
Count aequalis (Count adde V) * II.
```

Arithmetic operators have symbolic and textual spellings:

| Operation | Symbol | Word form |
|---|---|---|
| addition | `+` | `adde` |
| subtraction | `-` | `subtrahe` |
| multiplication | `*` | `multiplica` |
| division | `/` | `divide` |
| remainder | `%` | `diviso integra` |
| exponentiation | `^` | `exponens` |

The two forms can be mixed and have the same precedence. All binary arithmetic operators, including exponentiation, are left-associative: `2 ^ 3 ^ 2` is `(2 ^ 3) ^ 2`. Integer division truncates towards zero, and remainder uses the same quotient.

### Comparisons

`o-o`/`idem` mean equality. `oxo`/`non idem` mean inequality.

```text
variabilis sententia Equal <- X o-o 10.
variabilis sententia Different <- X non idem XI.
```

### Conditions

Blocks use `<<` and `>>` and must contain at least one statement. `aliter provisum` and `aliter` are optional.

```text
provisum Count idem X <<
    Scribe Count;
>>,
aliter provisum Count idem XV <<
    Scribe 15;
>>,
aliter <<
    Scribe nihil;
>>.
```

Top-level statements end with `.`, statements nested in a block end with `;`, and `,` connects branches belonging to the same conditional.

### Input and output

`Legere` may be a statement, may store into a variable, or may appear as an expression. A direct text argument to `Scribe` has a mandatory quotation marker `-`.

```text
Legere.
Legere in Count.
Count <- Legere.
Scribe - "Valor: ", Count, - "/linea".
```

The sequence `/linea` is a newline inside text, and `//` represents a slash. The special text `"nihil"` is an empty string.

### Comments

```text
N.B. A line comment.
(N.B. A comment that may
continue on another line.)
```

## AST format

Every AST node includes the source position of its originating token. Dumps include declaration mutability and type, source operator spelling, literal notation and value, branch flags and child counts. Indentation represents tree depth. The format is stable and is covered by golden tests.

Example:

```text
Program @1:1 statements=1
  VarDecl @1:1 name="Count" type="32bitInt" mutable=true keyword="variabilis"
    IntegerLiteral @1:30 text="XXXV" value=35 notation="roman"
```

## Running the tests

Run all positive and negative golden tests:

```bash
python3 tests/run_tests.py
```

The suite contains 28 valid programs and 42 invalid/range-error programs (70 golden tests), plus 32 independent regression tests. Every valid `.em` file has a matching `.ast` dump. Every invalid `.em` file has a matching `.err` file. The runner checks minimum test counts, applies per-process timeouts, reports failed cases and returns a non-zero status if anything differs. The independent tests include all 3999 canonical Roman literals, exact integer boundaries, scope isolation, arithmetic precedence, byte positions, invalid UTF-8, CR/LF/CRLF, deep inputs and CLI output/error contracts.

`tests/generate_expected.py` is a maintainer-only helper for deliberately refreshing golden files after reviewing an intentional AST or diagnostic-format change.

Do not regenerate expected files merely to make a failing test pass. The independent assertions in `tests/test_regressions.py` are handwritten oracles, not compiler-generated expectations.

## Stage-1 boundaries

This front end parses programs and dumps an AST; it does not execute `Scribe` or `Legere`. Per the assignment, full name resolution, mutability enforcement, type checking (including the boolean type of conditions) and code generation belong to the next stage. The required constant integer overflow check is implemented now, including intermediate results and assignment targets with known types. Block-local declarations do not leak to sibling or enclosing blocks.

Input and output use UTF-8. Locations are 1-based byte columns, not Unicode character or visual tab columns. Newlines may be LF, CRLF or CR. A final top-level dot may be followed directly by EOF. Decimal literal magnitude is limited to `2^63` (the extra magnitude is needed for signed INT64_MIN). Oversized source literals and excessive recursion produce a single formatted error, not a Python traceback.

## Repository structure

```text
compiler.py                       command-line entry point
epistula/lexer.py                 byte-oriented state-machine lexer
epistula/parser.py                recursive-descent parser
epistula/ast_nodes.py             AST class hierarchy and dump format
epistula/checks.py                constant integer overflow checks
grammar.ebnf                      complete EBNF grammar
docs/language-specification.md    language rules and examples
tests/valid/                      valid sources and expected ASTs
tests/invalid/                    invalid sources and expected errors
tests/run_tests.py                test runner
ai_usage.txt                      AI-use disclosure template
```

## Submission workflow

Development is tracked on the `stage1` branch. Before submission:

1. Complete every placeholder in `ai_usage.txt`.
2. Push `main` and `stage1` to a new GitHub or GitLab repository.
3. Add `vovaskochko` as a collaborator and wait until the invitation is accepted.
4. Open a pull request from `stage1` into `main`, request review from `vovaskochko`, and do not merge it.
5. Submit the repository URL, pull-request URL and the completed `ai_usage.txt` in Moodle.

The archive is **not yet administratively ready to submit**: `ai_usage.txt` intentionally remains a template at the author's request. A missing or incomplete disclosure gives an automatic grade of 0. Repository creation, collaborator invitation/acceptance, PR review request and Moodle submission must be performed by the student; this project has not been pushed. The first-day invitation requirement cannot be retroactively fulfilled by local code changes.

Existing commits were made with the explicitly generic local identity `Student <student@example.com>`. Configure your actual name/email before making your own commits. Do not misrepresent generated work as independent authorship.

The correction audit and requirement-to-test mapping are in [`docs/audit.md`](docs/audit.md).
