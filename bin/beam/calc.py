"""Arithmetic: a small Pratt parser over Decimal. Never uses eval."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation, localcontext
from typing import List, NamedTuple, Optional

from . import fmt
from .types import Answer, Context

FUNCS = {"sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "log", "ln", "exp",
         "abs", "round", "floor", "ceil", "min", "max"}
CONSTS = {"pi": Decimal("3.14159265358979323846264338327950288"),
          "e": Decimal("2.71828182845904523536028747135266250")}
MAX_LEN = 200

# Western (1,234,567) or Indian (12,34,567) grouping; only outside function args.
_NUM_GROUPED = re.compile(r"(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?")
_NUM = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_IDENT = re.compile(r"[A-Za-z_]+")
_GATE = re.compile(r"\d|\bpi\b|\bans\b|\b(?:" + "|".join(sorted(FUNCS)) + r")\s*\(", re.I)


class Tok(NamedTuple):
    kind: str  # num | id | op | lp | rp | comma
    val: object


class CalcError(Exception):
    pass


def _normalise(s: str) -> str:
    return (s.replace("−", "-").replace("×", "*").replace("÷", "/").replace("·", "*")
            .replace("**", "^").replace("π", "pi"))


def tokenize(s: str) -> Optional[List[Tok]]:
    s = _normalise(s)
    toks: List[Tok] = []
    stack: List[str] = []  # "f" inside a function call's parens, "g" for grouping
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            m = None
            if not stack or stack[-1] != "f":
                m = _NUM_GROUPED.match(s, i)
                if m and m.end() < n and s[m.end()] == ",":
                    m = None  # "1,234,5" is not a grouped number
            if m is None:
                m = _NUM.match(s, i)
            try:
                toks.append(Tok("num", Decimal(m.group().replace(",", ""))))
            except InvalidOperation:
                return None
            i = m.end()
            continue
        if c.isalpha() or c == "_":
            m = _IDENT.match(s, i)
            word = m.group().lower()
            i = m.end()
            if word == "x" and toks and toks[-1].kind in ("num", "rp"):
                j = i
                while j < n and s[j].isspace():
                    j += 1
                if j < n and (s[j].isdigit() or s[j] in "(."):
                    toks.append(Tok("op", "*"))
                    continue
            toks.append(Tok("id", word))
            continue
        if c == "(":
            stack.append("f" if toks and toks[-1].kind == "id" and toks[-1].val in FUNCS else "g")
            toks.append(Tok("lp", "("))
        elif c == ")":
            if not stack:
                return None
            stack.pop()
            toks.append(Tok("rp", ")"))
        elif c == ",":
            if not stack or stack[-1] != "f":
                return None
            toks.append(Tok("comma", ","))
        elif c in "+-*/^%!":
            toks.append(Tok("op", c))
        else:
            return None
        i += 1
    toks.extend(Tok("rp", ")") for _ in stack)  # forgive missing closing parens
    return toks


class Parser:
    BP = {"+": 10, "-": 10, "*": 20, "/": 20, "mod": 20, "^": 40}

    def __init__(self, toks: List[Tok]):
        self.toks = toks
        self.i = 0

    def peek(self) -> Optional[Tok]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self) -> Tok:
        tok = self.peek()
        if tok is None:
            raise CalcError("unexpected end")
        self.i += 1
        return tok

    def parse(self):
        node = self.expr(0)
        if self.peek() is not None:
            raise CalcError("trailing input")
        return node

    def _starts_operand(self, tok: Optional[Tok], prev: Tok) -> bool:
        if tok is None:
            return False
        if tok.kind == "lp":
            return True
        if tok.kind == "id" and tok.val != "mod":
            return True
        return tok.kind == "num" and prev.kind == "rp"

    def expr(self, rbp: int):
        tok = self.next()
        left = self.nud(tok)
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok.kind == "op" and tok.val in "!%":
                if 50 <= rbp:
                    break
                self.next()
                left = ("fact", left) if tok.val == "!" else ("pct", left)
                continue
            op = tok.val if tok.kind == "op" else ("mod" if tok.kind == "id" and tok.val == "mod" else None)
            if op in self.BP:
                bp = self.BP[op]
                if bp <= rbp:
                    break
                self.next()
                right = self.expr(bp - 1 if op == "^" else bp)
                left = ("bin", op, left, right)
                continue
            if self._starts_operand(tok, self.toks[self.i - 1]):
                if 20 <= rbp:
                    break
                right = self.expr(20)
                left = ("bin", "*", left, right)
                continue
            break
        return left

    def nud(self, tok: Tok):
        if tok.kind == "num":
            return ("num", tok.val)
        if tok.kind == "op" and tok.val in "+-":
            operand = self.expr(30)
            return ("neg", operand) if tok.val == "-" else operand
        if tok.kind == "lp":
            node = self.expr(0)
            if self.next().kind != "rp":
                raise CalcError("expected )")
            return node
        if tok.kind == "id":
            name = tok.val
            if name in CONSTS:
                return ("const", name)
            if name == "ans":
                return ("ans",)
            if name in FUNCS:
                nxt = self.peek()
                if nxt is not None and nxt.kind == "lp":
                    self.next()
                    args = [self.expr(0)]
                    while self.peek() is not None and self.peek().kind == "comma":
                        self.next()
                        args.append(self.expr(0))
                    if self.next().kind != "rp":
                        raise CalcError("expected )")
                    return ("call", name, args)
                return ("call", name, [self.expr(30)])
        raise CalcError(f"unexpected {tok.val!r}")


def _float_fn(fn, x: Decimal) -> Decimal:
    return Decimal(repr(fn(float(x))))


def evaluate(node, ctx: Context) -> Decimal:
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "const":
        return CONSTS[node[1]]
    if kind == "ans":
        if ctx.ans is None:
            raise CalcError("no previous answer")
        return ctx.ans
    if kind == "neg":
        return -evaluate(node[1], ctx)
    if kind == "pct":
        return evaluate(node[1], ctx) / 100
    if kind == "fact":
        x = evaluate(node[1], ctx)
        if x != x.to_integral_value() or x < 0 or x > 1000:
            raise CalcError("factorial domain")
        return Decimal(math.factorial(int(x)))
    if kind == "bin":
        op, a_node, b_node = node[1], node[2], node[3]
        a = evaluate(a_node, ctx)
        if op in "+-" and b_node[0] == "pct":
            p = evaluate(b_node[1], ctx) / 100
            return a * (1 + p) if op == "+" else a * (1 - p)
        b = evaluate(b_node, ctx)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise CalcError("division by zero")
            return a / b
        if op == "mod":
            if b == 0:
                raise CalcError("mod by zero")
            return a % b
        if op == "^":
            if b == b.to_integral_value() and abs(b) <= 10000:
                if a == 0 and b < 0:
                    raise CalcError("zero to a negative power")
                return a ** int(b)
            if a < 0:
                raise CalcError("fractional power of a negative number")
            return _float_fn(lambda x: x ** float(b), a)
    if kind == "call":
        name, args = node[1], [evaluate(a, ctx) for a in node[2]]
        return _call(name, args)
    raise CalcError(f"bad node {kind}")


def _call(name: str, args: List[Decimal]) -> Decimal:
    if name in ("min", "max"):
        return min(args) if name == "min" else max(args)
    if name == "round":
        if len(args) not in (1, 2):
            raise CalcError("round takes 1 or 2 arguments")
        places = int(args[1]) if len(args) == 2 else 0
        return args[0].quantize(Decimal(1).scaleb(-places))
    if len(args) != 1:
        raise CalcError(f"{name} takes one argument")
    x = args[0]
    if name == "sqrt":
        if x < 0:
            raise CalcError("sqrt of a negative number")
        return x.sqrt()
    if name == "abs":
        return abs(x)
    if name == "floor":
        return Decimal(math.floor(x))
    if name == "ceil":
        return Decimal(math.ceil(x))
    if name in ("log", "ln"):
        if x <= 0:
            raise CalcError("log domain")
        return x.log10() if name == "log" else x.ln()
    fns = {"sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin,
           "acos": math.acos, "atan": math.atan, "exp": math.exp}
    return _float_fn(fns[name], x)


def _interesting(toks: List[Tok]) -> bool:
    """A bare number is not worth an answer row; an expression is."""
    for i, tok in enumerate(toks):
        if tok.kind in ("id", "lp", "comma"):
            return True
        if tok.kind == "op" and (tok.val in "*/^%!" or i > 0):
            return True
    return False


def compute(s: str, ctx: Context) -> Decimal:
    """Evaluate an expression or raise CalcError. Used by other parsers too."""
    toks = tokenize(s)
    if not toks:
        raise CalcError("cannot tokenize")
    with localcontext() as lc:
        lc.prec = 34
        try:
            value = evaluate(Parser(toks).parse(), ctx)
            return +value
        except (InvalidOperation, ArithmeticError, ValueError, OverflowError) as e:
            raise CalcError(str(e)) from None


def pretty(s: str) -> str:
    s = _normalise(" ".join(s.split()))
    return s.replace("*", "×").replace("/", "÷")


_PCT_OF = re.compile(r"^(?P<p>.+?)\s*%\s*of\s+(?P<b>.+)$", re.I)
_WHAT_PCT = re.compile(r"^what\s*%\s*of\s+(?P<b>.+?)\s+is\s+(?P<a>.+)$", re.I)
_IS_WHAT_PCT = re.compile(r"^(?P<a>.+?)\s+is\s+what\s*%\s*of\s+(?P<b>.+)$", re.I)


def _answer(value: Decimal, detail: str, ctx: Context, suffix: str = "") -> List[Answer]:
    digits = ctx.settings.significant_digits
    grouping = fmt.resolve_grouping(ctx.settings.grouping, ctx.locale)
    return [Answer(value=fmt.display(value, digits, grouping) + suffix,
                   copy=fmt.plain(value, digits), detail=detail, kind="calculator")]


def _special(s: str, ctx: Context) -> Optional[List[Answer]]:
    m = _WHAT_PCT.match(s) or _IS_WHAT_PCT.match(s)
    if m:
        a, b = compute(m.group("a"), ctx), compute(m.group("b"), ctx)
        if b == 0:
            raise CalcError("division by zero")
        return _answer(a / b * 100, f"{pretty(m.group('a'))} of {pretty(m.group('b'))}", ctx, "%")
    m = _PCT_OF.match(s)
    if m:
        p, b = compute(m.group("p"), ctx), compute(m.group("b"), ctx)
        return _answer(p / 100 * b, f"{pretty(m.group('p'))}% of {pretty(m.group('b'))}", ctx)
    return None


def parse(q: str, ctx: Context) -> Optional[List[Answer]]:
    s = q.strip()
    if not s or len(s) > MAX_LEN or not _GATE.search(s):
        return None
    try:
        special = _special(s, ctx)
        if special:
            return special
        toks = tokenize(s)
        if not toks or not _interesting(toks):
            return None
        value = compute(s, ctx)
        return _answer(value, pretty(s), ctx)
    except (CalcError, ValueError):
        return None
