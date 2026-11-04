"""Conservative transformations on semantically checked trees."""
from __future__ import annotations
import copy
from dataclasses import fields, is_dataclass
from .ast_nodes import *
from .semantics import SemanticAnalyzer, NIL, INPUT

def walk(node):
    if not isinstance(node, ASTNode):
        return
    yield node
    for f in fields(node):
        value = getattr(node, f.name)
        if isinstance(value, ASTNode):
            yield from walk(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ASTNode):
                    yield from walk(item)

def call_counts(program, sem):
    counts = {name: 0 for name in sem.functions}
    for node in walk(program):
        if isinstance(node, CallNode):
            symbol = sem.call_symbols.get(id(node))
            if symbol and symbol.owner is None:
                counts[symbol.name] += 1
    return counts

def erase_unused_functions(program, sem):
    counts = call_counts(program, sem)
    removed = {name for name, count in counts.items() if count == 0}
    used_methods = {id(symbol.node) for symbol in sem.call_symbols.values()
                    if symbol.owner is not None}
    changed = bool(removed)
    program.statements[:] = [
        node for node in program.statements
        if not (isinstance(node, FunctionDeclNode) and node.name in removed)
    ]
    for struct in sem.structs.values():
        methods = struct.node.methods
        kept = [method for method in methods if method.constructor or id(method) in used_methods]
        if len(kept) != len(methods):
            methods[:] = kept
            changed = True
    return changed

def recursive(name, sem):
    def search(current, seen):
        if current in seen:
            return False
        seen = seen | {current}
        symbol = sem.functions[current]
        for node in walk(symbol.node):
            if isinstance(node, CallNode):
                target = sem.call_symbols.get(id(node))
                if target and target.owner is None:
                    if target.name == name or search(target.name, seen):
                        return True
        return False
    return search(name, set())

def statement_lists(program):
    yield program.statements
    for node in walk(program):
        if isinstance(node, FunctionDeclNode):
            yield node.body
        elif isinstance(node, IfNode):
            yield node.then_body
            for branch in node.else_if_branches:
                yield branch.body
            if node.else_body is not None:
                yield node.else_body
        elif isinstance(node, LoopNode):
            yield node.body

def rename(node, names):
    for item in walk(node):
        if isinstance(item, IdentifierNode) and item.name in names:
            item.name = names[item.name]

def inline_once(program, sem):
    counts = call_counts(program, sem)
    candidates = {}
    for name, symbol in sem.functions.items():
        body = symbol.node.body
        if (counts[name] != 1 or symbol.node.thread or symbol.result_type == NIL
                or any("[" in t for t in symbol.parameter_types)
                or not body or not isinstance(body[-1], ReturnNode)
                or any(not isinstance(item, VarDeclNode) for item in body[:-1])
                or any(isinstance(item, CallNode) for item in walk(symbol.node))
                or recursive(name, sem)):
            continue
        # A free global name could bind to a caller-local name after substitution.
        # Inline only bodies whose variable references are parameters or locals.
        bound = {parameter.name for parameter in symbol.node.parameters}
        safe = True
        for statement in body:
            expression = statement.initializer if isinstance(statement, VarDeclNode) else statement.value
            for item in walk(expression):
                if isinstance(item, IdentifierNode) and item.name in sem.globals and item.name not in bound:
                    safe = False
            if isinstance(statement, VarDeclNode):
                bound.add(statement.name)
        if safe:
            candidates[name] = symbol
    if not candidates:
        return False
    used_names = set()
    for node in walk(program):
        if isinstance(node, (IdentifierNode, VarDeclNode, ParameterNode, FunctionDeclNode,
                             StructDeclNode, FieldDeclNode, ThreadStartNode)):
            used_names.add(node.name)
        if isinstance(node, LoopNode) and node.index_name:
            used_names.add(node.index_name)
    serial = 0
    def fresh():
        nonlocal serial
        while True:
            serial += 1
            name = f"stage3_inline_{serial}"
            if name not in used_names:
                used_names.add(name)
                return name
    for statements in statement_lists(program):
        for position, statement in enumerate(statements):
            if isinstance(statement, VarDeclNode):
                call = statement.initializer
            elif isinstance(statement, AssignmentNode) and statement.target is None:
                call = statement.value
            elif isinstance(statement, ReturnNode):
                call = statement.value
            else:
                continue
            if not isinstance(call, CallNode):
                continue
            symbol = sem.call_symbols.get(id(call))
            if not symbol or symbol.owner is not None or symbol.name not in candidates:
                continue
            names = {}
            prefix = []
            for parameter, argument in zip(symbol.node.parameters, call.arguments):
                generated = fresh()
                prefix.append(VarDeclNode(argument.line, argument.column, "",
                                          parameter.type_name, generated, True, argument))
                names[parameter.name] = generated
            for original in symbol.node.body[:-1]:
                local = copy.deepcopy(original)
                rename(local.initializer, names)
                generated = fresh()
                names[local.name] = generated
                local.name = generated
                prefix.append(local)
            result_value = copy.deepcopy(symbol.node.body[-1].value)
            rename(result_value, names)
            result_name = fresh()
            prefix.append(VarDeclNode(result_value.line, result_value.column, "",
                                      symbol.node.result_type, result_name, True, result_value))
            result = IdentifierNode(result_value.line, result_value.column, result_name)
            if isinstance(statement, VarDeclNode):
                statement.initializer = result
            else:
                statement.value = result
            statements[position:position] = prefix
            return True
    return False

