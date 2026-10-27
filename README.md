# Epistula Minervae

Epistula Minervae is a small, statically typed language with Latin keywords, Roman integer literals, textual operator aliases, and sentence-like punctuation. Its hand-written byte-state-machine lexer and recursive-descent parser produce an AST. A separate semantic pass checks names and types before `llvmlite.ir` builders generate LLVM IR. The compiler keeps the Stage 1 `--ast` command.

## Build and run

On Linux or WSL, install Python 3.12, `llc`, and `clang`, then create a local environment with `llvmlite`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install llvmlite
.venv/bin/python compiler.py --ast program.em
.venv/bin/python compiler.py program.em program.ll
llc -relocation-model=pic -filetype=obj program.ll -o program.o
clang program.o -o program
./program
.venv/bin/python tests/run_tests.py
```

The code-generation command writes only the module printed by the builder to `program.ll`. `llc` turns it into an object file; `clang` links `printf` and `scanf` from the C library. A lexical, syntax, or semantic error gives a nonzero exit code, no output file, and exactly one standard-error line: `compilation error: line L:C: message`. Input and output use UTF-8. Source columns count bytes from 1.

## Existing syntax and types

The original `32bitInt` and `64bitInt` are signed integers. `integer` and `duplex` are their 32-bit and 64-bit aliases. `ludicium` is boolean, with `Veritas` and `Falsus`. `sententia` is the text type. For Stage 1 compatibility, a declaration spelled `sententia` with a clearly boolean initializer still has the old boolean meaning; in new parameter and result declarations `sententia` means text. `fractio` is not part of this stage.

```text
variabilis Count <- XV.
immutabilis integer Limit <- 100.
variabilis ludicium Enabled <- Veritas.
variabilis sententia Greeting <- "Salve".
```

An ordinary variable or field can omit its type when its initializer has a definite type. A field without an initializer needs an explicit type. `nihil` alone cannot infer a declared type. `variabilis` makes a mutable binding; `immutabilis` and `inaeternum` are immutable synonyms. The old explicit declarations remain valid. Names are declared before use, at most once per scope; an inner block may shadow an outer binding.

Decimal or canonical Roman integer literals are accepted. Arithmetic uses `+`/`adde`, `-`/`subtrahe`, `*`/`multiplica`, `/`/`divide`, `%`/`diviso integra`, and `^`/`exponens`. Operators of one precedence level associate left, including exponentiation. Integer division truncates toward zero; a statically known zero divisor is a compilation error. Equality is `o-o`/`idem` and inequality is `oxo`/`non idem`. `provisum`, `aliter provisum`, and `aliter` form nonempty conditional blocks; the condition must be `ludicium`. Assignment uses `<-`, `⬅`, or `aequalis`.

The two integer widths are compatible in either direction. Widening sign-extends. A compile-time integer expression outside its target width is a compilation error, including an overflowing intermediate constant result. A nonconstant `duplex` narrowed to `integer` keeps its low 32 bits, interpreted as a signed integer. This rule is exercised by `tests/e2e/narrowing_runtime.em`.

## Functions

`nuntia edictum` declares a function with typed parameters and a result type. `cape nihil` means no parameters; `remitteque nihil` means no result. `reditus expression!` returns a value; a no-result function may use `reditus nihil!`. A value-returning function must return on every path. A function body sees its parameters and locals, global values declared earlier, and all function signatures. Functions may call themselves or a function declared later. Their names are prefixed in LLVM IR so `main` and `printf` are available as source names without colliding with runtime symbols.

```text
nuntia edictum Add quo cape integer A, integer B remitteque integer <<
    reditus A + B!
>>.
Scribe Add(20, 22), "/linea".
```

The alternative `integer Double <- nuntia edictum quo cape integer X << ... >>.` declares the same kind of function: `Double` is its name and `integer` its result type. Calls are expressions and accept either `Add(20, 22)` or `Add quo cape 20, 22`; empty calls are `F(nihil)` or `F quo cape nihil`. Calls can nest. When a call is a whole statement, it ends with `.` at top level or `;` in a block; calls inside another expression have no separate terminator. Argument count and each argument type are checked before IR generation.

## Structures and member functions

`nuntia structuram` declares ordered fields. A field declared `immutabilis` cannot be assigned after construction. A field initializer is evaluated for each constructed object when that field is omitted; it may read earlier fields in declaration order. Construction accepts positional and named values together. A named value fills its field; each positional value fills the first unfilled field. Missing required fields, duplicates, unknown fields, and extra values are errors.

```text
nuntia structuram Point <<
    variabilis integer x;
    immutabilis integer y <- x + 1;
>>.
variabilis p <- Point cape 3.
variabilis q <- Point cape y <- 5, 2.
Scribe p, "/linea".
```

Fields and methods use `.` or `>`; the separators may mix, as in `p.center > x`. Assignment through a chain requires the starting object and every field on the path to be mutable. `immutabilis Point p <- ...` makes that object and nested paths immutable. `nuntia structuram immutabilem Name quo << ... >>.` makes every object of the type immutable.

A member function is declared inside a structure with `nuntia edictum` and is called on an object: `p.Distance quo cape nihil` or `p > Distance(nihil)`. Its fields and other members are visible by name. Name lookup inside a member checks parameters and locals, then fields, then globals. `hoc` names the current object inside a member; `hoc <- Point cape ...` replaces it. A member is mutating when it writes the current object or a field, or calls another member that does so. Calling a mutating member on an immutable object is an error.

## Input and output

`Legere` reads one integer from standard input. It is an expression, a statement, or `Legere in Name`. `Scribe` prints its arguments in order without inserting separators or a newline. It accepts integers, booleans (`true`/`false`), text, `nihil`, and structures. The first direct string literal in `Scribe` uses the Stage 1 quotation marker `-`; later string arguments need no marker. `/linea` inside text produces a newline. An object prints as `Type{field=value, other=value}` in field declaration order, recursively for nested objects.

```text
variabilis A <- Legere.
Scribe - "Value: ", A, "/linea".
```

The special string literal `"nihil"` is empty text. For legacy Stage 1 integer values initialized with bare `nihil`, the stored numeric value is zero; direct `Scribe nihil` prints `nihil`. A text value initialized with bare `nihil` prints `nihil` and compares equal to bare `nihil`. Equality between values of different nonnumeric types is false, inequality true. These compatibility rules keep the old parsing examples executable under the new integer input requirement.

## Grammar, tests, and disclosure

[`grammar.ebnf`](grammar.ebnf) defines the Stage 1 and Stage 2 syntax and lexical rules. [`docs/language-specification.md`](docs/language-specification.md) contains the full language specification. The test runner checks Stage 1 AST golden files, Stage 2 AST fields, lexical and syntax errors, semantic errors, independent regression assertions, and programs compiled through `.ll` to exact expected output. `tests/e2e/input_sum.in` supplies standard input without echoing it. In particular, positive and negative cases cover call count and type, return type, field existence, constructor completeness, constant chains, and mutating member calls.

`ai_usage_2.txt` must be completed by the author before submission with every tool, exact prompts or public full-chat links, accepted and changed output, reasons, and the author's own understanding. It is kept out of local commits at the author's request; it must be included in the final Stage 2 pull request and Moodle submission to receive a grade.
