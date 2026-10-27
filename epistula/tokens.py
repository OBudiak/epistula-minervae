from dataclasses import dataclass
from enum import Enum


class TokenKind(Enum):
    EOF = "EOF"
    NEWLINE = "NEWLINE"
    IDENTIFIER = "IDENTIFIER"
    INTEGER = "INTEGER"
    ROMAN_INTEGER = "ROMAN_INTEGER"
    STRING = "STRING"

    TYPE_I32 = "32bitInt"
    TYPE_I64 = "64bitInt"
    TYPE_INTEGER = "integer"
    TYPE_DUPLEX = "duplex"
    TYPE_BOOL = "ludicium"
    TYPE_TEXT = "sententia"
    TRUE = "Veritas"
    FALSE = "Falsus"
    NIL = "nihil"

    MUTABLE = "variabilis"
    FIELD_MUTABLE = "mutabilis"
    IMMUTABLE = "immutabilis"
    ETERNAL = "inaeternum"
    IF = "provisum"
    ELSE = "aliter"
    PRINT = "Scribe"
    READ = "Legere"
    IN = "in"
    ANNOUNCE = "nuntia"
    EDICT = "edictum"
    STRUCT = "structuram"
    IMMUTABLE_TYPE = "immutabilem"
    QUO = "quo"
    CAPE = "cape"
    RESULT = "remitteque"
    RETURN = "reditus"
    NEW = "novum"

    ASSIGN = "assignment"
    EQ = "equality"
    NE = "inequality"
    NON = "non"
    IDEM = "idem"

    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    CARET = "^"
    ADD_WORD = "adde"
    SUB_WORD = "subtrahe"
    MUL_WORD = "multiplica"
    DIV_WORD = "divide"
    MOD_WORD = "diviso"
    INTEGRA = "integra"
    POW_WORD = "exponens"

    LPAREN = "("
    RPAREN = ")"
    BLOCK_OPEN = "<<"
    BLOCK_CLOSE = ">>"
    DOT = "."
    SEMICOLON = ";"
    COMMA = ","
    MEMBER = ">"
    BANG = "!"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int

    @property
    def position(self) -> str:
        return f"{self.line}:{self.column}"

