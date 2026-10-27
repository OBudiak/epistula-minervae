# Epistula Minervae

Epistula Minervae has Latin keywords, signed integers, booleans, text, functions,
and structures. A hand-written byte state machine and recursive-descent parser
build the AST. A separate semantic pass checks it before `llvmlite.ir` builders
generate LLVM IR.

## Build and run

Use Linux or WSL with Python 3.12, `llc`, and `clang`. Console input uses the
POSIX allocation modifier of `scanf`, available in the WSL/Linux C library.

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

Source is UTF-8; diagnostic columns count bytes from 1. A lexical, syntax, or
semantic error produces one stderr line `compilation error: line L:C: message`,
a nonzero status, and no output file. Stale output is removed before a build;
the source and output paths must differ. The only IR text written is
`str(module)`. Use the terminal interactively or `./program < input.txt`.

## Variables and types

An explicit type starts a declaration. `variabilis` means that the initializer
determines the type; it is followed by a name without an explicit type. This
applies globally and inside functions or methods. Ordinary bindings are mutable.
`immutabilis` or its synonym `inaeternum` creates a constant.

```text
integer Count <- 10.
duplex Wide <- 4294967297.
ludicium Ready <- Veritas.
sententia Greeting <- "Salve".
variabilis Next <- Count + 1.
immutabilis integer Limit <- 100.
immutabilis variabilis Label <- "fixed".
Count <- Next.
```

`integer` and `duplex` alias the signed `32bitInt` and `64bitInt`. `ludicium` is
boolean (`Veritas`, `Falsus`); `sententia` is text. `fractio` is not included.
Names are case sensitive: `Sententia` is an identifier. A name made entirely of
Roman digits is a number: `X` is 10 and needs no declaration.

Names are declared before use, once per scope. Inner blocks may shadow outer
names. Numeric widths are compatible in both directions: widening sign-extends;
runtime narrowing retains the low 32 bits. Constant integer initializers and
intermediate results outside their target width cause a compilation error.
`nihil` alone cannot infer a type. Numeric `nihil` stores zero; text `nihil`
stores an absent string and prints `nihil`. The literal `"nihil"` is empty text.

Stage 1 programs remain accepted. Historical declarations such as
`variabilis 32bitInt Count <- X.` are compatibility syntax. An old prefixed
`sententia` declaration with a boolean initializer retains its boolean meaning.
Stage 1 fixtures intentionally keep their historical spelling and stable ASTs.
Canonical Stage 2 examples use the forms above; `variabilis integer N` is rejected.

## Expressions and conditions

Arithmetic is `+`/`adde`, `-`/`subtrahe`, `*`/`multiplica`, `/`/`divide`,
`%`/`diviso integra`, and `^`/`exponens`. Equal-precedence operators, including
power, associate left. Division truncates toward zero. A known zero divisor is
a compilation error; invalid runtime division exits with a diagnostic. Equality
is `o-o`/`idem`, inequality `oxo`/`non idem`. Different nonnumeric types compare
unequal. A negative integer exponent produces zero.

```text
provisum Count idem X <<
    integer Local <- Count + 1;
    Scribe Local, "/linea";
>>,
aliter <<
    Scribe Count, "/linea";
>>.
```

Conditions must be boolean; conditional branches are nonempty. Top-level
statements end with `.`, statements in bodies with `;`, and returns with `!`.

## Functions

Parameters and results are explicitly typed. `cape nihil` means no parameters;
`remitteque nihil` means no result. A function with a result returns on every
path. Calls are expressions, and the semantic pass checks argument count and
types before IR generation. Bodies see parameters, locals, earlier globals, and
every function signature. Recursion and calls to later functions work.

```text
nuntia edictum Add quo cape integer A, integer B remitteque integer <<
    integer Result <- A + B;
    reditus Result!
>>.
integer Double <- nuntia edictum quo cape integer value <<
    reditus Add(value, value)!
>>.
Scribe Double(21), "/linea".
Add quo cape 3, 4.
```