class VariableUses:
    def __init__(self, program, sem):
        self.program = program
        self.sem = sem
        self.decls = {}
        self.read = set()
        self.writes = {}
        self.globals = {n.name: n for n in program.statements if isinstance(n, VarDeclNode)}
        self.global_mentions = set()
        for node in walk(program):
            if isinstance(node, IdentifierNode) and node.name in self.globals:
                self.global_mentions.add(node.name)

    def resolve(self, scopes, name):
        for scope in reversed(scopes):
            if name in scope:
                return scope[name]
        return None

    def expression(self, node, scopes):
        if node is None:
            return
        for item in walk(node):
            if isinstance(item, IdentifierNode):
                target = self.resolve(scopes, item.name)
                if isinstance(target, VarDeclNode):
                    self.read.add(id(target))

    def statements(self, statements, scopes):
        for statement in statements:
            if isinstance(statement, VarDeclNode):
                self.expression(statement.initializer, scopes)
                self.decls[id(statement)] = (statements, statement)
                scopes[-1][statement.name] = statement
            elif isinstance(statement, AssignmentNode):
                self.expression(statement.value, scopes)
                if statement.target is None:
                    target = self.resolve(scopes, statement.name)
                    if isinstance(target, VarDeclNode):
                        self.writes.setdefault(id(target), []).append((statements, statement))
                else:
                    self.expression(statement.target, scopes)
            elif isinstance(statement, IfNode):
                self.expression(statement.condition, scopes)
                self.statements(statement.then_body, scopes + [{}])
                for branch in statement.else_if_branches:
                    self.expression(branch.condition, scopes)
                    self.statements(branch.body, scopes + [{}])
                if statement.else_body is not None:
                    self.statements(statement.else_body, scopes + [{}])
            elif isinstance(statement, LoopNode):
                self.expression(statement.condition, scopes)
                self.expression(statement.start, scopes)
                self.expression(statement.end, scopes)
                scope = {statement.index_name: None} if statement.index_name else {}
                self.statements(statement.body, scopes + [scope])
            elif isinstance(statement, FunctionDeclNode):
                scope = {parameter.name: None for parameter in statement.parameters}
                self.statements(statement.body, [self.globals, scope])
            elif isinstance(statement, StructDeclNode):
                self.structure(statement)
            elif isinstance(statement, ReadStmtNode):
                if statement.target is not None:
                    target = self.resolve(scopes, statement.target)
                    if isinstance(target, VarDeclNode):
                        self.writes.setdefault(id(target), []).append((statements, statement))
            elif isinstance(statement, ThreadStartNode):
                self.expression(statement.call, scopes)
                scopes[-1][statement.name] = None
            elif isinstance(statement, ThreadJoinNode):
                pass
            else:
                self.expression(statement, scopes)

    def structure(self, node):
        field_scope = {field.name: None for field in node.fields}
        for field in node.fields:
            self.expression(field.initializer, [self.globals, field_scope])
        for method in node.methods:
            scope = {p.name: None for p in method.parameters}
            self.statements(method.body, [self.globals, field_scope, scope])
        for nested in node.nested:
            self.structure(nested)

    def scan(self):
        self.statements(self.program.statements, [dict(self.globals)])

def can_drop(node, actual, expected):
    # Keep conversions from dynamically typed input, all operations, calls,
    # indexing and constructors, because they may fail or have side effects.
    if actual == INPUT and expected != INPUT:
        return False
    return isinstance(node, (IntegerLiteralNode, BooleanLiteralNode,
                             StringLiteralNode, NilLiteralNode, IdentifierNode))

def erase_unused_variables(program, sem):
    uses = VariableUses(program, sem)
    uses.scan()
    unused = set(uses.decls) - uses.read
    if not unused:
        return False
    edits = {}
    for key in unused:
        statements, decl = uses.decls[key]
        expected = sem.variable_types[id(decl)]
        actual = sem.expression_types[id(decl.initializer)]
        replacement = None if can_drop(decl.initializer, actual, expected) else DiscardNode(
            decl.line, decl.column, decl.initializer, expected)
        edits[id(decl)] = replacement
        for _, assignment in uses.writes.get(key, []):
            if isinstance(assignment, ReadStmtNode):
                read = ReadExprNode(assignment.line, assignment.column)
                edits[id(assignment)] = DiscardNode(assignment.line, assignment.column,
                                                     read, sem.read_target_types[id(assignment)])
            else:
                expected = sem.assignment_target_types[id(assignment)]
                actual = sem.expression_types[id(assignment.value)]
                edits[id(assignment)] = None if can_drop(assignment.value, actual, expected) else DiscardNode(
                    assignment.line, assignment.column, assignment.value, expected)
    for statements in statement_lists(program):
        statements[:] = [edits.get(id(node), node) for node in statements
                         if id(node) not in edits or edits[id(node)] is not None]
    return True

def optimize(program, sem):
    while True:
        if erase_unused_functions(program, sem):
            sem = SemanticAnalyzer().analyze(program)
            continue
        if inline_once(program, sem):
            sem = SemanticAnalyzer().analyze(program)
            continue
        if erase_unused_variables(program, sem):
            sem = SemanticAnalyzer().analyze(program)
            continue
        return sem
