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
clang -pthread program.o -o program
./program
.venv/bin/python tests/run_tests.py
```

The test runner shows the current file check and its progress. It runs
hundreds of checks, including compilation and native execution with and
without optimization, so completion time depends on the machine. A test that
exceeds its timeout is reported as a failure.

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


## Stage 3: loops, arrays and threads

Stage 3 adds the three features below. Their contextual keywords remain usable
as identifiers outside the new constructs. Stage 2 programs retain their
syntax and behavior.

### Loops and conditions

`nuntia cycliciter quo condition << ... >>` repeats while its boolean
condition is true. `nuntia finite first ad last quo index name << ... >>`
evaluates its integer bounds once, then visits the inclusive ascending range
with step one; a reversed range executes zero times. The index is a mutable
`duplex` scoped to the loop. Nested loops and local declarations are
supported. `Interrumpe!` leaves the innermost enclosing loop.

The Latin-letter operators `o/o`, `o\o`, `o/=o` and
`o\=o` mean greater, less, greater-or-equal and less-or-equal.
`||` means AND and `|v|` means OR; AND has higher precedence and both
short-circuit. Operands must be boolean. Existing equality operators remain.

Example 1:
```text
duplex Total <- 0.
nuntia finite 1 ad 3 quo index Row <<
    nuntia finite 1 ad 2 quo index Col <<
        duplex Value <- Row * Col;
        Total <- Total + Value;
    >>;
>>.
Scribe Total, "/linea".
```
Example 2:
```text
integer Number <- 0.
nuntia cycliciter quo Number o\o 10 <<
    Number <- Number + 1;
    provisum Number idem 3 <<
        Interrumpe!
    >>;
>>.
Scribe Number, "/linea".
```

This is a generated IR excerpt for the nested-loop example:

```llvm
  %".34" = icmp sge i64 %".33", %".5"
  br i1 %".34", label %"loop_end", label %"loop_step.1"
loop_step:
  %".29" = load i64, i64* %"Col"
  %".30" = add i64 %".29", 1
  store i64 %".30", i64* %"Col"
  br label %"loop_test.1"
loop_step.1:
  %".36" = load i64, i64* %"Row"
  %".37" = add i64 %".36", 1
  store i64 %".37", i64* %"Row"
  br label %"loop_test"
print_null_text:
  %".46" = getelementptr [3 x i8], [3 x i8]* @".em_str_2", i32 0, i32 0
```

The first branch selects the loop exit or increment block. The increment block
loads, increments and stores the index. Its final branch goes back to the test,
forming the LLVM loop back edge.

### Fixed-size arrays

An array type is `type[] longitudo (size)` or
`type[][] longitudo (rows, columns)`. Sizes are positive decimal or
canonical Roman integer literals and there are at most two dimensions. Elements
are indexed from 1, and reads and writes use `array[index]`. Every existing
built-in or structure type can be an element type.

An initializer is `[]` for zero initialization or a complete list of
exactly the declared size in each dimension. Zero initialization gives numeric
zero, false, null text, and recursively zero-initialized structure fields; it
does not run structure constructors or field defaults. An immutable binding
cannot be modified through its elements or passed to a mutable array parameter.
Arrays are passed to functions by reference, and dimensions are part of their
parameter type. A statically known out-of-range index is a compilation error;
a dynamic out-of-range index prints a runtime error and exits with status 1.

Example 1:
```text
integer[] longitudo (III) Numbers <- [1, 2, 3].
Numbers[2] <- 7.
Scribe Numbers[1], ",", Numbers[2], ",", Numbers[3], "/linea".
```
Example 2:
```text
nuntia edictum Change quo cape duplex[][] longitudo (II, III) Grid remitteque nihil <<
    Grid[2][3] <- 42;
>>.
duplex[][] longitudo (II, III) Matrix <- [].
Change(Matrix).
Scribe Matrix[2][3], "/linea".
```

The compiler generated the following excerpt for the second example:

```llvm
entry:
  store [2 x [3 x i64]] zeroinitializer, [2 x [3 x i64]]* @"em_global_Matrix"
  call void @"em_fn_Change"([2 x [3 x i64]]* @"em_global_Matrix")
  %".4" = sext i32 2 to i64
  %".5" = icmp sge i64 %".4", 1
  %".6" = icmp sle i64 %".4", 2
  %".7" = and i1 %".5", %".6"
  br i1 %".7", label %"input_ok", label %"input_error"
input_ok:
  %".13" = sub i64 %".4", 1
  %".14" = getelementptr [2 x [3 x i64]], [2 x [3 x i64]]* @"em_global_Matrix", i32 0, i64 %".13"
  %".15" = sext i32 3 to i64
  %".16" = icmp sge i64 %".15", 1
  %".17" = icmp sle i64 %".15", 3
  %".18" = and i1 %".16", %".17"
  br i1 %".18", label %"input_ok.1", label %"input_error.1"
```

The first store initializes the nested fixed-size LLVM array to zero. The call
passes its address, so the function modifies the original array. The
comparisons and branch check the one-based index before element addressing.

### Threads

Declare a worker with `nuntia in filo Name quo cape ... << ... >>.`, start
it with `filum Handle <- incipe Name(arguments).` and wait with
`exspecta Handle.`. A declaration can be launched multiple times; each
launch has its own handle. Join each handle at most once. A worker does not
return a language value. Numeric and boolean arguments are copies; arrays,
structures and text are references. Arrays and structures passed by reference
must be mutable locations. A text expression that is not a location is stored
in a temporary location before it is passed.

The generated program declares `pthread_create` and `pthread_join`
and stores arguments in a heap structure for each launch. Referenced local
arrays, structures and text slots are retained until process exit so a worker
can outlive its caller; text storage has the existing process-lifetime policy.
This conservative policy can use substantial memory for long-running programs.
The worker argument structure itself is freed by the worker wrapper.

Concurrent reads and writes to disjoint locations are supported. Concurrent
access to the same location when at least one access writes is unsupported:
there is no mutex, and a data race has no guaranteed result. Workers may print
concurrently but output order is unspecified. The process does not implicitly
join workers; if main exits first, those workers may not finish.

Example 1:
```text
nuntia in filo Worker quo cape duplex[] longitudo (II) Numbers, duplex Position, duplex Value <<
    Numbers[Position] <- Value;
