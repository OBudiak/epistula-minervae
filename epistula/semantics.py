"""Name resolution and type checking before LLVM code generation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast_nodes import (
    AssignmentNode, BinaryExprNode, BooleanLiteralNode, CallNode,
    ComparisonExprNode, ConstructorNode, ExprNode, ExprStmtNode,
    FieldDeclNode, FunctionDeclNode, IdentifierNode, IfNode,
    IntegerLiteralNode, MemberAccessNode, NilLiteralNode, PrintNode,
    ProgramNode, ReadExprNode, ReadStmtNode, ReturnNode, StmtNode,
    StringLiteralNode, StructDeclNode, UnaryExprNode, VarDeclNode,
)
from .checks import OverflowChecker
from .errors import CompilationError


I32 = "32bitInt"
I64 = "64bitInt"
BOOL = "ludicium"
TEXT = "sententia"
INPUT = "lectum"
NIL = "nihil"
NUMERIC = {I32, I64}


@dataclass
class VariableSymbol:
    name: str
    type_name: str
    mutable: bool
    global_variable: bool = False


@dataclass
class FieldSymbol:
    name: str
    type_name: str
    mutable: bool
    index: int
    initializer: ExprNode | None


@dataclass
class FunctionSymbol:
    name: str
    parameter_types: list[str]
    result_type: str
    node: FunctionDeclNode
    owner: str | None = None
    mutating: bool = False
    callees_on_self: set[str] = field(default_factory=set)


@dataclass
class StructSymbol:
    name: str
    immutable: bool
    node: StructDeclNode
    fields: list[FieldSymbol] = field(default_factory=list)
    methods: dict[str, FunctionSymbol] = field(default_factory=dict)
    constructor: FunctionSymbol | None = None

    def field_named(self, name: str) -> FieldSymbol | None:
        return next((item for item in self.fields if item.name == name), None)


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.structs: dict[str, StructSymbol] = {}
        self.functions: dict[str, FunctionSymbol] = {}
        self.globals: dict[str, VariableSymbol] = {}
        self.scopes: list[dict[str, VariableSymbol]] = []
        self.expression_types: dict[int, str] = {}
        self.call_symbols: dict[int, FunctionSymbol] = {}
        self.constructor_fields: dict[int, dict[str, ExprNode | None]] = {}
        self.constructor_arguments: dict[int, list[ExprNode]] = {}
        self.variable_types: dict[int, str] = {}
        self.struct_names: dict[int, str] = {}
        self.assignment_target_types: dict[int, str] = {}
        self.read_target_types: dict[int, str] = {}
        self.member_calls: list[tuple[CallNode, FunctionSymbol, bool]] = []
        self.current_function: FunctionSymbol | None = None
        self.current_struct: StructSymbol | None = None
        self.initialized_fields: set[str] | None = None
        self.writing_target = False
        self.fields_ready: set[str] = set()
        self.pending_constructors: dict[int, tuple] = {}

    def error(self, node: object, message: str) -> None:
        raise CompilationError(node.line, node.column, message)

    def canonical(self, spelling: str, node: object, allow_void: bool = False) -> str:
        aliases = {"integer": I32, "duplex": I64}
        result = aliases.get(spelling, spelling)
        if self.current_struct and result not in (I32, I64, BOOL, TEXT, NIL):
            prefix = self.current_struct.name
            while prefix:
                if f"{prefix}.{result}" in self.structs:
                    result = f"{prefix}.{result}"
                    break
                prefix = prefix.rpartition(".")[0]
        if result in (I32, I64, BOOL, TEXT) or result in self.structs:
            return result
        if allow_void and result == NIL:
            return NIL
        self.error(node, f"Typus '{spelling}' ignotus est.")

    def analyze(self, program: ProgramNode) -> SemanticAnalyzer:
        for statement in program.statements:
            if isinstance(statement, StructDeclNode):
                self._register_struct(statement)
        for statement in program.statements:
            if isinstance(statement, FunctionDeclNode):
                self._register_function(statement)
        for struct in self.structs.values():
            self.current_struct = struct
            for method in struct.node.methods:
                symbol = self._register_function(method, struct.name)
                if method.constructor:
                    if struct.constructor is not None:
                        self.error(method, "Constructor iteratus est.")
                    struct.constructor = symbol
                else:
                    if symbol.name in struct.methods:
                        self.error(method, "Edictum iteratum est.")
                    struct.methods[symbol.name] = symbol
        self.current_struct = None
        self.scopes = [self.globals]
        for statement in program.statements:
            if isinstance(statement, StructDeclNode):
                self._analyze_struct(statement)
            elif isinstance(statement, FunctionDeclNode):
                self._analyze_function(self.functions[statement.name])
            else:
                self._statement(statement)
        self._check_structure_cycles()
        saved = self.scopes, self.current_struct, self.current_function, self.initialized_fields
        for node, scopes, owner, function, initialized in self.pending_constructors.values():
            self.scopes, self.current_struct, self.current_function = scopes, owner, function
            self.initialized_fields = initialized
            self._constructor(node)
        self.scopes, self.current_struct, self.current_function, self.initialized_fields = saved
        self._propagate_mutation()
        for call, symbol, receiver_mutable in self.member_calls:
            if symbol.mutating and not receiver_mutable:
                self.error(call, "Edictum mutans in structura immutabili vocari non potest.")
        return self

    def _register_struct(self, node: StructDeclNode, parent: str = "") -> None:
        name = f"{parent}.{node.name}" if parent else node.name
        if name in self.structs:
            self.error(node, "Structura iterata est.")
        self.struct_names[id(node)] = name
        self.structs[name] = StructSymbol(name, node.immutable, node)
        for nested in node.nested:
            self._register_struct(nested, name)

    def _check_structure_cycles(self) -> None:
        visiting, visited = set(), set()
        def visit(name: str) -> None:
            if name in visiting:
                self.error(self.structs[name].node, "Structura se per valorem continere non potest.")
            if name in visited:
                return
            visiting.add(name)
            for item in self.structs[name].fields:
                if item.type_name in self.structs:
                    visit(item.type_name)
            visiting.remove(name)
            visited.add(name)
        for name in self.structs:
            visit(name)

    def _register_function(self, node: FunctionDeclNode,
                           owner: str | None = None) -> FunctionSymbol:
        if owner and node.name == owner.rpartition(".")[2] and not node.constructor:
            self.error(node, "Constructor remitteque habere non potest.")
        params = [self.canonical(p.type_name, p) for p in node.parameters]
        result = self.canonical(node.result_type, node, allow_void=True)
        symbol = FunctionSymbol(node.name, params, result, node, owner)
        if owner is None:
            if node.name in self.functions or node.name in self.structs:
                self.error(node, "Edictum iteratum est.")
            self.functions[node.name] = symbol
        return symbol

    def _analyze_struct(self, node: StructDeclNode) -> None:
        struct = self.structs[self.struct_names[id(node)]]
        for nested in node.nested:
            self._analyze_struct(nested)
        previous_struct = self.current_struct
        self.current_struct = struct
        try:
            for field_node in node.fields:
                if field_node.name == "hoc":
                    self.error(field_node, "Nomen 'hoc' in structura reservatum est.")
                if struct.field_named(field_node.name) or field_node.name in struct.methods:
                    self.error(field_node, "Campus iteratus est.")
                expected = self.canonical(field_node.type_name, field_node) if field_node.type_name else None
                inferred = (self._expression(field_node.initializer, expected)
                            if field_node.initializer is not None else None)
                if field_node.type_name is None:
                    if inferred in (None, NIL):
                        self.error(field_node, "Typus campi exspectabatur.")
                    type_name = inferred
                else:
                    type_name = self.canonical(field_node.type_name, field_node)
                if inferred is not None:
                    self._compatible(inferred, type_name, field_node.initializer)
                    self._constant_range(field_node.initializer, type_name)
                struct.fields.append(FieldSymbol(
                    field_node.name, type_name, field_node.mutable,
                    len(struct.fields), field_node.initializer))
            self.fields_ready.add(struct.name)
            for method in node.methods:
                symbol = struct.constructor if method.constructor else struct.methods[method.name]
                self._analyze_function(symbol, struct)
        finally:
            self.current_struct = previous_struct

    def _analyze_function(self, symbol: FunctionSymbol,
                          struct: StructSymbol | None = None) -> None:
        previous_function, previous_struct = self.current_function, self.current_struct
        previous_initialized = self.initialized_fields
        self.current_function, self.current_struct = symbol, struct
        self.initialized_fields = ({item.name for item in struct.fields if item.initializer is not None}
                                   if symbol.node.constructor else None)
        self.scopes.append({})
        try:
            for parameter, type_name in zip(symbol.node.parameters,
                                            symbol.parameter_types):
                self._declare(parameter.name, type_name, True, parameter)
            returns = self._statements(symbol.node.body, new_scope=False)
            if symbol.result_type != NIL and not returns:
                self.error(symbol.node, "Valor reditus deest.")
            if symbol.node.constructor:
                self._check_initialized(symbol.node)
        finally:
            self.scopes.pop()
            self.current_function, self.current_struct = previous_function, previous_struct
            self.initialized_fields = previous_initialized

    def _check_initialized(self, node: object) -> None:
        missing = [item.name for item in self.current_struct.fields
                   if item.name not in self.initialized_fields]
        if missing:
            self.error(node, f"Valor campi '{missing[0]}' in constructore deest.")

    def _statements(self, statements: list[StmtNode], new_scope: bool = True) -> bool:
        if new_scope:
            self.scopes.append({})
        try:
            guaranteed_return = False
            for statement in statements:
                returns = self._statement(statement)
                guaranteed_return = guaranteed_return or returns
            return guaranteed_return
        finally:
            if new_scope:
                self.scopes.pop()

    def _statement(self, node: StmtNode) -> bool:
        if isinstance(node, VarDeclNode):
            expected = self.canonical(node.type_name, node) if node.type_name else None
            inferred = self._expression(node.initializer, expected)
            if node.type_name is None:
                if inferred == NIL:
                    self.error(node, "Typus variabilis exspectabatur.")
                type_name = inferred
            else:
                type_name = (BOOL if node.keyword and node.type_name == TEXT and inferred == BOOL
                             else self.canonical(node.type_name, node))
            self._compatible(inferred, type_name, node.initializer)
            self._constant_range(node.initializer, type_name)
            self._declare(node.name, type_name, node.mutable, node)
            self.variable_types[id(node)] = type_name
            return False
        if isinstance(node, AssignmentNode):
            target = node.target or IdentifierNode(node.line, node.column, node.name)
            self.writing_target = True
            try:
                target_type = self._expression(target)
            finally:
                self.writing_target = False
            self.assignment_target_types[id(node)] = target_type
            initializing = self._initializing_field(target)
            if initializing is not None and not initializing.mutable and initializing.name in self.initialized_fields:
                self.error(node, "Campus immutabilis semel tantum initiari potest.")
            if initializing is None and not self._mutable_chain(target):
                self.error(node, "Valor immutabilis mutari non potest.")
            value_type = self._expression(node.value, target_type)
            self._compatible(value_type, target_type, node.value)
            self._constant_range(node.value, target_type)
            if initializing is not None:
                self.initialized_fields.add(initializing.name)
            if self.current_function and self.current_function.owner and self._on_self(target):
                self.current_function.mutating = True
            return False
        if isinstance(node, PrintNode):
            for argument in node.arguments:
                self._expression(argument.value)
            return False
        if isinstance(node, ReadStmtNode):
            if node.target is not None:
                target = IdentifierNode(node.line, node.column, node.target)
                target_type = self._expression(target)
                self.read_target_types[id(node)] = target_type
                if target_type not in NUMERIC | {TEXT, INPUT} or not self._mutable_chain(target):
                    self.error(node, "Legere requirit variabilem numericam aut textum.")
            return False
        if isinstance(node, ExprStmtNode):
            self._expression(node.expression)
            return False
        if isinstance(node, ReturnNode):
            if self.current_function is None:
                self.error(node, "Reditus extra edictum est.")
            actual = self._expression(node.value, self.current_function.result_type)
            self._compatible(actual, self.current_function.result_type, node.value)
            if self.initialized_fields is not None:
                self._check_initialized(node)
            self._constant_range(node.value, self.current_function.result_type)
            return True
        if isinstance(node, IfNode):
            if self._expression(node.condition) != BOOL:
                self.error(node.condition, "Condicio ludicium esse debet.")
            before = self.initialized_fields.copy() if self.initialized_fields is not None else None
            branches_return = [self._statements(node.then_body)]
            initialized = [self.initialized_fields.copy()] if before is not None else []
            for branch in node.else_if_branches:
                if before is not None:
                    self.initialized_fields = before.copy()
                if self._expression(branch.condition) != BOOL:
                    self.error(branch.condition, "Condicio ludicium esse debet.")
                branches_return.append(self._statements(branch.body))
                if before is not None:
                    initialized.append(self.initialized_fields.copy())
            if node.else_body is not None:
                if before is not None:
                    self.initialized_fields = before.copy()
                branches_return.append(self._statements(node.else_body))
                if before is not None:
                    initialized.append(self.initialized_fields.copy())
            elif before is not None:
                initialized.append(before)
            if before is not None:
                self.initialized_fields = set.intersection(*initialized)
            return node.else_body is not None and all(branches_return)
        self.error(node, "Sententia ignota est.")

    def _declare(self, name: str, type_name: str, mutable: bool,
                 node: object) -> VariableSymbol:
        if self.current_struct and name == "hoc":
            self.error(node, "Nomen 'hoc' in edicto membri reservatum est.")
        scope = self.scopes[-1]
        if name in scope or (len(self.scopes) == 1 and
                             (name in self.functions or name in self.structs)):
            self.error(node, "Nomen iteratum est.")
        symbol = VariableSymbol(name, type_name, mutable, len(self.scopes) == 1)
        scope[name] = symbol
        return symbol

    def _variable(self, node: IdentifierNode) -> VariableSymbol | FieldSymbol:
        for scope in reversed(self.scopes[1:]):
            if node.name in scope:
                return scope[node.name]
        if self.current_struct and node.name == "hoc":
            return VariableSymbol("hoc", self.current_struct.name,
                                  not self.current_struct.immutable)
        if self.current_struct:
            field_symbol = self.current_struct.field_named(node.name)
            if field_symbol:
                return field_symbol
        if node.name in self.globals:
            return self.globals[node.name]
        self.error(node, f"Nomen '{node.name}' ignotum est.")

    def _initializing_field(self, node: ExprNode) -> FieldSymbol | None:
        if self.initialized_fields is None:
            return None
        if isinstance(node, IdentifierNode):
            symbol = self._variable(node)
            return symbol if isinstance(symbol, FieldSymbol) else None
        if (isinstance(node, MemberAccessNode) and isinstance(node.object, IdentifierNode)
                and node.object.name == "hoc"):
            return self.current_struct.field_named(node.name)
        return None

    def _expression(self, node: ExprNode | None, expected: str | None = None) -> str:
        if node is None:
            raise ValueError("missing expression")
        if isinstance(node, IntegerLiteralNode):
            type_name = I32 if node.value <= 2**31 - 1 else I64
        elif isinstance(node, BooleanLiteralNode):
            type_name = BOOL
        elif isinstance(node, NilLiteralNode):
            type_name = NIL
        elif isinstance(node, StringLiteralNode):
            type_name = TEXT
        elif isinstance(node, ReadExprNode):
            type_name = expected if expected in NUMERIC | {TEXT} else INPUT
        elif isinstance(node, IdentifierNode):
            symbol = self._variable(node)
            if (isinstance(symbol, FieldSymbol) and self.initialized_fields is not None
                    and not self.writing_target and symbol.name not in self.initialized_fields):
                self.error(node, f"Campus '{symbol.name}' nondum initiatus est.")
            type_name = symbol.type_name
        elif isinstance(node, MemberAccessNode):
            base = self._expression(node.object)
            struct = self.structs.get(base)
            if struct is None:
                self.error(node, "Accessus campi structuram requirit.")
            field_symbol = struct.field_named(node.name)
            if field_symbol is None:
                self.error(node, f"Campus '{node.name}' ignotus est.")
            type_name = field_symbol.type_name
            if (self.initialized_fields is not None and not self.writing_target
                    and isinstance(node.object, IdentifierNode) and node.object.name == "hoc"
                    and field_symbol.name not in self.initialized_fields):
                self.error(node, f"Campus '{field_symbol.name}' nondum initiatus est.")
        elif isinstance(node, UnaryExprNode):
            type_name = self._expression(node.operand)
            if type_name not in NUMERIC | {INPUT}:
                self.error(node, "Operatio numerum requirit.")
            if type_name == INPUT:
                type_name = I64
        elif isinstance(node, BinaryExprNode):
            left, right = self._expression(node.left), self._expression(node.right)
            if left not in NUMERIC | {INPUT} or right not in NUMERIC | {INPUT}:
                self.error(node, "Operatio numeros requirit.")
            if node.operator in ("/", "divide", "%", "diviso integra"):
                divisor = OverflowChecker()._constant_integer(node.right, right)
                if divisor == 0:
                    self.error(node.right, "Divisio per nihil vetita est.")
            type_name = I64 if I64 in (left, right) or INPUT in (left, right) else I32
        elif isinstance(node, ComparisonExprNode):
            self._expression(node.left)
            self._expression(node.right)
            type_name = BOOL
        elif isinstance(node, ConstructorNode):
            if not node.type_name:
                if expected not in self.structs:
                    self.error(node, "Typus structurae pro novum exspectabatur.")
                node.type_name = expected
            type_name = self._constructor(node)
        elif isinstance(node, CallNode):
            type_name = self._call(node)
        else:
            self.error(node, "Expressio ignota est.")
        self.expression_types[id(node)] = type_name
        return type_name

    def _constructor(self, node: ConstructorNode) -> str:
        node.type_name = self.canonical(node.type_name, node)
        struct = self.structs.get(node.type_name)
        if struct is None:
            self.error(node, f"Structura '{node.type_name}' ignota est.")
        if struct.constructor is not None:
            symbol = struct.constructor
            bound_params: dict[str, ExprNode] = {}
            names = [item.name for item in symbol.node.parameters]
            for argument in node.arguments:
                name = argument.name or next((name for name in names if name not in bound_params), None)
                if name not in names:
                    self.error(argument, "Argumentum constructoris ignotum aut nimium est.")
                if name in bound_params:
                    self.error(argument, "Argumentum constructoris iteratum est.")
                expected = symbol.parameter_types[names.index(name)]
                actual = self._expression(argument.value, expected)
                self._compatible(actual, expected, argument.value)
                self._constant_range(argument.value, expected)
                bound_params[name] = argument.value
            if len(bound_params) != len(names):
                self.error(node, "Numerus argumentorum constructoris invalidus est.")
            self.constructor_arguments[id(node)] = [bound_params[name] for name in names]
            return struct.name
        if struct.name not in self.fields_ready:
            initialized = self.initialized_fields.copy() if self.initialized_fields is not None else None
            self.pending_constructors[id(node)] = (
                node, [scope.copy() for scope in self.scopes], self.current_struct,
                self.current_function, initialized)
            return struct.name
        bound: dict[str, ExprNode | None] = {}
        for argument in node.arguments:
            if argument.name is None:
                field_symbol = next((f for f in struct.fields if f.name not in bound), None)
            else:
                field_symbol = struct.field_named(argument.name)
            if field_symbol is None:
                self.error(argument, "Campus constructoris ignotus aut nimius est.")
            if field_symbol.name in bound:
                self.error(argument, "Campus constructoris iteratus est.")
            actual = self._expression(argument.value, field_symbol.type_name)
            self._compatible(actual, field_symbol.type_name, argument.value)
            self._constant_range(argument.value, field_symbol.type_name)
            bound[field_symbol.name] = argument.value
        for field_symbol in struct.fields:
            if field_symbol.name not in bound:
                if field_symbol.initializer is None:
                    self.error(node, f"Valor campi '{field_symbol.name}' deest.")
                bound[field_symbol.name] = None
        self.constructor_fields[id(node)] = bound
        return struct.name

    def _call(self, node: CallNode) -> str:
        receiver_mutable = True
        receiver_on_self = False
        if isinstance(node.callee, MemberAccessNode):
            base_type = self._expression(node.callee.object)
            struct = self.structs.get(base_type)
            if struct is None or node.callee.name not in struct.methods:
                self.error(node.callee, "Edictum membri ignotum est.")
            symbol = struct.methods[node.callee.name]
            receiver_mutable = self._mutable_chain(node.callee.object)
            receiver_on_self = self._on_self(node.callee.object)
        elif isinstance(node.callee, IdentifierNode):
            name = node.callee.name
            shadowed = (any(name in scope for scope in self.scopes[1:])
                        or (self.current_struct is not None
                            and self.current_struct.field_named(name) is not None))
            if self.current_struct and not shadowed and name in self.current_struct.methods:
                symbol = self.current_struct.methods[name]
                receiver_mutable = not self.current_struct.immutable
                receiver_on_self = True
            elif name in self.functions and not shadowed and name not in self.globals:
                symbol = self.functions[name]
            else:
                self.error(node.callee, f"Edictum '{name}' ignotum est.")
        else:
            self.error(node.callee, "Edictum exspectabatur.")
        if self.initialized_fields is not None and receiver_on_self:
            self._check_initialized(node)
        if len(node.arguments) != len(symbol.parameter_types):
            self.error(node, "Numerus argumentorum invalidus est.")
        for argument, expected in zip(node.arguments, symbol.parameter_types):
            actual = self._expression(argument, expected)
            self._compatible(actual, expected, argument)
            self._constant_range(argument, expected)
        self.call_symbols[id(node)] = symbol
        if symbol.owner:
            self.member_calls.append((node, symbol, receiver_mutable))
            if self.current_function and self.current_function.owner and receiver_on_self:
                self.current_function.callees_on_self.add(
                    f"{symbol.owner}.{symbol.name}")
        return symbol.result_type

    def _compatible(self, actual: str, expected: str, node: object) -> None:
        if actual == expected or (actual in NUMERIC and expected in NUMERIC):
            return
        if (actual == INPUT and expected in NUMERIC | {TEXT, INPUT}
                or expected == INPUT and actual in NUMERIC | {TEXT}):
            return
        if actual == NIL:
            if isinstance(node, CallNode):
                self.error(node, "Edictum sine valore in expressione adhiberi non potest.")
            return
        self.error(node, f"Typus {expected} exspectabatur, {actual} inventus est.")

    def _constant_range(self, node: ExprNode, type_name: str) -> None:
        if type_name in NUMERIC:
            OverflowChecker()._constant_integer(node, type_name)

    def _mutable_chain(self, node: ExprNode) -> bool:
        if isinstance(node, IdentifierNode):
            symbol = self._variable(node)
            if isinstance(symbol, FieldSymbol):
                return symbol.mutable and not self.current_struct.immutable
            return symbol.mutable
        if isinstance(node, MemberAccessNode):
            base_type = self._expression(node.object)
            struct = self.structs[base_type]
            field_symbol = struct.field_named(node.name)
            return (self._mutable_chain(node.object) and not struct.immutable
                    and field_symbol is not None and field_symbol.mutable)
        if isinstance(node, ConstructorNode):
            return not self.structs[node.type_name].immutable
        return False

    def _on_self(self, node: ExprNode) -> bool:
        if self.current_struct is None:
            return False
        if isinstance(node, IdentifierNode):
            if node.name == "hoc":
                return True
            try:
                return isinstance(self._variable(node), FieldSymbol)
            except CompilationError:
                return False
        if isinstance(node, MemberAccessNode):
            return self._on_self(node.object)
        return False

    def _propagate_mutation(self) -> None:
        all_methods = {f"{owner}.{name}": symbol
                       for owner, struct in self.structs.items()
                       for name, symbol in struct.methods.items()}
        changed = True
        while changed:
            changed = False
            for symbol in all_methods.values():
                if not symbol.mutating and any(all_methods[name].mutating
                                               for name in symbol.callees_on_self):
                    symbol.mutating = True
                    changed = True