Both `Add(3, 4)` and `Add quo cape 3, 4` work. Empty calls use `F(nihil)` or
`F quo cape nihil`. Use parentheses when a word-form call's trailing commas
would otherwise belong to its argument list. LLVM names have a prefix, so
source functions named `main` or `printf` do not collide with runtime functions.

## Structures and constructors

Each field has a required modifier, `mutabilis` or `immutabilis` (`inaeternum`
is the immutable alias). These are mutability modifiers, not data types. An
inferred field uses `mutabilis variabilis Name <- value;`. Variables inside
methods use ordinary declarations and need no field modifier.

A constructor is optional. Its name equals the structure name, its parameters
are typed, and it has no `remitteque` clause. Fields and methods end with `;`.
Every structure declaration, including a nested one, ends with `.`.

```text
nuntia structuram Nums <<
    immutabilis integer second;
    mutabilis integer first;
    immutabilis sententia label;
    nuntia edictum Nums quo cape integer A, integer B, sententia Text <<
        label <- Text;
        first <- A;
        second <- B;
    >>;
    nuntia edictum Later quo cape integer amount remitteque integer <<
        integer Result <- first + second + amount;
        reditus Result!
    >>;
>>.
variabilis nums <- novum Nums quo cape 3, 4, "lala".
Nums other <- novum Text <- "other", B <- 8, A <- 7.
Scribe nums > Later(2), "/linea", other, "/linea".
```

`Nums nums <- novum 3, 4, "lala".` gets its type from the declaration. The same
context works in assignments, typed arguments, and returns. An inferred
variable must specify the type after `novum`.

Constructor parameter order defines positional arguments independently of field
order; its body may initialize fields in any order. Named arguments name
parameters and may appear in any order. A positional argument fills the first
unfilled parameter. Duplicate, missing, unknown, excess, or wrongly typed
arguments are errors.

Without a user constructor, named arguments name fields; positional arguments
fill the first unfilled field in declaration order. Use names to avoid depending
on field order. Omitted fields need defaults. Defaults run for each object and
may read earlier fields. With a user constructor, defaults run first, and every
remaining field must be initialized on every path before it is read, before
calling a member on the new object, and before construction completes. An
immutable field is initialized once. No object has an uninitialized field.

```text
nuntia structuram Point <<
    mutabilis integer x;
    immutabilis integer y <- 4;
>>.
Point p <- novum y <- 5, x <- 3.
Scribe p, "/linea".
```

The older `Point cape ...` spelling remains accepted as an alias. Nested type
names are qualified outside their parent:

```text
nuntia structuram Outer <<
    nuntia structuram Inner <<
        mutabilis integer value;
    >>.
    mutabilis Inner center;
>>.
Outer.Inner inner <- novum 3.
Outer outer <- novum inner.
Scribe outer.center.value, "/linea".
```

An empty nested structure may use the short form
`nuntia structuram Outer <<Inner <<>>.>>.`. Recursive containment by value is
rejected because it has no finite LLVM layout.

## Members and immutability

Access uses `.` or `>`, and separators may mix. `p > center.x <- 5.` requires a
mutable starting object and every field in the chain to be mutable.
`immutabilis Point p <- ...` makes nested paths immutable.
`nuntia structuram immutabilem Name quo << ... >>.` makes instances immutable.
There is no separate reference data type.

Members look up names among parameters and locals, then fields, then globals.
`hoc` denotes the current object: `hoc.field <- value`; assignment to `hoc`
replaces it. A member that writes a field, replaces `hoc`, or calls a mutating
member is mutating and can be called only on a mutable receiver. Constructor
initialization can initialize immutable fields once.

## Console input and output

The required integer input uses an explicit integer context:

```text
integer Number <- Legere.
sententia Text <- Legere.
variabilis Value <- Legere.
Scribe Number, ",", Text, ",", Value, "/linea".
```

