"""Checked console input helpers built with LLVM IRBuilder.

Explicit integer input reads one whitespace-delimited token. Text and inferred
input read one complete line. All buffers live until process exit, so returned
text remains valid when assigned, returned, or stored in a structure.
"""

from llvmlite import ir

from .semantics import I32, I64, INPUT, TEXT


class InputRuntime:
    def __init__(self, generator):
        self.g = generator
        self.parse_function = None
        self.line_function = None
        g = self.g
        self.getchar = self.external("getchar", g.i32, [])
        self.malloc = self.external("malloc", g.i8p, [g.i64])
        self.realloc = self.external("realloc", g.i8p, [g.i8p, g.i64])
        self.write = self.external("write", g.i64, [g.i32, g.i8p, g.i64])
        self.exit = self.external("exit", ir.VoidType(), [g.i32])
        self.fflush = self.external("fflush", g.i32, [g.i8p])
        self.strlen = self.external("strlen", g.i64, [g.i8p])
        self.strncmp = self.external("strncmp", g.i32, [g.i8p, g.i8p, g.i64])

    def external(self, name, result, args):
        return ir.Function(self.g.module, ir.FunctionType(result, args), name=name)

    def constant(self, value, width=64):
        return ir.Constant(ir.IntType(width), value)

    def guard(self, condition, message):
        g, b = self.g, self.g.builder
        good = b.function.append_basic_block("input_ok")
        bad = b.function.append_basic_block("input_error")
        b.cbranch(condition, good, bad)
        b.position_at_end(bad)
        text = "runtime error: " + message + "\n"
        b.call(self.write, [self.constant(2, 32), g._string_pointer(text),
                            self.constant(len(text.encode("utf-8")))])
        b.call(self.exit, [self.constant(1, 32)])
        b.unreachable()
        b.position_at_end(good)

    def box(self, value, type_name, text=None):
        g, b = self.g, self.g.builder
        result = ir.Constant(g.input_type, None)
        numeric = type_name != TEXT
        number = (g._cast(value, type_name, I64) if numeric else self.constant(0))
        result = b.insert_value(result, self.constant(int(numeric), 1), 0)
        result = b.insert_value(result, number, 1)
        return b.insert_value(result, text if text is not None else
                              (value if type_name == TEXT else ir.Constant(g.i8p, None)), 2)

    def convert(self, value, expected):
        g, b = self.g, self.g.builder
        if expected == TEXT:
            text = b.extract_value(value, 2)
            self.guard(b.icmp_unsigned("!=", text, ir.Constant(g.i8p, None)),
                       "input has no text representation")
            return text
        self.guard(b.extract_value(value, 0), "integer input required")
        number = b.extract_value(value, 1)
        return g._cast(number, I64, expected)

    def read(self, type_name):
        g, b = self.g, self.g.builder
        b.call(self.fflush, [ir.Constant(g.i8p, None)])
        if type_name in (I32, I64):
            # POSIX scanf's allocation modifier avoids a fixed input-buffer limit.
            slot = b.alloca(g.i8p)
            b.store(ir.Constant(g.i8p, None), slot)
            count = b.call(g.scanf, [g._string_pointer("%ms"), slot])
            self.guard(b.icmp_signed("==", count, self.constant(1, 32)),
                       "integer input required (end of input)")
            text = b.load(slot)
            delimiter = b.call(self.getchar, [])
            cr = b.function.append_basic_block("input_cr")
            ready = b.function.append_basic_block("input_token_ready")
            b.cbranch(b.icmp_signed("==", delimiter, self.constant(13, 32)), cr, ready)
            b.position_at_end(cr)
            b.call(self.getchar, [])
            b.branch(ready)
            b.position_at_end(ready)
        else:
            text = b.call(self._line_helper(), [])
        if type_name == TEXT:
            return text
        number = b.alloca(g.i64)
        b.store(self.constant(0), number)
        status = b.call(self._integer_helper(), [text, number])
        if type_name in (I32, I64):
            self.guard(b.icmp_signed("!=", status, self.constant(2, 32)),
                       "integer input is outside the 64-bit range")
            self.guard(b.icmp_signed("==", status, self.constant(1, 32)),
                       "invalid integer input (use decimal or canonical Roman notation)")
            value = b.load(number)
            if type_name == I32:
                self.guard(b.and_(b.icmp_signed(">=", value, self.constant(-(2**31))),
                                  b.icmp_signed("<=", value, self.constant(2**31 - 1))),
                           "integer input is outside the 32-bit range")
            return g._cast(value, I64, type_name)
        self.guard(b.icmp_signed("!=", status, self.constant(2, 32)),
                   "integer input is outside the 64-bit range")
        result = ir.Constant(g.input_type, None)
        result = b.insert_value(result, b.icmp_signed("==", status, self.constant(1, 32)), 0)
        result = b.insert_value(result, b.load(number), 1)
        return b.insert_value(result, text, 2)

    def _line_helper(self):
        if self.line_function is not None:
            return self.line_function
        g, saved = self.g, self.g.builder
        fn = ir.Function(g.module, ir.FunctionType(g.i8p, []), name="em_read_line")
        self.line_function = fn
        b = ir.IRBuilder(fn.append_basic_block("entry"))
        g.builder = b
        buffer, capacity, length = b.alloca(g.i8p), b.alloca(g.i64), b.alloca(g.i64)
        b.store(self.constant(64), capacity)
        b.store(self.constant(0), length)
        allocated = b.call(self.malloc, [self.constant(64)])
        self.guard(b.icmp_unsigned("!=", allocated, ir.Constant(g.i8p, None)),
                   "input allocation failed")
        b.store(allocated, buffer)
        loop, body, grow, store, done = [fn.append_basic_block(name)
                                         for name in ("loop", "body", "grow", "store", "done")]
        b.branch(loop)
        b.position_at_end(loop)
        char = b.call(self.getchar, [])
        ended = b.or_(b.icmp_signed("==", char, self.constant(-1, 32)),
                      b.icmp_signed("==", char, self.constant(10, 32)))
        b.cbranch(ended, done, body)
        b.position_at_end(body)
        count = b.load(length)
        b.cbranch(b.icmp_unsigned(">=", b.add(count, self.constant(1)), b.load(capacity)), grow, store)
        b.position_at_end(grow)
        size = b.mul(b.load(capacity), self.constant(2))
        allocated = b.call(self.realloc, [b.load(buffer), size])
        self.guard(b.icmp_unsigned("!=", allocated, ir.Constant(g.i8p, None)),
                   "input allocation failed")
        b.store(allocated, buffer)
        b.store(size, capacity)
        b.branch(store)
        b.position_at_end(store)
        b.store(b.trunc(char, g.i8), b.gep(b.load(buffer), [b.load(length)]))
        b.store(b.add(b.load(length), self.constant(1)), length)
        b.branch(loop)
        b.position_at_end(done)
        self.guard(b.or_(b.icmp_signed("!=", char, self.constant(-1, 32)),
                         b.icmp_unsigned("!=", b.load(length), self.constant(0))),
                   "end of input")
        # Strip only the CR of a CRLF line ending, preserving all other text.
        trim, finish = fn.append_basic_block("trim_cr"), fn.append_basic_block("finish")
        b.cbranch(b.icmp_unsigned(">", b.load(length), self.constant(0)), trim, finish)
        b.position_at_end(trim)
        last_index = b.sub(b.load(length), self.constant(1))
        last = b.load(b.gep(b.load(buffer), [last_index]))
        crlf = b.and_(b.icmp_unsigned("==", last, self.constant(13, 8)),
                      b.icmp_signed("==", char, self.constant(10, 32)))
        b.store(b.select(crlf, last_index, b.load(length)), length)
        b.branch(finish)
        b.position_at_end(finish)
        b.store(self.constant(0, 8), b.gep(b.load(buffer), [b.load(length)]))
        b.ret(b.load(buffer))
        g.builder = saved
        return fn

    def _integer_helper(self):
        if self.parse_function is not None:
            return self.parse_function
        g, saved = self.g, self.g.builder
        fn = ir.Function(g.module, ir.FunctionType(g.i32, [g.i8p, g.i64.as_pointer()]),
                         name="em_parse_integer")
        self.parse_function = fn
        b = ir.IRBuilder(fn.append_basic_block("entry"))
        g.builder = b
        text, output = fn.args
        invalid = fn.append_basic_block("text")
        first = b.load(text)
        minus = b.icmp_unsigned("==", first, self.constant(45, 8))
        sign = b.or_(minus, b.icmp_unsigned("==", first, self.constant(43, 8)))
        offset = b.zext(sign, g.i64)
        current = b.gep(text, [offset])
        char = b.load(current)
        digit = b.and_(b.icmp_unsigned(">=", char, self.constant(48, 8)),
                       b.icmp_unsigned("<=", char, self.constant(57, 8)))
        decimal, roman = fn.append_basic_block("decimal"), fn.append_basic_block("roman")
        b.cbranch(digit, decimal, roman)
        b.position_at_end(decimal)
        cursor, total, overflow = b.alloca(g.i8p), b.alloca(g.i64), b.alloca(g.i1)
        b.store(current, cursor)
        b.store(self.constant(0), total)
        b.store(self.constant(0, 1), overflow)
        limit = b.select(minus, self.constant(2**63), self.constant(2**63 - 1))
        loop, body, done = [fn.append_basic_block(name) for name in ("digit_loop", "digit", "decimal_done")]
        b.branch(loop)
        b.position_at_end(loop)
        char = b.load(b.load(cursor))
        b.cbranch(b.icmp_unsigned("==", char, self.constant(0, 8)), done, body)
        b.position_at_end(body)
        digit = b.and_(b.icmp_unsigned(">=", char, self.constant(48, 8)),
                       b.icmp_unsigned("<=", char, self.constant(57, 8)))
        valid_digit = fn.append_basic_block("valid_digit")
        b.cbranch(digit, valid_digit, invalid)
        b.position_at_end(valid_digit)
        number = b.zext(b.sub(char, self.constant(48, 8)), g.i64)
        max_previous = b.udiv(b.sub(limit, number), self.constant(10))
        b.store(b.or_(b.load(overflow), b.icmp_unsigned(">", b.load(total), max_previous)), overflow)
        b.store(b.add(b.mul(b.load(total), self.constant(10)), number), total)
        b.store(b.gep(b.load(cursor), [self.constant(1)]), cursor)
        b.branch(loop)
        b.position_at_end(done)
        overflow_block, accepted = fn.append_basic_block("overflow"), fn.append_basic_block("accepted")
        b.cbranch(b.load(overflow), overflow_block, accepted)
        b.position_at_end(overflow_block)
        b.ret(self.constant(2, 32))
        b.position_at_end(accepted)
        value = b.load(total)
        b.store(b.select(minus, b.neg(value), value), output)
        b.ret(self.constant(1, 32))
        b.position_at_end(roman)
        length = b.call(self.strlen, [text])
        roman_start = fn.append_basic_block("roman_start")
        allowed = b.and_(b.not_(sign), b.and_(b.icmp_unsigned(">", length, self.constant(0)),
                                             b.icmp_unsigned("<=", length, self.constant(15))))
        b.cbranch(allowed, roman_start, invalid)
        b.position_at_end(roman_start)
        index, previous, total = b.alloca(g.i64), b.alloca(g.i64), b.alloca(g.i64)
        for slot in (index, previous, total):
            b.store(self.constant(0), slot)
        roman_loop, roman_body, canonical = [fn.append_basic_block(name)
                                            for name in ("roman_loop", "roman_char", "canonical")]
        b.branch(roman_loop)
        b.position_at_end(roman_loop)
        b.cbranch(b.icmp_unsigned("<", b.load(index), length), roman_body, canonical)
        b.position_at_end(roman_body)
        char = b.load(b.gep(text, [b.load(index)]))
        value = self.constant(0)
        for letter, amount in (("I", 1), ("V", 5), ("X", 10), ("L", 50),
                               ("C", 100), ("D", 500), ("M", 1000)):
            value = b.select(b.icmp_unsigned("==", char, self.constant(ord(letter), 8)),
                             self.constant(amount), value)
        roman_valid = fn.append_basic_block("roman_valid")
        b.cbranch(b.icmp_unsigned("!=", value, self.constant(0)), roman_valid, invalid)
        b.position_at_end(roman_valid)
        subtract = b.select(b.icmp_unsigned(">", value, b.load(previous)),
                             b.mul(b.load(previous), self.constant(2)), self.constant(0))
        b.store(b.sub(b.add(b.load(total), value), subtract), total)
        b.store(value, previous)
        b.store(b.add(b.load(index), self.constant(1)), index)
        b.branch(roman_loop)
        b.position_at_end(canonical)
        canonical_start = fn.append_basic_block("canonical_start")
        value = b.load(total)
        b.cbranch(b.and_(b.icmp_signed(">", value, self.constant(0)),
                         b.icmp_signed("<=", value, self.constant(3999))), canonical_start, invalid)
        b.position_at_end(canonical_start)
        b.store(value, output)
        b.store(self.constant(0), index)
        for token, amount in (("M", 1000), ("CM", 900), ("D", 500), ("CD", 400),
                              ("C", 100), ("XC", 90), ("L", 50), ("XL", 40),
                              ("X", 10), ("IX", 9), ("V", 5), ("IV", 4), ("I", 1)):
            test, match, advance, next_token = [fn.append_basic_block(name)
                                                for name in ("token_test", "token_match", "advance", "next_token")]
            b.branch(test)
            b.position_at_end(test)
            b.cbranch(b.icmp_unsigned(">=", b.load(total), self.constant(amount)), match, next_token)
            b.position_at_end(match)
            compared = b.call(self.strncmp, [b.gep(text, [b.load(index)]),
                                             g._string_pointer(token), self.constant(len(token))])
            b.cbranch(b.icmp_signed("==", compared, self.constant(0, 32)), advance, invalid)
            b.position_at_end(advance)
            b.store(b.add(b.load(index), self.constant(len(token))), index)
            b.store(b.sub(b.load(total), self.constant(amount)), total)
            b.branch(test)
            b.position_at_end(next_token)
        roman_accepted = fn.append_basic_block("roman_accepted")
        b.cbranch(b.icmp_unsigned("==", b.load(index), length), roman_accepted, invalid)
        b.position_at_end(roman_accepted)
        b.ret(self.constant(1, 32))
        b.position_at_end(invalid)
        b.ret(self.constant(0, 32))
        g.builder = saved
        return fn
