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
    "integer": (-(2**31), 2**31 - 1),
    "duplex": (-(2**63), 2**63 - 1),
}


class OverflowChecker:
    """Checks statically evaluable integer values against their target type."""

    def __init__(self) -> None:
        self.variable_types: dict[str, str] = {}

    def check(self, program: ProgramNode) -> None:
        self.variable_types = {}
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
                self._check_block(statement.then_body)
                for branch in statement.else_if_branches:
                    self._check_block(branch.body)
                if statement.else_body is not None:
                    self._check_block(statement.else_body)

    def _check_block(self, statements: list[StmtNode]) -> None:
        enclosing = self.variable_types.copy()
        try:
            self._check_statements(statements)
        finally:
            self.variable_types = enclosing

    def _check_expression_for_type(self, expression: ExprNode, type_name: str) -> None:
        limits = _LIMITS.get(type_name)
        if limits is None:
            return
        self._constant_integer(expression, type_name)

    @staticmethod
    def _validate(value: int, expression: ExprNode, type_name: str) -> int:
        minimum, maximum = _LIMITS[type_name]
        if not minimum <= value <= maximum:
            raise CompilationError(
                expression.line,
                expression.column,
                f"Valor fines {type_name} excedit.",
            )
        return value

    def _constant_integer(self, expression: ExprNode, type_name: str) -> int | None:
        if isinstance(expression, IntegerLiteralNode):
            return self._validate(expression.value, expression, type_name)
        if isinstance(expression, UnaryExprNode):
            # Fold a literal sign before range checking: the absolute value of
            # INT_MIN is not a positive value representable in its signed type.
            if isinstance(expression.operand, IntegerLiteralNode):
                operand = expression.operand.value
            else:
                operand = self._constant_integer(expression.operand, type_name)
            if operand is None:
                return None
            if expression.operator == "+":
                return self._validate(operand, expression, type_name)
            if expression.operator == "-":
                return self._validate(-operand, expression, type_name)
            return None
        if isinstance(expression, BinaryExprNode):
            left = self._constant_integer(expression.left, type_name)
            right = self._constant_integer(expression.right, type_name)
            if left is None or right is None:
                return None
            operator = expression.operator
            if operator in ("+", "adde"):
                return self._validate(left + right, expression, type_name)
            if operator in ("-", "subtrahe"):
                return self._validate(left - right, expression, type_name)
            if operator in ("*", "multiplica"):
                return self._validate(left * right, expression, type_name)
            if operator in ("/", "divide"):
                if right == 0:
                    return None
                quotient = abs(left) // abs(right)
                value = -quotient if (left < 0) != (right < 0) else quotient
                return self._validate(value, expression, type_name)
            if operator in ("%", "diviso integra"):
                if right == 0:
                    return None
                quotient = abs(left) // abs(right)
                if (left < 0) != (right < 0):
                    quotient = -quotient
                return self._validate(left - quotient * right, expression, type_name)
            if operator in ("^", "exponens"):
                if right < 0:
                    return None
                # Bounded exponentiation: never materialize an enormous bigint.
                # Squaring is saturated; the actual result is checked exactly.
                bound = -_LIMITS[type_name][0]
                result, factor, exponent = 1, abs(left), right
                while exponent:
                    if exponent & 1:
                        result *= factor
                        if result > bound:
                            raise CompilationError(
                                expression.line, expression.column,
                                f"Valor fines {type_name} excedit.",
                            )
                    exponent >>= 1
                    if exponent:
                        factor = min(factor * factor, bound + 1)
                if left < 0 and right % 2:
                    result = -result
                return self._validate(result, expression, type_name)
        return None
