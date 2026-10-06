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

The two forms can be mixed and have the same precedence. Exponentiation is right-associative; the other binary arithmetic operators are left-associative.

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

The suite contains 21 valid programs and 27 invalid programs. Every valid `.em` file has a matching `.ast` dump. Every invalid `.em` file has a matching `.err` file. The runner reports every failed case and returns a non-zero status if anything differs.

`tests/generate_expected.py` is a maintainer-only helper for deliberately refreshing golden files after reviewing an intentional AST or diagnostic-format change.

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
