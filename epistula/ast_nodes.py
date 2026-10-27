from __future__ import annotations

from dataclasses import dataclass, field
import json


def _value_text(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@dataclass
class ASTNode:
    line: int
    column: int

    def _header(self, depth: int, node_name: str, **fields: object) -> str:
        suffix = "".join(f" {key}={_value_text(value)}" for key, value in fields.items())
        return f"{'  ' * depth}{node_name} @{self.line}:{self.column}{suffix}"

    def dump_lines(self, depth: int = 0) -> list[str]:
        raise NotImplementedError


@dataclass
class ProgramNode(ASTNode):
    statements: list[StmtNode] = field(default_factory=list)

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "Program", statements=len(self.statements))]
        for statement in self.statements:
            lines.extend(statement.dump_lines(depth + 1))
        return lines

    def dump(self) -> str:
        return "\n".join(self.dump_lines()) + "\n"


@dataclass
class StmtNode(ASTNode):
    pass


@dataclass
class ExprNode(ASTNode):
    pass


@dataclass
class VarDeclNode(StmtNode):
    keyword: str
    type_name: str | None
    name: str
    mutable: bool
    initializer: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(
            depth,
            "VarDecl",
            name=self.name,
            type=self.type_name,
            mutable=self.mutable,
            keyword=self.keyword,
        )]
        lines.extend(self.initializer.dump_lines(depth + 1))
        return lines


@dataclass
class AssignmentNode(StmtNode):
    name: str
    operator: str
    value: ExprNode
    target: ExprNode | None = None

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "Assignment", name=self.name, operator=self.operator)]
        if self.target is not None:
            lines.extend(self.target.dump_lines(depth + 1))
        lines.extend(self.value.dump_lines(depth + 1))
        return lines


@dataclass
class PrintArgumentNode(ASTNode):
    quoted: bool
    value: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "PrintArgument", quoted=self.quoted)]
        lines.extend(self.value.dump_lines(depth + 1))
        return lines


@dataclass
class PrintNode(StmtNode):
    arguments: list[PrintArgumentNode]

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "Print", arguments=len(self.arguments))]
        for argument in self.arguments:
            lines.extend(argument.dump_lines(depth + 1))
        return lines


@dataclass
class ReadStmtNode(StmtNode):
    target: str | None

    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "ReadStmt", target=self.target)]


@dataclass
class ElseIfNode(ASTNode):
    condition: ExprNode
    body: list[StmtNode]

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "ElseIf", statements=len(self.body))]
        lines.append(f"{'  ' * (depth + 1)}Condition")
        lines.extend(self.condition.dump_lines(depth + 2))
        lines.append(f"{'  ' * (depth + 1)}Body")
        for statement in self.body:
            lines.extend(statement.dump_lines(depth + 2))
        return lines


@dataclass
class IfNode(StmtNode):
    condition: ExprNode
    then_body: list[StmtNode]
    else_if_branches: list[ElseIfNode]
    else_body: list[StmtNode] | None

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(
            depth,
            "If",
            then_statements=len(self.then_body),
            else_if_branches=len(self.else_if_branches),
            has_else=self.else_body is not None,
        )]
        lines.append(f"{'  ' * (depth + 1)}Condition")
        lines.extend(self.condition.dump_lines(depth + 2))
        lines.append(f"{'  ' * (depth + 1)}Then")
        for statement in self.then_body:
            lines.extend(statement.dump_lines(depth + 2))
        for branch in self.else_if_branches:
            lines.extend(branch.dump_lines(depth + 1))
        if self.else_body is not None:
            lines.append(f"{'  ' * (depth + 1)}Else statements={len(self.else_body)}")
            for statement in self.else_body:
                lines.extend(statement.dump_lines(depth + 2))
        return lines


@dataclass
class IntegerLiteralNode(ExprNode):
    text: str
    value: int
    notation: str

    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(
            depth,
            "IntegerLiteral",
            text=self.text,
            value=self.value,
            notation=self.notation,
        )]


@dataclass
class BooleanLiteralNode(ExprNode):
    value: bool

    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "BooleanLiteral", value=self.value)]


@dataclass
class NilLiteralNode(ExprNode):
    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "NilLiteral")]


@dataclass
class StringLiteralNode(ExprNode):
    value: str

    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "StringLiteral", value=self.value)]


@dataclass
class IdentifierNode(ExprNode):
    name: str

    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "Identifier", name=self.name)]