>>.
duplex[] longitudo (II) Numbers <- [].
filum First <- incipe Worker(Numbers, 1, 40).
filum Second <- incipe Worker(Numbers, 2, 2).
exspecta First.
exspecta Second.
Scribe Numbers[1] + Numbers[2], "/linea".
```
Example 2:
```text
nuntia structuram Box <<
    mutabilis duplex value;
>>.
nuntia in filo Worker quo cape Box Item <<
    Item.value <- 9;
>>.
Box Item <- novum 1.
filum Task <- incipe Worker(Item).
exspecta Task.
Scribe Item.value, "/linea".
```

A generated excerpt for the first example is:

```llvm
  %".16" = getelementptr {[2 x i64]*, i64, i64}, {[2 x i64]*, i64, i64}* %".12", i32 0, i32 1
  store i64 %".15", i64* %".16"
  %".18" = sext i32 40 to i64
  %".19" = getelementptr {[2 x i64]*, i64, i64}, {[2 x i64]*, i64, i64}* %".12", i32 0, i32 2
  store i64 %".18", i64* %".19"
  %".21" = bitcast {[2 x i64]*, i64, i64}* %".12" to i8*
  %".22" = call i32 @"pthread_create"(i64* @"em_global_First", i8* null, i8* (i8*)* @"em_thread_Worker", i8* %".21")
  %".23" = icmp eq i32 %".22", 0
  br i1 %".23", label %"input_ok.1", label %"input_error.1"
input_error:
  %".8" = getelementptr [34 x i8], [34 x i8]* @".em_str_1", i32 0, i32 0
  %".9" = call i64 @"write"(i32 2, i8* %".8", i64 33)
  call void @"exit"(i32 1)
  unreachable
```

The first stores put copied integer arguments in the launch structure.
`pthread_create` receives the handle address, worker wrapper and argument
structure pointer. The following comparison checks creation status and
branches to an error path on failure.

### Checked-tree optimizer

`--optimize` is accepted anywhere in the compiler command line. It
transforms the semantically checked tree before LLVM generation;
`--optimize --ast input` prints the transformed tree. Unused declarations
and writes are eliminated to a fixed point while preserving evaluation when it
may have effects or fail. Uncalled functions are eliminated repeatedly.

Inlining is limited to nonrecursive, value-returning global functions called
exactly once, whose bodies contain only local declarations followed by a return
and contain no calls or free global variables. The call must be the complete
initializer, a plain-variable assignment value, or a return value. Array
parameters are not inlined. Other shapes, including returns within conditionals,
are left alone. Arguments, locals and the converted result receive fresh names
to preserve evaluation, scope and return type.

For `tests/optimizer/inline_rename.em`, before optimization the call is:
```llvm
entry:
  store i32 3, i32* @"em_global_Local"
  %".3" = load i32, i32* @"em_global_Local"
  %".4" = call i32 @"em_fn_Double"(i32 %".3")
  store i32 %".4", i32* @"em_global_Result"
  %".6" = load i32, i32* @"em_global_Result"
```
After optimization its body is in the caller:
```llvm
  store i32 3, i32* @"em_global_Local"
  %".3" = load i32, i32* @"em_global_Local"
  store i32 %".3", i32* @"em_global_stage3_inline_1"
  %".5" = load i32, i32* @"em_global_stage3_inline_1"
  %".6" = load i32, i32* @"em_global_stage3_inline_1"
  %".7" = add i32 %".5", %".6"
  store i32 %".7", i32* @"em_global_stage3_inline_2"
  %".9" = load i32, i32* @"em_global_stage3_inline_2"
  store i32 %".9", i32* @"em_global_stage3_inline_3"
  %".11" = load i32, i32* @"em_global_stage3_inline_3"
  store i32 %".11", i32* @"em_global_Result"
```

`tests/optimizer/` contains expected optimized ASTs and output for each
transformation. The test runner compares execution with and without
`--optimize`, including existing executable and runtime-error cases.

### Interactive matrix program

`programs/matrix.txt` multiplies a 20 by 20 matrix by a 20-element vector.
The user provides one `duplex` value for every matrix cell and then the
vector values individually. Four workers each compute five independent result
rows; main joins them before printing. A `Report` structure and its method
introduce the results, and a separate function prints each value. Arithmetic
uses fixed-width two's-complement results; choose inputs whose intermediate and
final values fit `duplex` when exact results are required. The two recorded
sessions use different matrix and vector values.

From the repository root, build a native executable and run both sessions:

```bash
.venv/bin/python compiler.py programs/matrix.txt /tmp/matrix.ll
llc -relocation-model=pic -filetype=obj /tmp/matrix.ll -o /tmp/matrix.o
clang -pthread /tmp/matrix.o -o /tmp/matrix
/tmp/matrix < programs/matrix_one.in
/tmp/matrix < programs/matrix_two.in
```

Exact output including prompts is in `programs/matrix_one.expected` and
`programs/matrix_two.expected`. The test runner checks both sessions with
and without optimization.
