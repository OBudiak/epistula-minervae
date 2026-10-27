from __future__ import annotations

from .ast_nodes import (
    AssignmentNode,
    BinaryExprNode,
    BooleanLiteralNode,
    ComparisonExprNode,
    ConstructorArgNode,
    ConstructorNode,
    ElseIfNode,
    ExprStmtNode,
    ExprNode,
    FieldDeclNode,
    FunctionDeclNode,
    IdentifierNode,
    IfNode,
    IntegerLiteralNode,
    CallNode,
    MemberAccessNode,
    NilLiteralNode,
    ParameterNode,
    PrintArgumentNode,
    PrintNode,
    ProgramNode,
    ReadExprNode,
    ReadStmtNode,
    ReturnNode,
    StmtNode,
    StringLiteralNode,
    StructDeclNode,
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
        if self._check(TokenKind.RETURN):
            if top_level:
                token = self._peek()
                raise CompilationError(token.line, token.column,
                                       "Reditus extra edictum est.")
            keyword = self._advance()
            value = self._parse_expression()
            self._expect(TokenKind.BANG, "Signum '!' exspectabatur.")
            self._expect_line_end(allow_eof=False)
            return ReturnNode(keyword.line, keyword.column, value)
        if self._check(TokenKind.IF):
            statement = self._parse_if()
        elif self._check(TokenKind.ANNOUNCE):
            if not top_level:
                token = self._peek()
                raise CompilationError(token.line, token.column,
                                       "Edictum vel structura in summo tantum licet.")
            keyword = self._advance()
            if self._check(TokenKind.STRUCT):
                statement = self._parse_struct(keyword)
            else:
                statement = self._parse_function(keyword)
        elif self._looks_like_alternate_function():
            if not top_level:
                token = self._peek()
                raise CompilationError(token.line, token.column,
                                       "Edictum in summo tantum licet.")
            statement = self._parse_alternate_function()
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
        if self._looks_like_typed_declaration():
            return self._parse_declaration()
        if self._check(TokenKind.IDENTIFIER):
            target = self._parse_postfix()
            if self._match(TokenKind.ASSIGN):
                operator = self._previous()
                value = self._parse_expression()
                if isinstance(target, IdentifierNode):
                    return AssignmentNode(target.line, target.column, target.name,
                                          operator.text, value)
                return AssignmentNode(target.line, target.column, "", operator.text,
                                      value, target)
            if isinstance(target, CallNode):
                return ExprStmtNode(target.line, target.column, target)
            token = self._peek()
            raise CompilationError(token.line, token.column,
                                   "Operator assignationis exspectabatur.")
        if self._check(TokenKind.PRINT):
            return self._parse_print()
        if self._check(TokenKind.READ):
            return self._parse_read_statement()
        token = self._peek()
        raise CompilationError(token.line, token.column, "Sententia exspectabatur.")

    @staticmethod
    def _is_type_kind(kind: TokenKind) -> bool:
        return kind in (TokenKind.TYPE_I32, TokenKind.TYPE_I64,
                        TokenKind.TYPE_INTEGER, TokenKind.TYPE_DUPLEX,
                        TokenKind.TYPE_BOOL, TokenKind.TYPE_TEXT,
                        TokenKind.IDENTIFIER)

    def _parse_type(self, allow_nihil: bool = False) -> Token:
        kinds = (TokenKind.TYPE_I32, TokenKind.TYPE_I64,
                 TokenKind.TYPE_INTEGER, TokenKind.TYPE_DUPLEX,
                 TokenKind.TYPE_BOOL, TokenKind.TYPE_TEXT,
                 TokenKind.IDENTIFIER)
        if allow_nihil:
            kinds += (TokenKind.NIL,)
        token = self._expect_any(kinds, "Typus exspectabatur.")
        text = token.text
        while self._check(TokenKind.DOT) and self._peek(1).kind == TokenKind.IDENTIFIER:
            self._advance()
            text += "." + self._advance().text
        return Token(token.kind, text, token.line, token.column)

    def _looks_like_typed_declaration(self) -> bool:
        if not self._is_type_kind(self._peek().kind):
            return False
        offset = 1
        while self._peek(offset).kind == TokenKind.DOT and self._peek(offset + 1).kind == TokenKind.IDENTIFIER:
            offset += 2
        return self._peek(offset).kind == TokenKind.IDENTIFIER

    def _parse_declaration(self) -> VarDeclNode:
        prefixed = self._check(TokenKind.MUTABLE, TokenKind.IMMUTABLE, TokenKind.ETERNAL)
        keyword = self._advance() if prefixed else self._peek()
        inferred_marker = (prefixed and keyword.kind in (TokenKind.IMMUTABLE, TokenKind.ETERNAL)
                           and self._match(TokenKind.MUTABLE))
        type_token: Token | None = None
        if not prefixed:
            type_token = self._parse_type()
        elif not inferred_marker and (self._peek().kind in (TokenKind.TYPE_I32, TokenKind.TYPE_I64,
                                 TokenKind.TYPE_INTEGER, TokenKind.TYPE_DUPLEX,
                                 TokenKind.TYPE_BOOL, TokenKind.TYPE_TEXT) or (self._peek().kind == TokenKind.IDENTIFIER
                                                       and self._peek(1).kind == TokenKind.IDENTIFIER)):
            type_token = self._parse_type()
        if (prefixed and keyword.kind == TokenKind.MUTABLE and type_token
                and type_token.text not in ("32bitInt", "64bitInt", "sententia")):
            raise CompilationError(type_token.line, type_token.column,
                                   "Variabilis typum ex initio deducit; typus explicitus non licet.")
        name = self._expect(TokenKind.IDENTIFIER, "Nomen variabilis exspectabatur.")
        self._expect(TokenKind.ASSIGN, "Operator assignationis exspectabatur.")
        initializer = self._parse_expression()
        if isinstance(initializer, ConstructorNode) and not initializer.type_name and type_token:
            initializer.type_name = type_token.text
        return VarDeclNode(
            keyword.line,
            keyword.column,
            keyword.text if prefixed else "",
            type_token.text if type_token else None,
            name.text,
            not prefixed or keyword.kind == TokenKind.MUTABLE,
            initializer,
        )

    def _looks_like_alternate_function(self) -> bool:
        if not self._is_type_kind(self._peek().kind):
            return False
        offset = 1
        while self._peek(offset).kind == TokenKind.DOT and self._peek(offset + 1).kind == TokenKind.IDENTIFIER:
            offset += 2
        return (self._peek(offset).kind == TokenKind.IDENTIFIER
                and self._peek(offset + 1).kind == TokenKind.ASSIGN
                and self._peek(offset + 2).kind == TokenKind.ANNOUNCE
                and self._peek(offset + 3).kind == TokenKind.EDICT)

    def _parse_alternate_function(self) -> FunctionDeclNode:
        result = self._parse_type(allow_nihil=True)
        name = self._expect(TokenKind.IDENTIFIER, "Nomen edicti exspectabatur.")
        self._expect(TokenKind.ASSIGN, "Operator assignationis exspectabatur.")
        self._expect(TokenKind.ANNOUNCE, "'nuntia' exspectabatur.")
        self._expect(TokenKind.EDICT, "'edictum' exspectabatur.")
        parameters = self._parse_parameters()
        body = self._parse_function_body()
        return FunctionDeclNode(result.line, result.column, name.text,
                                parameters, result.text, body, True)

    def _parse_function(self, keyword: Token, owner: str | None = None) -> FunctionDeclNode:
        self._expect(TokenKind.EDICT, "'edictum' exspectabatur.")
        name = self._expect(TokenKind.IDENTIFIER, "Nomen edicti exspectabatur.")
        parameters = self._parse_parameters()
        constructor = not self._match(TokenKind.RESULT)
        if constructor:
            if owner is None or name.text != owner:
                token = self._peek()
                raise CompilationError(token.line, token.column, "'remitteque' exspectabatur.")
            result = Token(TokenKind.NIL, "nihil", name.line, name.column)
        else:
            result = self._parse_type(allow_nihil=True)
        body = self._parse_function_body()
        return FunctionDeclNode(keyword.line, keyword.column, name.text,
                                parameters, result.text, body, constructor=constructor)

    def _parse_parameters(self) -> list[ParameterNode]:
        self._expect(TokenKind.QUO, "'quo' exspectabatur.")
        self._expect(TokenKind.CAPE, "'cape' exspectabatur.")
        if self._match(TokenKind.NIL):
            return []
        parameters: list[ParameterNode] = []
        while True:
            type_token = self._parse_type()
            name = self._expect(TokenKind.IDENTIFIER, "Nomen parametri exspectabatur.")
            parameters.append(ParameterNode(type_token.line, type_token.column,
                                            type_token.text, name.text))
            if not self._match(TokenKind.COMMA):
                break
        return parameters

    def _parse_function_body(self) -> list[StmtNode]:
        self._expect(TokenKind.BLOCK_OPEN, "Initium clausulae '<<' exspectabatur.")
        if self._match(TokenKind.BLOCK_CLOSE):
            return []
        self._require_newline()
        self._skip_newlines()
        if self._match(TokenKind.BLOCK_CLOSE):
            return []
        body = self._parse_block_body()
        self._expect(TokenKind.BLOCK_CLOSE, "Finis clausulae '>>' exspectabatur.")
        return body

    def _parse_struct(self, keyword: Token, short_name: Token | None = None) -> StructDeclNode:
        if short_name is None:
            self._expect(TokenKind.STRUCT, "'structuram' exspectabatur.")
            immutable = self._match(TokenKind.IMMUTABLE_TYPE)
            name = self._expect(TokenKind.IDENTIFIER, "Nomen structurae exspectabatur.")
        else:
            immutable, name = False, short_name
        self._match(TokenKind.QUO)
        self._expect(TokenKind.BLOCK_OPEN, "Initium clausulae '<<' exspectabatur.")
        fields: list[FieldDeclNode] = []
        methods: list[FunctionDeclNode] = []
        nested: list[StructDeclNode] = []
        self._skip_newlines()
        while not self._check(TokenKind.BLOCK_CLOSE, TokenKind.EOF):
            if self._match(TokenKind.ANNOUNCE):
                opening = self._previous()
                if self._check(TokenKind.STRUCT):
                    nested.append(self._parse_struct(opening))
                    self._expect(TokenKind.DOT, "Punctum exspectabatur.")
                    self._skip_newlines()
                    continue
                methods.append(self._parse_function(opening, owner=name.text))
            elif self._check(TokenKind.IDENTIFIER) and self._peek(1).kind == TokenKind.BLOCK_OPEN:
                opening = self._advance()
                nested.append(self._parse_struct(opening, short_name=opening))
                self._expect(TokenKind.DOT, "Punctum exspectabatur.")
                self._skip_newlines()
                continue
            elif self._check(TokenKind.FIELD_MUTABLE, TokenKind.IMMUTABLE, TokenKind.ETERNAL):
                fields.append(self._parse_field())
            else:
                token = self._peek()
                raise CompilationError(token.line, token.column,
                                       "Campus aut edictum exspectabatur.")
            self._expect(TokenKind.SEMICOLON, "Semicolon exspectabatur.")
            self._skip_newlines()
        self._expect(TokenKind.BLOCK_CLOSE, "Finis clausulae '>>' exspectabatur.")
        return StructDeclNode(keyword.line, keyword.column, name.text,
                              immutable, fields, methods, nested)

    def _parse_field(self) -> FieldDeclNode:
        keyword = self._advance()
        inferred = self._match(TokenKind.MUTABLE)
        type_token = None if inferred else self._parse_type()
        name = self._expect(TokenKind.IDENTIFIER, "Nomen campi exspectabatur.")
        initializer = self._parse_expression() if self._match(TokenKind.ASSIGN) else None
        return FieldDeclNode(keyword.line, keyword.column, keyword.text,
                             type_token.text if type_token else None, name.text,
                             keyword.kind == TokenKind.FIELD_MUTABLE, initializer)

    def _parse_print(self) -> PrintNode:
        keyword = self._advance()
        if self._check(TokenKind.DOT, TokenKind.SEMICOLON, TokenKind.NEWLINE, TokenKind.EOF):
            token = self._peek()
            raise CompilationError(token.line, token.column, "Argumentum Scribe exspectabatur.")
        arguments = [self._parse_print_argument(first=True)]
        while self._match(TokenKind.COMMA):
            arguments.append(self._parse_print_argument(first=False))
        return PrintNode(keyword.line, keyword.column, arguments)

    def _parse_print_argument(self, first: bool) -> PrintArgumentNode:
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
        value = self._parse_print_expression(require_marker=first)
        return PrintArgumentNode(value.line, value.column, False, value)

    def _parse_print_expression(self, require_marker: bool) -> ExprNode:
        # The first bare string is quoted explicitly; later bare strings are
        # regular print arguments. Parentheses never bypass the first marker.
        parenthesized = self._check(TokenKind.LPAREN)
        value = self._parse_expression()
        if isinstance(value, StringLiteralNode) and (require_marker or parenthesized):
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
        expression = self._parse_postfix()
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
        return self._parse_postfix()

    def _parse_postfix(self) -> ExprNode:
        expression = self._parse_primary()
        while True:
            if self._check(TokenKind.DOT, TokenKind.MEMBER) and self._peek(1).kind == TokenKind.IDENTIFIER:
                separator = self._advance()
                name = self._advance()
                expression = MemberAccessNode(separator.line, separator.column,
                                              expression, name.text, separator.text)
            elif self._match(TokenKind.LPAREN):
                opening = self._previous()
                args = self._parse_call_arguments(parenthesized=True)
                expression = CallNode(opening.line, opening.column, expression,
                                      args, "parentheses")
            elif self._match(TokenKind.QUO):
                opening = self._previous()
                self._expect(TokenKind.CAPE, "'cape' exspectabatur.")
                args = self._parse_call_arguments(parenthesized=False)
                expression = CallNode(opening.line, opening.column, expression,
                                      args, "quo cape")
            elif self._match(TokenKind.CAPE):
                if not isinstance(expression, IdentifierNode):
                    token = self._previous()
                    raise CompilationError(token.line, token.column,
                                           "Nomen structurae exspectabatur.")
                expression = self._parse_constructor(expression)
            else:
                break
        return expression

    def _parse_call_arguments(self, parenthesized: bool) -> list[ExprNode]:
        if parenthesized and self._match(TokenKind.RPAREN):
            return []
        if self._match(TokenKind.NIL):
            if parenthesized:
                self._expect(TokenKind.RPAREN, "Clausula ')' exspectabatur.")
            return []
        arguments = [self._parse_expression()]
        while self._match(TokenKind.COMMA):
            arguments.append(self._parse_expression())
        if parenthesized:
            self._expect(TokenKind.RPAREN, "Clausula ')' exspectabatur.")
        return arguments

    def _parse_constructor(self, name: IdentifierNode) -> ConstructorNode:
        arguments: list[ConstructorArgNode] = []
        if self._match(TokenKind.NIL):
            return ConstructorNode(name.line, name.column, name.name, arguments)
        while True:
            field_name: str | None = None
            argument_line, argument_column = self._peek().line, self._peek().column
            if self._check(TokenKind.IDENTIFIER) and self._peek(1).kind == TokenKind.ASSIGN:
                field_name = self._advance().text
                self._advance()
            value = self._parse_expression()
            arguments.append(ConstructorArgNode(argument_line, argument_column,
                                                field_name, value))
            if not self._match(TokenKind.COMMA):
                break
        return ConstructorNode(name.line, name.column, name.name, arguments)

    def _parse_primary(self) -> ExprNode:
        if self._match(TokenKind.NEW):
            opening = self._previous()
            type_name = ""
            offset = 1
            while self._peek(offset).kind == TokenKind.DOT and self._peek(offset + 1).kind == TokenKind.IDENTIFIER:
                offset += 2
            if self._check(TokenKind.IDENTIFIER) and self._peek(offset).kind == TokenKind.QUO:
                type_name = self._parse_type().text
                self._expect(TokenKind.QUO, "'quo' exspectabatur.")
                self._expect(TokenKind.CAPE, "'cape' exspectabatur.")
            node = self._parse_constructor(
                IdentifierNode(opening.line, opening.column, type_name))
            node.syntax = "novum"
            return node
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
