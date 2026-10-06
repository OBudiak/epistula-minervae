from __future__ import annotations

from .ast_nodes import (
    AssignmentNode,
    BinaryExprNode,
    ExprNode,
    IfNode,
    IntegerLiteralNode,
    ProgramNode,
    StmtNode,
    UnaryExprNode,
    VarDeclNode,
)
from .errors import CompilationError


_LIMITS = {
    "32bitInt": (-(2**31), 2**31 - 1),
    "64bitInt": (-(2**63), 2**63 - 1),
}


class OverflowChecker:
    """Checks statically evaluable integer values against their target type."""

    def __init__(self) -> None:
        self.variable_types: dict[str, str] = {}

    def check(self, program: ProgramNode) -> None:
        self._check_statements(program.statements)

    def _check_statements(self, statements: list[StmtNode]) -> None:
        for statement in statements:
            if isinstance(statement, VarDeclNode):
                self.variable_types[statement.name] = statement.type_name
                self._check_expression_for_type(statement.initializer, statement.type_name)
            elif isinstance(statement, AssignmentNode):
                type_name = self.variable_types.get(statement.name)
                if type_name is not None:
                    self._check_expression_for_type(statement.value, type_name)
            elif isinstance(statement, IfNode):
                self._check_statements(statement.then_body)
                for branch in statement.else_if_branches:
                    self._check_statements(branch.body)
                if statement.else_body is not None:
                    self._check_statements(statement.else_body)

    def _check_expression_for_type(self, expression: ExprNode, type_name: str) -> None:
        limits = _LIMITS.get(type_name)
        if limits is None:
            return
        value = self._constant_integer(expression)
        if value is None:
            return
        minimum, maximum = limits
        if value < minimum or value > maximum:
            raise CompilationError(
                expression.line,
                expression.column,
                f"Valor fines {type_name} excedit.",
            )

    def _constant_integer(self, expression: ExprNode) -> int | None:
        if isinstance(expression, IntegerLiteralNode):
            return expression.value
        if isinstance(expression, UnaryExprNode):
            operand = self._constant_integer(expression.operand)
            if operand is None:
                return None
            if expression.operator == "+":
                return operand
            if expression.operator == "-":
                return -operand
            return None
        if isinstance(expression, BinaryExprNode):
            left = self._constant_integer(expression.left)
            right = self._constant_integer(expression.right)
            if left is None or right is None:
                return None
            operator = expression.operator
            if operator in ("+", "adde"):
                return left + right
            if operator in ("-", "subtrahe"):
                return left - right
            if operator in ("*", "multiplica"):
                return left * right
            if operator in ("/", "divide"):
                if right == 0:
                    return None
                quotient = abs(left) // abs(right)
                return -quotient if (left < 0) != (right < 0) else quotient
            if operator in ("%", "diviso integra"):
                if right == 0:
                    return None
                return left % right
            if operator in ("^", "exponens"):
                if right < 0 or right > 10000:
                    return None
                return left**right
        return None

