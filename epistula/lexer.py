from __future__ import annotations

from .errors import CompilationError
from .tokens import Token, TokenKind


_KEYWORDS = {
    "sententia": TokenKind.TYPE_BOOL,
    "Veritas": TokenKind.TRUE,
    "Falsus": TokenKind.FALSE,
    "nihil": TokenKind.NIL,
    "variabilis": TokenKind.MUTABLE,
    "immutabilis": TokenKind.IMMUTABLE,
    "inaeternum": TokenKind.ETERNAL,
    "provisum": TokenKind.IF,
    "aliter": TokenKind.ELSE,
    "Scribe": TokenKind.PRINT,
    "Legere": TokenKind.READ,
    "in": TokenKind.IN,
    "aequalis": TokenKind.ASSIGN,
    "idem": TokenKind.IDEM,
    "non": TokenKind.NON,
    "adde": TokenKind.ADD_WORD,
    "subtrahe": TokenKind.SUB_WORD,
    "multiplica": TokenKind.MUL_WORD,
    "divide": TokenKind.DIV_WORD,
    "diviso": TokenKind.MOD_WORD,
    "integra": TokenKind.INTEGRA,
    "exponens": TokenKind.POW_WORD,
}


class Lexer:
    """Hand-written state-machine lexer operating directly on UTF-8 bytes."""

    def __init__(self, source: bytes) -> None:
        self.source = source
        self.index = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def scan(self) -> list[Token]:
        while not self._at_end():
            current = self._peek()

            if current in (0x20, 0x09, 0x0D):
                self._advance()
                continue
            if current == 0x0A:
                self._emit_single(TokenKind.NEWLINE)
                continue

            if self._starts(b"(N.B."):
                self._block_comment()
                continue
            if self._starts(b"N.B."):
                self._line_comment()
                continue

            if self._match_fixed_word(b"32bitInt"):
                self._emit_fixed(TokenKind.TYPE_I32, len(b"32bitInt"))
                continue
            if self._match_fixed_word(b"64bitInt"):
                self._emit_fixed(TokenKind.TYPE_I64, len(b"64bitInt"))
                continue

            if self._is_digit(current):
                self._decimal_integer()
                continue
            if self._is_letter(current):
                self._word_or_identifier()
                continue
            if current == 0x22:
                self._string()
                continue

            if self._starts("⬅".encode("utf-8")):
                self._emit_fixed(TokenKind.ASSIGN, len("⬅".encode("utf-8")))
                continue
            if self._starts(b"<-"):
                self._emit_fixed(TokenKind.ASSIGN, 2)
                continue
            if self._starts(b"<<"):
                self._emit_fixed(TokenKind.BLOCK_OPEN, 2)
                continue
            if self._starts(b">>"):
                self._emit_fixed(TokenKind.BLOCK_CLOSE, 2)
                continue
            if self._starts(b"o-o") and self._boundary_after(3):
                self._emit_fixed(TokenKind.EQ, 3)
                continue
            if self._starts(b"oxo") and self._boundary_after(3):
                self._emit_fixed(TokenKind.NE, 3)
                continue

            one_byte = {
                0x2B: TokenKind.PLUS,
                0x2D: TokenKind.MINUS,
                0x2A: TokenKind.STAR,
                0x2F: TokenKind.SLASH,
                0x25: TokenKind.PERCENT,
                0x5E: TokenKind.CARET,
                0x28: TokenKind.LPAREN,
                0x29: TokenKind.RPAREN,
                0x2E: TokenKind.DOT,
                0x3B: TokenKind.SEMICOLON,
                0x2C: TokenKind.COMMA,
            }
            kind = one_byte.get(current)
            if kind is not None:
                self._emit_single(kind)
                continue

            raise CompilationError(
                self.line,
                self.column,
                "Character ignotum inventum est.",
            )

        self.tokens.append(Token(TokenKind.EOF, "", self.line, self.column))
        return self.tokens

    def _decimal_integer(self) -> None:
        start = self.index
        line, column = self.line, self.column
        while not self._at_end() and self._is_digit(self._peek()):
            self._advance()
        if not self._at_end() and self._is_identifier_continue(self._peek()):
            while not self._at_end() and self._is_identifier_continue(self._peek()):
                self._advance()
            raise CompilationError(
                line,
                column,
                "Numerus Arabico Romanoque mixtus est.",
            )
        self._append(TokenKind.INTEGER, start, line, column)

    def _word_or_identifier(self) -> None:
        start = self.index
        line, column = self.line, self.column
        while not self._at_end() and self._is_identifier_continue(self._peek()):
            self._advance()
        text = self.source[start:self.index].decode("ascii")

        kind = _KEYWORDS.get(text)
        if kind is not None:
            self.tokens.append(Token(kind, text, line, column))
            return
        if text == "o-o":
            self.tokens.append(Token(TokenKind.EQ, text, line, column))
            return
        if text == "oxo":
            self.tokens.append(Token(TokenKind.NE, text, line, column))
            return
        if self._only_roman_symbols(text):
            if not self._valid_roman(text):
                raise CompilationError(line, column, "Numerus Romanus invalidus est.")
            self.tokens.append(Token(TokenKind.ROMAN_INTEGER, text, line, column))
            return
        self.tokens.append(Token(TokenKind.IDENTIFIER, text, line, column))

    def _string(self) -> None:
        start = self.index
        line, column = self.line, self.column
        self._advance()
        while not self._at_end():
            if self._peek() == 0x22:
                self._advance()
                raw = self.source[start:self.index]
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CompilationError(line, column, "Catena UTF-8 invalida est.") from exc
                self.tokens.append(Token(TokenKind.STRING, text, line, column))
                return
            if self._peek() == 0x2F:
                if self._starts(b"/linea"):
                    self._advance_many(len(b"/linea"))
                    continue
                if self._starts(b"//"):
                    self._advance_many(2)
                    continue
                raise CompilationError(
                    self.line,
                    self.column,
                    "Series effugiens invalida est.",
                )
            self._advance()
        raise CompilationError(line, column, "Catena non clausa est.")

    def _line_comment(self) -> None:
        self._advance_many(4)
        while not self._at_end() and self._peek() != 0x0A:
            self._advance()

    def _block_comment(self) -> None:
        line, column = self.line, self.column
        self._advance_many(5)
        while not self._at_end():
            if self._peek() == 0x29:
                self._advance()
                return
            self._advance()
        raise CompilationError(line, column, "Commentarium non clausum est.")

    def _emit_single(self, kind: TokenKind) -> None:
        line, column = self.line, self.column
        start = self.index
        self._advance()
        self._append(kind, start, line, column)

    def _emit_fixed(self, kind: TokenKind, length: int) -> None:
        line, column = self.line, self.column
        start = self.index
        self._advance_many(length)
        self._append(kind, start, line, column)

    def _append(self, kind: TokenKind, start: int, line: int, column: int) -> None:
        raw = self.source[start:self.index]
        self.tokens.append(Token(kind, raw.decode("utf-8"), line, column))

    def _advance_many(self, count: int) -> None:
        for _ in range(count):
            self._advance()

    def _advance(self) -> int:
        value = self.source[self.index]
        self.index += 1
        if value == 0x0A:
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return value

    def _peek(self) -> int:
        return self.source[self.index]

    def _at_end(self) -> bool:
        return self.index >= len(self.source)

    def _starts(self, value: bytes) -> bool:
        end = self.index + len(value)
        return self.source[self.index:end] == value

    def _match_fixed_word(self, value: bytes) -> bool:
        return self._starts(value) and self._boundary_after(len(value))

    def _boundary_after(self, length: int) -> bool:
        target = self.index + length
        return target >= len(self.source) or not self._is_identifier_continue(self.source[target])

    @staticmethod
    def _is_digit(value: int) -> bool:
        return 0x30 <= value <= 0x39

    @staticmethod
    def _is_letter(value: int) -> bool:
        return 0x41 <= value <= 0x5A or 0x61 <= value <= 0x7A

    @classmethod
    def _is_identifier_continue(cls, value: int) -> bool:
        return cls._is_letter(value) or cls._is_digit(value) or value in (0x5F, 0x2D)

    @staticmethod
    def _only_roman_symbols(text: str) -> bool:
        if not text:
            return False
        for character in text:
            if character not in "IVXLCDM":
                return False
        return True

    @classmethod
    def _valid_roman(cls, text: str) -> bool:
        value = cls.roman_value(text)
        return 1 <= value <= 3999 and cls.roman_text(value) == text

    @staticmethod
    def roman_value(text: str) -> int:
        values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        total = 0
        previous = 0
        for character in reversed(text):
            value = values[character]
            if value < previous:
                total -= value
            else:
                total += value
                previous = value
        return total

    @staticmethod
    def roman_text(value: int) -> str:
        pairs = (
            (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
            (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
            (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
        )
        result = ""
        remaining = value
        for amount, symbols in pairs:
            while remaining >= amount:
                result += symbols
                remaining -= amount
        return result