`integer`/`duplex` input reads one whitespace-delimited decimal or canonical Roman
integer, checks conversion and range, and consumes the next delimiter.
`sententia` input reads a line, preserving spaces, digits, and text; only its line
ending is removed. Thus text input `0010` stays `0010`.

`variabilis Value <- Legere` reads one line and classifies the entire line as a
signed decimal integer, canonical Roman integer, or text. `0010` and `X` both
print `10`; `Legere` prints `Legere`. Decimal values outside signed 64-bit range
fail. A line with spaces or other characters is text. Internally inferred input
has a fixed tagged representation (number or text), so its LLVM type never
changes at runtime. Numeric uses check the tag; text used as a number fails with
a runtime diagnostic. Typed text contexts preserve the original input. This
extends the assignment's integer built-in.

`Legere in Name` reads according to an existing mutable variable's type.
Standalone `Legere.` reads and discards one integer. End of input and invalid
numeric input exit with status 1 and a `runtime error:` line on stderr. Text
buffers live until process exit, including when returned from functions.

`Scribe` prints arguments in order without separators or automatic newlines.
Booleans print `true`/`false`; objects print as `Type{field=value, field2=value}`,
recursively in field order. The first argument needs `-` only when it is a direct
string literal. Later strings need no marker; an optional legacy marker remains
accepted. `/linea` in a source string produces a newline.

```text
Scribe p, "/linea".
Scribe - "Value: ", Number, "/linea".
```

## Grammar, verification and disclosure

[`grammar.ebnf`](grammar.ebnf) defines syntax and lexical constraints.
[`docs/language-specification.md`](docs/language-specification.md) is the full
specification; its DOCX counterpart contains the same rules. The runner checks
Stage 1 AST goldens, compiler diagnostics, compiled output, input files, and
runtime failures, reporting every failed case. Historical fixtures keep Stage 1
syntax; Stage 2 cases use the current syntax.

| Rule | Positive case | Negative case |
|---|---|---|
| Explicit declarations and inference | `e2e/custom_constructor` | `semantic_invalid/variabilis_explicit_type` |
| Field modifiers | `e2e/inferred_field` | `semantic_invalid/field_missing_modifier` |
| Calls and argument types | `e2e/nested_calls` | `semantic_invalid/too_few_arguments`, `too_many_arguments`, `wrong_argument_type` |
| Return types and forward calls | `e2e/forward_function` | `semantic_invalid/wrong_return_type` |
| Constructor order and completeness | `e2e/custom_constructor` | `semantic_invalid/constructor_missing_field`, `constructor_wrong_count`, `constructor_wrong_type` |
| Initialization on every path | `e2e/constructor_branch_initialization` | `semantic_invalid/constructor_conditional_field` |
| Lookup and shadowing | `e2e/name_lookup` | `semantic_invalid/field_shadows_function` |
| Mutable field paths | `e2e/field_chain` | `semantic_invalid/unknown_field`, `immutable_chain` |
| Mutating methods | `e2e/mutable_member` | `semantic_invalid/mutating_method_on_constant` |
| Nested type layout | `e2e/nested_structures` | `semantic_invalid/recursive_value_structure` |
| Width conversion and overflow | `e2e/narrowing_runtime` | `semantic_invalid/alias_overflow` |
| Typed and inferred input | `e2e/typed_text_input`, `input_variant_operations` | `runtime_invalid/invalid_integer_input`, `input_text_used_as_integer` |
| Input bounds and failures | `e2e/input_integer_bounds` | `runtime_invalid/input_i32_overflow`, `input_i64_overflow`, `input_numeric_eof` |
| Conditions and constants | `e2e/if_else`, `immutable_member` | `semantic_invalid/non_boolean_condition`, `immutable_assignment` |

Paths are relative to `tests/`. Executable cases have `.em`, `.expected`, and
optionally `.in`; runtime failures also have `.stderr` and `.exit`. Compiler
failures have `.err`.