@dataclass
class ReadExprNode(ExprNode):
    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "ReadExpr")]


@dataclass
class UnaryExprNode(ExprNode):
    operator: str
    operand: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "UnaryExpr", operator=self.operator)]
        lines.extend(self.operand.dump_lines(depth + 1))
        return lines


@dataclass
class BinaryExprNode(ExprNode):
    operator: str
    left: ExprNode
    right: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "BinaryExpr", operator=self.operator)]
        lines.extend(self.left.dump_lines(depth + 1))
        lines.extend(self.right.dump_lines(depth + 1))
        return lines


@dataclass
class ComparisonExprNode(ExprNode):
    operator: str
    left: ExprNode
    right: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "ComparisonExpr", operator=self.operator)]
        lines.extend(self.left.dump_lines(depth + 1))
        lines.extend(self.right.dump_lines(depth + 1))
        return lines


@dataclass
class ParameterNode(ASTNode):
    type_name: str
    name: str

    def dump_lines(self, depth: int = 0) -> list[str]:
        return [self._header(depth, "Parameter", name=self.name, type=self.type_name)]


@dataclass
class ReturnNode(StmtNode):
    value: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "Return")]
        lines.extend(self.value.dump_lines(depth + 1))
        return lines


@dataclass
class FunctionDeclNode(StmtNode):
    name: str
    parameters: list[ParameterNode]
    result_type: str
    body: list[StmtNode]
    alternate: bool = False
    constructor: bool = False

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "FunctionDecl", name=self.name,
                              result_type=self.result_type, parameters=len(self.parameters),
                              alternate=self.alternate, statements=len(self.body))]
        if self.constructor:
            lines[0] += " constructor=true"
        for parameter in self.parameters:
            lines.extend(parameter.dump_lines(depth + 1))
        for statement in self.body:
            lines.extend(statement.dump_lines(depth + 1))
        return lines


@dataclass
class FieldDeclNode(ASTNode):
    keyword: str
    type_name: str | None
    name: str
    mutable: bool
    initializer: ExprNode | None

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "FieldDecl", name=self.name, type=self.type_name,
                              mutable=self.mutable, has_default=self.initializer is not None)]
        if self.initializer is not None:
            lines.extend(self.initializer.dump_lines(depth + 1))
        return lines


@dataclass
class StructDeclNode(StmtNode):
    name: str
    immutable: bool
    fields: list[FieldDeclNode]
    methods: list[FunctionDeclNode]
    nested: list[StructDeclNode] = field(default_factory=list)

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "StructDecl", name=self.name,
                              immutable=self.immutable, fields=len(self.fields),
                              methods=len(self.methods))]
        for field_node in self.fields:
            lines.extend(field_node.dump_lines(depth + 1))
        for method in self.methods:
            lines.extend(method.dump_lines(depth + 1))
        for nested in self.nested:
            lines.extend(nested.dump_lines(depth + 1))
        return lines


@dataclass
class MemberAccessNode(ExprNode):
    object: ExprNode
    name: str
    separator: str

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "MemberAccess", name=self.name,
                              separator=self.separator)]
        lines.extend(self.object.dump_lines(depth + 1))
        return lines


@dataclass
class CallNode(ExprNode):
    callee: ExprNode
    arguments: list[ExprNode]
    syntax: str

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "Call", arguments=len(self.arguments),
                              syntax=self.syntax,
                              ends_member_chain=isinstance(self.callee, MemberAccessNode))]
        lines.extend(self.callee.dump_lines(depth + 1))
        for argument in self.arguments:
            lines.extend(argument.dump_lines(depth + 1))
        return lines


@dataclass
class ConstructorArgNode(ASTNode):
    name: str | None
    value: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "ConstructorArg", name=self.name)]
        lines.extend(self.value.dump_lines(depth + 1))
        return lines


@dataclass
class ConstructorNode(ExprNode):
    type_name: str
    arguments: list[ConstructorArgNode]
    syntax: str = "cape"

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "Constructor", type=self.type_name,
                              arguments=len(self.arguments))]
        if self.syntax == "novum":
            lines[0] += ' syntax="novum"'
        for argument in self.arguments:
            lines.extend(argument.dump_lines(depth + 1))
        return lines


@dataclass
class ExprStmtNode(StmtNode):
    expression: ExprNode

    def dump_lines(self, depth: int = 0) -> list[str]:
        lines = [self._header(depth, "ExprStmt")]
        lines.extend(self.expression.dump_lines(depth + 1))
        return lines
