from __future__ import annotations

from .ast_nodes import (
    AssignmentNode,
    BinaryExprNode,
    BooleanLiteralNode,
    ComparisonExprNode,
    ElseIfNode,
    ExprNode,
    IdentifierNode,
    IfNode,
    IntegerLiteralNode,
    NilLiteralNode,
    PrintArgumentNode,
    PrintNode,
    ProgramNode,
    ReadExprNode,
    ReadStmtNode,
    StmtNode,
    StringLiteralNode,
    UnaryExprNode,
    VarDeclNode,
)
from .errors import CompilationError
from .lexer import Lexer
from .tokens import Token, TokenKind


class Parser:
    """One-function-per-rule recursive-descent parser."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse_program(self) -> ProgramNode:
        start = self._peek()
        statements: list[StmtNode] = []
        self._skip_newlines()
        while not self._check(TokenKind.EOF):
            statements.append(self._parse_statement(top_level=True))
            self._skip_newlines()
        return ProgramNode(start.line, start.column, statements)

    def _parse_statement(self, top_level: bool) -> StmtNode:
        if self._check(TokenKind.IF):
            statement = self._parse_if()
        else:
            statement = self._parse_simple_statement()

        terminator = TokenKind.DOT if top_level else TokenKind.SEMICOLON
        message = "Punctum exspectabatur." if top_level else "Semicolon exspectabatur."
        self._expect(terminator, message)
        self._expect_line_end(allow_eof=top_level)
        return statement

    def _parse_simple_statement(self) -> StmtNode:
        if self._check(TokenKind.MUTABLE, TokenKind.IMMUTABLE, TokenKind.ETERNAL):
            return self._parse_declaration()
        if self._check(TokenKind.IDENTIFIER):
            return self._parse_assignment()
        if self._check(TokenKind.PRINT):
            return self._parse_print()
        if self._check(TokenKind.READ):
            return self._parse_read_statement()
        token = self._peek()
        raise CompilationError(token.line, token.column, "Sententia exspectabatur.")

    def _parse_declaration(self) -> VarDeclNode:
        keyword = self._advance()
        type_token = self._expect_any(
            (TokenKind.TYPE_I32, TokenKind.TYPE_I64, TokenKind.TYPE_BOOL),
            "Typus exspectabatur.",
        )
        name = self._expect(TokenKind.IDENTIFIER, "Nomen variabilis exspectabatur.")
        self._expect(TokenKind.ASSIGN, "Operator assignationis exspectabatur.")
        initializer = self._parse_expression()
        return VarDeclNode(
            keyword.line,
            keyword.column,
            keyword.text,
            type_token.text,
            name.text,
            keyword.kind == TokenKind.MUTABLE,
            initializer,
        )

    def _parse_assignment(self) -> AssignmentNode:
        name = self._advance()
        operator = self._expect(TokenKind.ASSIGN, "Operator assignationis exspectabatur.")
        value = self._parse_expression()
        return AssignmentNode(name.line, name.column, name.text, operator.text, value)

    def _parse_print(self) -> PrintNode:
        keyword = self._advance()
        if self._check(TokenKind.DOT, TokenKind.SEMICOLON, TokenKind.NEWLINE, TokenKind.EOF):
            token = self._peek()
            raise CompilationError(token.line, token.column, "Argumentum Scribe exspectabatur.")
        arguments = [self._parse_print_argument()]
        while self._match(TokenKind.COMMA):
            arguments.append(self._parse_print_argument())
        return PrintNode(keyword.line, keyword.column, arguments)

    def _parse_print_argument(self) -> PrintArgumentNode:
        if (
            self._check(TokenKind.MINUS)
            and self._peek(1).kind == TokenKind.STRING
            and self._peek(2).kind in (
                TokenKind.COMMA, TokenKind.DOT, TokenKind.SEMICOLON,
                TokenKind.NEWLINE, TokenKind.EOF,
            )
        ):
            marker = self._advance()
            value = self._parse_primary()
            return PrintArgumentNode(marker.line, marker.column, True, value)
        value = self._parse_print_expression()
        return PrintArgumentNode(value.line, value.column, False, value)

    def _parse_print_expression(self) -> ExprNode:
        # The print-* EBNF rules partition expressions by their root shape.
        # Reuse the precedence parser, then exclude the bare-string partition.
        value = self._parse_expression()
        if isinstance(value, StringLiteralNode):
            raise CompilationError(
                value.line,
                value.column,
                "Signum citationis '-' exspectabatur.",
            )
        return value

    def _parse_read_statement(self) -> ReadStmtNode:
        keyword = self._advance()
        target: str | None = None
        if self._match(TokenKind.IN):
            name = self._expect(TokenKind.IDENTIFIER, "Nomen post 'in' exspectabatur.")
            target = name.text
        return ReadStmtNode(keyword.line, keyword.column, target)

    def _parse_if(self) -> IfNode:
        keyword = self._expect(TokenKind.IF, "'provisum' exspectabatur.")
        condition = self._parse_expression()
        self._expect(TokenKind.BLOCK_OPEN, "Initium clausulae '<<' exspectabatur.")
        self._require_newline()
        then_body = self._parse_block_body()
        self._expect(TokenKind.BLOCK_CLOSE, "Finis clausulae '>>' exspectabatur.")

        else_if_branches: list[ElseIfNode] = []
        else_body: list[StmtNode] | None = None
        while self._match(TokenKind.COMMA):
            self._require_newline()
            self._skip_newlines()
            else_token = self._expect(TokenKind.ELSE, "'aliter' post comma exspectabatur.")
            if self._match(TokenKind.IF):
                if else_body is not None:
                    raise CompilationError(else_token.line, else_token.column, "'aliter' ultimum esse debet.")
                branch_condition = self._parse_expression()
                self._expect(TokenKind.BLOCK_OPEN, "Initium clausulae '<<' exspectabatur.")
                self._require_newline()
                body = self._parse_block_body()
                self._expect(TokenKind.BLOCK_CLOSE, "Finis clausulae '>>' exspectabatur.")
                else_if_branches.append(
                    ElseIfNode(else_token.line, else_token.column, branch_condition, body)
                )
                continue
            self._expect(TokenKind.BLOCK_OPEN, "Initium clausulae '<<' exspectabatur.")
            self._require_newline()
            else_body = self._parse_block_body()
            self._expect(TokenKind.BLOCK_CLOSE, "Finis clausulae '>>' exspectabatur.")
            if self._check(TokenKind.COMMA):
                token = self._peek()
                raise CompilationError(token.line, token.column, "'aliter' ultimum esse debet.")
            break

        return IfNode(
            keyword.line,
            keyword.column,
            condition,
            then_body,
            else_if_branches,
            else_body,
        )

    def _parse_block_body(self) -> list[StmtNode]:
        self._skip_newlines()
        if self._check(TokenKind.BLOCK_CLOSE):
            token = self._peek()
            raise CompilationError(token.line, token.column, "Clausula vacua esse non potest.")
        statements: list[StmtNode] = []
        while not self._check(TokenKind.BLOCK_CLOSE, TokenKind.EOF):
            statements.append(self._parse_statement(top_level=False))
            self._skip_newlines()
        if self._check(TokenKind.EOF):
            token = self._peek()
            raise CompilationError(token.line, token.column, "Finis clausulae '>>' exspectabatur.")
        return statements

    def _parse_expression(self) -> ExprNode:
        return self._parse_comparison()

    def _parse_comparison(self) -> ExprNode:
        left = self._parse_additive()
        operator: Token | None = None
        operator_text = ""
        if self._match(TokenKind.EQ, TokenKind.NE, TokenKind.IDEM):
            operator = self._previous()
            operator_text = operator.text
        elif self._match(TokenKind.NON):
            operator = self._previous()
            self._expect(TokenKind.IDEM, "'idem' post 'non' exspectabatur.")
            operator_text = "non idem"
        if operator is None:
            return left
        right = self._parse_additive()
        if self._check(TokenKind.EQ, TokenKind.NE, TokenKind.IDEM, TokenKind.NON):
            token = self._peek()
            raise CompilationError(token.line, token.column, "Comparatio concatenata vetita est.")
        return ComparisonExprNode(operator.line, operator.column, operator_text, left, right)

    def _parse_additive(self) -> ExprNode:
        expression = self._parse_multiplicative()
        while self._match(
            TokenKind.PLUS,
            TokenKind.MINUS,
            TokenKind.ADD_WORD,
            TokenKind.SUB_WORD,
        ):
            operator = self._previous()
            right = self._parse_multiplicative()
            expression = BinaryExprNode(
                operator.line, operator.column, operator.text, expression, right
            )
        return expression

    def _parse_multiplicative(self) -> ExprNode:
        expression = self._parse_unary()
        while self._match(
            TokenKind.STAR,
            TokenKind.SLASH,
            TokenKind.PERCENT,
            TokenKind.MUL_WORD,
            TokenKind.DIV_WORD,
            TokenKind.MOD_WORD,
        ):
            operator = self._previous()
            operator_text = operator.text
            if operator.kind == TokenKind.MOD_WORD:
                self._expect(TokenKind.INTEGRA, "'integra' post 'diviso' exspectabatur.")
                operator_text = "diviso integra"
            right = self._parse_unary()
            expression = BinaryExprNode(
                operator.line, operator.column, operator_text, expression, right
            )
        return expression

    def _parse_unary(self) -> ExprNode:
        if self._match(TokenKind.PLUS, TokenKind.MINUS):
            operator = self._previous()
            operand = self._parse_unary()
            return UnaryExprNode(operator.line, operator.column, operator.text, operand)
        return self._parse_power()

    def _parse_power(self) -> ExprNode:
        expression = self._parse_primary()
        while self._match(TokenKind.CARET, TokenKind.POW_WORD):
            operator = self._previous()
            right = self._parse_power_operand()
            expression = BinaryExprNode(
                operator.line, operator.column, operator.text, expression, right
            )
        return expression

    def _parse_power_operand(self) -> ExprNode:
        if self._match(TokenKind.PLUS, TokenKind.MINUS):
            operator = self._previous()
            return UnaryExprNode(
                operator.line, operator.column, operator.text,
                self._parse_power_operand(),
            )
        return self._parse_primary()

    def _parse_primary(self) -> ExprNode:
        if self._match(TokenKind.INTEGER):
            token = self._previous()
            value = 0
            for character in token.text:
                value = value * 10 + ord(character) - ord("0")
            return IntegerLiteralNode(
                token.line, token.column, token.text, value, "decimal"
            )
        if self._match(TokenKind.ROMAN_INTEGER):
            token = self._previous()
            return IntegerLiteralNode(
                token.line,
                token.column,
                token.text,
                Lexer.roman_value(token.text),
                "roman",
            )
        if self._match(TokenKind.TRUE, TokenKind.FALSE):
            token = self._previous()
            return BooleanLiteralNode(
                token.line, token.column, token.kind == TokenKind.TRUE
            )
        if self._match(TokenKind.NIL):
            token = self._previous()
            return NilLiteralNode(token.line, token.column)
        if self._match(TokenKind.STRING):
            token = self._previous()
            value = self._decode_string(token.text)
            return StringLiteralNode(token.line, token.column, value)
        if self._match(TokenKind.IDENTIFIER):
            token = self._previous()
            return IdentifierNode(token.line, token.column, token.text)
        if self._match(TokenKind.READ):
            token = self._previous()
            return ReadExprNode(token.line, token.column)
        if self._match(TokenKind.LPAREN):
            expression = self._parse_expression()
            self._expect(TokenKind.RPAREN, "Clausula ')' exspectabatur.")
            return expression
        token = self._peek()
        raise CompilationError(token.line, token.column, "Expressio exspectabatur.")

    @staticmethod
    def _decode_string(text: str) -> str:
        content = text[1:-1].replace("\r\n", "\n").replace("\r", "\n")
        if content == "nihil":
            return ""
        result = ""
        index = 0
        while index < len(content):
            if content.startswith("/linea", index):
                result += "\n"
                index += len("/linea")
            elif content.startswith("//", index):
                result += "/"
                index += 2
            else:
                result += content[index]
                index += 1
        return result

    def _expect_line_end(self, allow_eof: bool) -> None:
        if self._match(TokenKind.NEWLINE):
            return
        if allow_eof and self._check(TokenKind.EOF):
            return
        token = self._peek()
        raise CompilationError(token.line, token.column, "Nova linea exspectabatur.")

    def _require_newline(self) -> None:
        self._expect(TokenKind.NEWLINE, "Nova linea exspectabatur.")

    def _skip_newlines(self) -> None:
        while self._match(TokenKind.NEWLINE):
            pass

    def _match(self, *kinds: TokenKind) -> bool:
        if self._check(*kinds):
            self._advance()
            return True
        return False

    def _expect(self, kind: TokenKind, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        token = self._peek()
        raise CompilationError(token.line, token.column, message)

    def _expect_any(self, kinds: tuple[TokenKind, ...], message: str) -> Token:
        if self._check(*kinds):
            return self._advance()
        token = self._peek()
        raise CompilationError(token.line, token.column, message)

    def _check(self, *kinds: TokenKind) -> bool:
        return self._peek().kind in kinds

    def _advance(self) -> Token:
        token = self._peek()
        if token.kind != TokenKind.EOF:
            self.index += 1
        return token

    def _peek(self, offset: int = 0) -> Token:
        target = self.index + offset
        if target >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[target]

    def _previous(self) -> Token:
        return self.tokens[self.index - 1]
