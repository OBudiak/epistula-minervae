"""LLVM IR generation through llvmlite.ir builders only."""

from __future__ import annotations

from llvmlite import binding, ir

from .ast_nodes import (
    AssignmentNode, BinaryExprNode, BooleanLiteralNode, CallNode,
    ComparisonExprNode, ConstructorNode, ExprNode, ExprStmtNode,
    FunctionDeclNode, IdentifierNode, IfNode, IntegerLiteralNode,
    MemberAccessNode, NilLiteralNode, PrintNode, ProgramNode,
    ReadExprNode, ReadStmtNode, ReturnNode, StmtNode, StringLiteralNode,
    StructDeclNode, UnaryExprNode, VarDeclNode,
)
from .semantics import BOOL, I32, I64, INPUT, NIL, NUMERIC, TEXT, FunctionSymbol, SemanticAnalyzer
from .input_runtime import InputRuntime


class CodeGenerator:
    def __init__(self, semantics: SemanticAnalyzer) -> None:
        self.sem = semantics
        self.context = ir.Context()
        self.module = ir.Module(name="epistula_minervae", context=self.context)
        self.module.triple = binding.get_default_triple()
        self.i1 = ir.IntType(1)
        self.i8 = ir.IntType(8)
        self.i32 = ir.IntType(32)
        self.i64 = ir.IntType(64)
        self.i8p = self.i8.as_pointer()
        self.input_type = self.context.get_identified_type("em_input")
        self.input_type.set_body(self.i1, self.i64, self.i8p)
        self.struct_types = {
            name: self.context.get_identified_type(f"em_struct_{name}")
            for name in semantics.structs
        }
        self.functions: dict[tuple[str | None, str], ir.Function] = {}
        self.global_ptrs: dict[str, ir.GlobalVariable] = {}
        self.string_counter = 0
        self.string_globals: dict[str, ir.GlobalVariable] = {}
        self.scopes: list[dict[str, ir.Value]] = []
        self.builder: ir.IRBuilder | None = None
        self.current_function: FunctionSymbol | None = None
        self.current_struct: str | None = None
        self.self_pointer: ir.Value | None = None
        self.power_functions: dict[str, ir.Function] = {}
        c_type = ir.FunctionType(self.i32, [self.i8p], var_arg=True)
        self.printf = ir.Function(self.module, c_type, name="printf")
        self.scanf = ir.Function(self.module, c_type, name="scanf")
        self.strcmp = ir.Function(
            self.module, ir.FunctionType(self.i32, [self.i8p, self.i8p]),
            name="strcmp")
        self.input_runtime = InputRuntime(self)

    def llvm_type(self, type_name: str) -> ir.Type:
        if type_name == I32:
            return self.i32
        if type_name == I64:
            return self.i64
        if type_name == BOOL:
            return self.i1
        if type_name == TEXT:
            return self.i8p
        if type_name == INPUT:
            return self.input_type
        if type_name == NIL:
            return ir.VoidType()
        return self.struct_types[type_name]

    def generate(self, program: ProgramNode) -> str:
        for name, symbol in self.sem.structs.items():
            self.struct_types[name].set_body(
                *(self.llvm_type(field.type_name) for field in symbol.fields))
        for name, symbol in self.sem.globals.items():
            global_value = ir.GlobalVariable(
                self.module, self.llvm_type(symbol.type_name), name=f"em_global_{name}")
            global_value.initializer = ir.Constant(self.llvm_type(symbol.type_name), None)
            self.global_ptrs[name] = global_value
        for symbol in self.sem.functions.values():
            self._declare_function(symbol)
        for struct in self.sem.structs.values():
            if struct.constructor:
                self._declare_function(struct.constructor)
            for symbol in struct.methods.values():
                self._declare_function(symbol)
        for symbol in self.sem.functions.values():
            self._function_body(symbol)
        for struct in self.sem.structs.values():
            if struct.constructor:
                self._function_body(struct.constructor)
            for symbol in struct.methods.values():
                self._function_body(symbol)
        main = ir.Function(self.module, ir.FunctionType(self.i32, []), name="main")
        self.builder = ir.IRBuilder(main.append_basic_block("entry"))
        self.scopes = [self.global_ptrs]
        self.current_function = None
        self.current_struct = None
        self.self_pointer = None
        for statement in program.statements:
            if not isinstance(statement, (FunctionDeclNode, StructDeclNode)):
                self._statement(statement)
        if not self.builder.block.is_terminated:
            self.builder.ret(ir.Constant(self.i32, 0))
        return str(self.module)

    def _declare_function(self, symbol: FunctionSymbol) -> None:
        parameters = [self.llvm_type(name) for name in symbol.parameter_types]
        if symbol.owner:
            parameters.insert(0, self.struct_types[symbol.owner].as_pointer())
            name = f"em_method_{symbol.owner}_{symbol.name}"
        else:
            name = f"em_fn_{symbol.name}"
        function_type = ir.FunctionType(self.llvm_type(symbol.result_type), parameters)
        self.functions[(symbol.owner, symbol.name)] = ir.Function(
            self.module, function_type, name=name)

    def _function_body(self, symbol: FunctionSymbol) -> None:
        llvm_function = self.functions[(symbol.owner, symbol.name)]
        self.builder = ir.IRBuilder(llvm_function.append_basic_block("entry"))
        self.current_function = symbol
        self.current_struct = symbol.owner
        self.self_pointer = llvm_function.args[0] if symbol.owner else None
        self.scopes = [self.global_ptrs, {}]
        args = llvm_function.args[1:] if symbol.owner else llvm_function.args
        for parameter, type_name, value in zip(symbol.node.parameters,
                                                symbol.parameter_types, args):
            value.name = parameter.name
            slot = self.builder.alloca(self.llvm_type(type_name), name=parameter.name)
            self.builder.store(value, slot)
            self.scopes[-1][parameter.name] = slot
        for statement in symbol.node.body:
            if self.builder.block.is_terminated:
                break
            self._statement(statement)
        if not self.builder.block.is_terminated:
            if symbol.result_type == NIL:
                self.builder.ret_void()
            else:
                self.builder.unreachable()

    def _statement(self, node: StmtNode) -> None:
        if isinstance(node, VarDeclNode):
            if self.current_function is None and len(self.scopes) == 1:
                type_name = self.sem.globals[node.name].type_name
                slot = self.global_ptrs[node.name]
            else:
                type_name = self.sem.variable_types[id(node)]
                slot = self.builder.alloca(self.llvm_type(type_name), name=node.name)
                self.scopes[-1][node.name] = slot
            value = self._value(node.initializer)
            self.builder.store(self._cast(value,
                                          self.sem.expression_types[id(node.initializer)],
                                          type_name), slot)
            return
        if isinstance(node, AssignmentNode):
            target = node.target or IdentifierNode(node.line, node.column, node.name)
            pointer = self._address(target)
            target_type = self.sem.assignment_target_types[id(node)]
            value = self._value(node.value)
            self.builder.store(self._cast(value,
                                          self.sem.expression_types[id(node.value)],
                                          target_type), pointer)
            return
        if isinstance(node, PrintNode):
            for argument in node.arguments:
                self._print_value(argument.value,
                                  self.sem.expression_types[id(argument.value)])
            return
        if isinstance(node, ReadStmtNode):
            if node.target is None:
                self._read(I32)
            else:
                target = IdentifierNode(node.line, node.column, node.target)
                target_type = self.sem.read_target_types[id(node)]
                self.builder.store(self._read(target_type), self._address(target))
            return
        if isinstance(node, ExprStmtNode):
            self._value(node.expression)
            return
        if isinstance(node, ReturnNode):
            result_type = self.current_function.result_type
            if result_type == NIL:
                self.builder.ret_void()
            else:
                value = self._value(node.value)
                self.builder.ret(self._cast(value,
                                            self.sem.expression_types[id(node.value)],
                                            result_type))
            return
        if isinstance(node, IfNode):
            self._if(node)
            return
        raise TypeError(type(node).__name__)

    def _if(self, node: IfNode) -> None:
        function = self.builder.function
        end = function.append_basic_block("if_end")
        branches = [(node.condition, node.then_body)]
        branches += [(branch.condition, branch.body) for branch in node.else_if_branches]
        for condition, body in branches:
            then = function.append_basic_block("if_then")
            next_condition = function.append_basic_block("if_next")
            self.builder.cbranch(self._value(condition), then, next_condition)
            self.builder.position_at_end(then)
            self.scopes.append({})
            for statement in body:
                if not self.builder.block.is_terminated:
                    self._statement(statement)
            self.scopes.pop()
            if not self.builder.block.is_terminated:
                self.builder.branch(end)
            self.builder.position_at_end(next_condition)
        if node.else_body is not None:
            self.scopes.append({})
            for statement in node.else_body:
                if not self.builder.block.is_terminated:
                    self._statement(statement)
            self.scopes.pop()
        if not self.builder.block.is_terminated:
            self.builder.branch(end)
        self.builder.position_at_end(end)

    def _value(self, node: ExprNode) -> ir.Value | None:
        type_name = self.sem.expression_types[id(node)]
        if isinstance(node, IntegerLiteralNode):
            return ir.Constant(self.llvm_type(type_name), node.value)
        if isinstance(node, BooleanLiteralNode):
            return ir.Constant(self.i1, int(node.value))
        if isinstance(node, NilLiteralNode):
            return None
        if isinstance(node, StringLiteralNode):
            return self._string_pointer(node.value)
        if isinstance(node, ReadExprNode):
            return self._read(type_name)
        if isinstance(node, (IdentifierNode, MemberAccessNode)):
            return self.builder.load(self._address(node))
        if isinstance(node, ConstructorNode):
            return self._constructor(node)
        if isinstance(node, CallNode):
            return self._call(node)
        if isinstance(node, UnaryExprNode):
            if (node.operator == "-" and isinstance(node.operand, IntegerLiteralNode)
                    and node.operand.value == 2**63):
                return ir.Constant(self.i64, -(2**63))
            operand = self._cast(self._value(node.operand),
                                 self.sem.expression_types[id(node.operand)], type_name)
            return operand if node.operator == "+" else self.builder.neg(operand)
        if isinstance(node, BinaryExprNode):
            left_type = self.sem.expression_types[id(node.left)]
            right_type = self.sem.expression_types[id(node.right)]
            left = self._cast(self._value(node.left), left_type, type_name)
            right = self._cast(self._value(node.right), right_type, type_name)
            operator = node.operator
            if operator in ("+", "adde"):
                return self.builder.add(left, right)
            if operator in ("-", "subtrahe"):
                return self.builder.sub(left, right)
            if operator in ("*", "multiplica"):
                return self.builder.mul(left, right)
            if operator in ("/", "divide"):
                self._guard_division(left, right, type_name)
                return self.builder.sdiv(left, right)
            if operator in ("%", "diviso integra"):
                self._guard_division(left, right, type_name)
                return self.builder.srem(left, right)
            if operator in ("^", "exponens"):
                return self.builder.call(self._power_function(type_name), [left, right])
        if isinstance(node, ComparisonExprNode):
            return self._comparison(node)
        raise TypeError(type(node).__name__)

    def _guard_division(self, left, right, type_name):
        zero = ir.Constant(self.llvm_type(type_name), 0)
        minimum = ir.Constant(self.llvm_type(type_name), -(2**(63 if type_name == I64 else 31)))
        negative_one = ir.Constant(self.llvm_type(type_name), -1)
        nonzero = self.builder.icmp_signed("!=", right, zero)
        overflow = self.builder.and_(self.builder.icmp_signed("==", left, minimum),
                                     self.builder.icmp_signed("==", right, negative_one))
        self.input_runtime.guard(self.builder.and_(nonzero, self.builder.not_(overflow)),
                                 "invalid integer division")

    def _input_comparison(self, node, left_type, right_type, equality):
        left, right = self._value(node.left), self._value(node.right)
        if left_type not in NUMERIC | {INPUT, TEXT, NIL} or right_type not in NUMERIC | {INPUT, TEXT, NIL}:
            return ir.Constant(self.i1, int(not equality))
        left = self._cast(left, left_type, INPUT)
        right = self._cast(right, right_type, INPUT)
        left_tag, right_tag = self.builder.extract_value(left, 0), self.builder.extract_value(right, 0)
        same = self.builder.function.append_basic_block("input_same_type")
        different = self.builder.function.append_basic_block("input_different_type")
        numeric = self.builder.function.append_basic_block("input_numeric_compare")
        text = self.builder.function.append_basic_block("input_text_compare")
        done = self.builder.function.append_basic_block("input_compare_end")
        self.builder.cbranch(self.builder.icmp_unsigned("==", left_tag, right_tag), same, different)
        self.builder.position_at_end(different)
        self.builder.branch(done)
        self.builder.position_at_end(same)
        self.builder.cbranch(left_tag, numeric, text)
        self.builder.position_at_end(numeric)
        numbers_equal = self.builder.icmp_signed(
            "==", self.builder.extract_value(left, 1), self.builder.extract_value(right, 1))
        self.builder.branch(done)
        self.builder.position_at_end(text)
        texts_equal = self._text_equal(self.builder.extract_value(left, 2),
                                       self.builder.extract_value(right, 2))
        text_end = self.builder.block
        self.builder.branch(done)
        self.builder.position_at_end(done)
        result = self.builder.phi(self.i1)
        result.add_incoming(ir.Constant(self.i1, 0), different)
        result.add_incoming(numbers_equal, numeric)
        result.add_incoming(texts_equal, text_end)
        return result if equality else self.builder.not_(result)

    def _text_equal(self, left, right):
        left_null = self.builder.icmp_unsigned("==", left, ir.Constant(self.i8p, None))
        right_null = self.builder.icmp_unsigned("==", right, ir.Constant(self.i8p, None))
        null_block = self.builder.function.append_basic_block("text_null")
        compare_block = self.builder.function.append_basic_block("text_compare")
        end_block = self.builder.function.append_basic_block("text_equal_end")
        self.builder.cbranch(self.builder.or_(left_null, right_null), null_block, compare_block)
        self.builder.position_at_end(null_block)
        null_equal = self.builder.and_(left_null, right_null)
        self.builder.branch(end_block)
        self.builder.position_at_end(compare_block)
        result = self.builder.call(self.strcmp, [left, right])
        compared = self.builder.icmp_signed("==", result, ir.Constant(self.i32, 0))
        self.builder.branch(end_block)
        self.builder.position_at_end(end_block)
        equal = self.builder.phi(self.i1)
        equal.add_incoming(null_equal, null_block)
        equal.add_incoming(compared, compare_block)
        return equal

    def _comparison(self, node: ComparisonExprNode) -> ir.Value:
        left_type = self.sem.expression_types[id(node.left)]
        right_type = self.sem.expression_types[id(node.right)]
        equality = node.operator in ("o-o", "idem")
        if INPUT in (left_type, right_type):
            return self._input_comparison(node, left_type, right_type, equality)
        if left_type == NIL and right_type == NIL:
            return ir.Constant(self.i1, int(equality))
        if left_type == NIL or right_type == NIL:
            other = node.right if left_type == NIL else node.left
            other_type = right_type if left_type == NIL else left_type
            if other_type in NUMERIC or other_type == BOOL:
                value = self._value(other)
                predicate = "==" if equality else "!="
                return self.builder.icmp_signed(
                    predicate, value, ir.Constant(self.llvm_type(other_type), 0))
            if other_type == TEXT:
                value = self._value(other)
                return self.builder.icmp_unsigned(
                    "==" if equality else "!=", value,
                    ir.Constant(self.i8p, None))
            return ir.Constant(self.i1, int(not equality))
        if left_type in NUMERIC and right_type in NUMERIC:
            width = I64 if I64 in (left_type, right_type) else I32
            left = self._cast(self._value(node.left), left_type, width)
            right = self._cast(self._value(node.right), right_type, width)
            return self.builder.icmp_signed("==" if equality else "!=", left, right)
        if left_type == right_type == BOOL:
            return self.builder.icmp_signed(
                "==" if equality else "!=", self._value(node.left), self._value(node.right))
        if left_type == right_type == TEXT:
            left, right = self._value(node.left), self._value(node.right)
            equal = self._text_equal(left, right)
            return equal if equality else self.builder.not_(equal)
        self._value(node.left)
        self._value(node.right)
        return ir.Constant(self.i1, int(not equality))

    def _constructor(self, node: ConstructorNode) -> ir.Value:
        struct = self.sem.structs[node.type_name]
        slot = self.builder.alloca(self.struct_types[node.type_name])
        self.builder.store(ir.Constant(self.struct_types[node.type_name], None), slot)
        # Evaluate supplied arguments in their source order and caller scope.
        values = {id(argument.value): self._value(argument.value) for argument in node.arguments}
        bound = self.sem.constructor_fields.get(id(node), {})
        previous_struct, previous_self = self.current_struct, self.self_pointer
        previous_scopes = self.scopes
        try:
            self.current_struct, self.self_pointer = node.type_name, slot
            self.scopes = [self.global_ptrs]
            for field in struct.fields:
                expression = bound.get(field.name) or field.initializer
                if expression is None:
                    continue
                value = values[id(expression)] if id(expression) in values else self._value(expression)
                from_type = self.sem.expression_types[id(expression)]
                pointer = self.builder.gep(slot, [ir.Constant(self.i32, 0),
                                                  ir.Constant(self.i32, field.index)])
                self.builder.store(self._cast(value, from_type, field.type_name), pointer)
        finally:
            self.current_struct, self.self_pointer = previous_struct, previous_self
            self.scopes = previous_scopes
        if struct.constructor:
            symbol = struct.constructor
            args = [slot]
            for expression, expected in zip(self.sem.constructor_arguments[id(node)], symbol.parameter_types):
                args.append(self._cast(values[id(expression)],
                                       self.sem.expression_types[id(expression)], expected))
            self.builder.call(self.functions[(symbol.owner, symbol.name)], args)
        return self.builder.load(slot)

    def _call(self, node: CallNode) -> ir.Value | None:
        symbol = self.sem.call_symbols[id(node)]
        function = self.functions[(symbol.owner, symbol.name)]
        arguments: list[ir.Value] = []
        if symbol.owner:
            if isinstance(node.callee, MemberAccessNode):
                arguments.append(self._address(node.callee.object))
            else:
                arguments.append(self.self_pointer)
        for argument, target_type in zip(node.arguments, symbol.parameter_types):
            value = self._value(argument)
            arguments.append(self._cast(value,
                                        self.sem.expression_types[id(argument)],
                                        target_type))
        return self.builder.call(function, arguments)

    def _address(self, node: ExprNode) -> ir.Value:
        if isinstance(node, IdentifierNode):
            for scope in reversed(self.scopes[1:]):
                if node.name in scope:
                    return scope[node.name]
            if self.current_struct and node.name == "hoc":
                return self.self_pointer
            if self.current_struct:
                field = self.sem.structs[self.current_struct].field_named(node.name)
                if field:
                    return self.builder.gep(
                        self.self_pointer, [ir.Constant(self.i32, 0),
                                            ir.Constant(self.i32, field.index)])
            return self.global_ptrs[node.name]
        if isinstance(node, MemberAccessNode):
            base_type = self._address_type(node.object)
            struct = self.sem.structs[base_type]
            field = struct.field_named(node.name)
            return self.builder.gep(self._address(node.object),
                                    [ir.Constant(self.i32, 0),
                                     ir.Constant(self.i32, field.index)])
        value = self._value(node)
        slot = self.builder.alloca(self.llvm_type(self.sem.expression_types[id(node)]))
        self.builder.store(value, slot)
        return slot

    def _address_type(self, node: ExprNode) -> str:
        if id(node) in self.sem.expression_types:
            return self.sem.expression_types[id(node)]
        if isinstance(node, IdentifierNode):
            for scope in reversed(self.sem.scopes[1:]):
                if node.name in scope:
                    return scope[node.name].type_name
            if self.current_struct:
                field = self.sem.structs[self.current_struct].field_named(node.name)
                if field:
                    return field.type_name
            return self.sem.globals[node.name].type_name
        return self.sem.expression_types[id(node)]

    def _cast(self, value: ir.Value | None, actual: str, expected: str) -> ir.Value:
        if actual == NIL:
            return ir.Constant(self.llvm_type(expected), None)
        if actual == expected:
            return value
        if actual == INPUT:
            return self.input_runtime.convert(value, expected)
        if expected == INPUT:
            return self.input_runtime.box(value, actual)
        if actual == I32 and expected == I64:
            return self.builder.sext(value, self.i64)
        if actual == I64 and expected == I32:
            return self.builder.trunc(value, self.i32)
        return value

    def _read(self, type_name: str) -> ir.Value:
        return self.input_runtime.read(type_name)

    def _print_text(self, text: str) -> None:
        self.builder.call(self.printf, [self._string_pointer("%s"),
                                        self._string_pointer(text)])

    def _print_value(self, node: ExprNode, type_name: str) -> None:
        if type_name == NIL:
            self._print_text("nihil")
            return
        value = self._value(node)
        self._print_loaded(value, type_name)

    def _print_loaded(self, value: ir.Value, type_name: str) -> None:
        if type_name == INPUT:
            numeric = self.builder.function.append_basic_block("print_input_number")
            text = self.builder.function.append_basic_block("print_input_text")
            done = self.builder.function.append_basic_block("print_input_end")
            self.builder.cbranch(self.builder.extract_value(value, 0), numeric, text)
            self.builder.position_at_end(numeric)
            self._print_loaded(self.builder.extract_value(value, 1), I64)
            self.builder.branch(done)
            self.builder.position_at_end(text)
            self._print_loaded(self.builder.extract_value(value, 2), TEXT)
            self.builder.branch(done)
            self.builder.position_at_end(done)
        elif type_name == I32:
            self.builder.call(self.printf, [self._string_pointer("%d"), value])
        elif type_name == I64:
            self.builder.call(self.printf, [self._string_pointer("%lld"), value])
        elif type_name == BOOL:
            true_block = self.builder.function.append_basic_block("print_true")
            false_block = self.builder.function.append_basic_block("print_false")
            end_block = self.builder.function.append_basic_block("print_end")
            self.builder.cbranch(value, true_block, false_block)
            self.builder.position_at_end(true_block)
            self._print_text("true")
            self.builder.branch(end_block)
            self.builder.position_at_end(false_block)
            self._print_text("false")
            self.builder.branch(end_block)
            self.builder.position_at_end(end_block)
        elif type_name == TEXT:
            null_block = self.builder.function.append_basic_block("print_null_text")
            text_block = self.builder.function.append_basic_block("print_text")
            end_block = self.builder.function.append_basic_block("print_text_end")
            is_null = self.builder.icmp_unsigned(
                "==", value, ir.Constant(self.i8p, None))
            self.builder.cbranch(is_null, null_block, text_block)
            self.builder.position_at_end(null_block)
            self._print_text("nihil")
            self.builder.branch(end_block)
            self.builder.position_at_end(text_block)
            self.builder.call(self.printf, [self._string_pointer("%s"), value])
            self.builder.branch(end_block)
            self.builder.position_at_end(end_block)
        elif type_name in self.sem.structs:
            struct = self.sem.structs[type_name]
            slot = self.builder.alloca(self.struct_types[type_name])
            self.builder.store(value, slot)
            self._print_text(f"{type_name}{{")
            for index, field in enumerate(struct.fields):
                if index:
                    self._print_text(", ")
                self._print_text(f"{field.name}=")
                ptr = self.builder.gep(slot, [ir.Constant(self.i32, 0),
                                              ir.Constant(self.i32, field.index)])
                self._print_loaded(self.builder.load(ptr), field.type_name)
            self._print_text("}")

    def _string_pointer(self, text: str) -> ir.Value:
        if text not in self.string_globals:
            data = text.encode("utf-8") + b"\0"
            array_type = ir.ArrayType(self.i8, len(data))
            global_value = ir.GlobalVariable(
                self.module, array_type, name=f".em_str_{self.string_counter}")
            self.string_counter += 1
            global_value.linkage = "internal"
            global_value.global_constant = True
            global_value.initializer = ir.Constant(array_type, bytearray(data))
            self.string_globals[text] = global_value
        return self.builder.gep(self.string_globals[text],
                                [ir.Constant(self.i32, 0), ir.Constant(self.i32, 0)])

    def _power_function(self, type_name: str) -> ir.Function:
        if type_name in self.power_functions:
            return self.power_functions[type_name]
        integer_type = self.llvm_type(type_name)
        helper = ir.Function(self.module,
                             ir.FunctionType(integer_type, [integer_type, integer_type]),
                             name=f"em_pow_{'i64' if type_name == I64 else 'i32'}")
        self.power_functions[type_name] = helper
        saved_builder = self.builder
        builder = ir.IRBuilder(helper.append_basic_block("entry"))
        result = builder.alloca(integer_type)
        exponent = builder.alloca(integer_type)
        builder.store(ir.Constant(integer_type, 1), result)
        builder.store(helper.args[1], exponent)
        negative = helper.append_basic_block("negative")
        loop_test = helper.append_basic_block("test")
        loop_body = helper.append_basic_block("body")
        done = helper.append_basic_block("done")
        builder.cbranch(builder.icmp_signed("<", helper.args[1],
                                          ir.Constant(integer_type, 0)),
                        negative, loop_test)
        builder.position_at_end(negative)
        builder.ret(ir.Constant(integer_type, 0))
        builder.position_at_end(loop_test)
        builder.cbranch(builder.icmp_signed(">", builder.load(exponent),
                                          ir.Constant(integer_type, 0)),
                        loop_body, done)
        builder.position_at_end(loop_body)
        builder.store(builder.mul(builder.load(result), helper.args[0]), result)
        builder.store(builder.sub(builder.load(exponent),
                                  ir.Constant(integer_type, 1)), exponent)
        builder.branch(loop_test)
        builder.position_at_end(done)
        builder.ret(builder.load(result))
        self.builder = saved_builder
        return helper
