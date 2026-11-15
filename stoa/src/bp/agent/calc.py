"""A safe calculator. The model writes the expression. The numbers in it must come from a tool or the question."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable  # noqa: TC003 - used in runtime annotations
from typing import Final

CONSTANTS: Final[dict[str, float]] = {
    "M2_PER_FT2": 0.09290304,
    "FT2_PER_M2": 10.763910416709722,
    "M_PER_FT": 0.3048,
    "FT_PER_M": 3.280839895013123,
    "M3_PER_FT3": 0.028316846592,
    "PI": math.pi,
}
# Literals that an expression may always hold: small integers for counting steps and percent arithmetic.
FREE_LITERALS: Final[frozenset[float]] = frozenset({0.0, 1.0, 2.0, 100.0})

_BINARY: Final[dict[type[ast.operator], Callable[[float, float], float]]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_FUNCTIONS: Final[dict[str, Callable[..., float]]] = {
    "sum": lambda *xs: float(sum(xs)),
    "min": lambda *xs: float(min(xs)),
    "max": lambda *xs: float(max(xs)),
    "count": lambda *xs: float(len(xs)),
    "mean": lambda *xs: float(sum(xs) / len(xs)),
    "abs": lambda x: float(abs(x)),
    "sqrt": lambda x: float(math.sqrt(x)),
    "ceil": lambda x: float(math.ceil(x)),
    "floor": lambda x: float(math.floor(x)),
    "round": lambda x, n=0: float(round(x, int(n))),
}


class CalcError(ValueError):
    pass


def _flatten(values: list[float | list[float]]) -> list[float]:
    flat: list[float] = []
    for value in values:
        flat.extend(value) if isinstance(value, list) else flat.append(value)
    return flat


def _walk(node: ast.AST, literals: list[float]) -> float | list[float]:  # noqa: C901, PLR0911, PLR0912 - one grammar
    if isinstance(node, ast.Expression):
        return _walk(node.body, literals)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalcError("only numbers are allowed")
        literals.append(float(node.value))
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in CONSTANTS:
            raise CalcError(f"unknown name {node.id}")
        return CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _walk(node.operand, literals)
        if isinstance(value, list):
            raise CalcError("a sign needs one number")
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _walk(node.left, literals), _walk(node.right, literals)
        if isinstance(left, list) or isinstance(right, list):
            raise CalcError("an operator needs two numbers")
        try:
            return float(_BINARY[type(node.op)](left, right))
        except (ZeroDivisionError, OverflowError) as exc:
            raise CalcError(str(exc)) from exc
    if isinstance(node, (ast.List, ast.Tuple)):
        return _flatten([_walk(element, literals) for element in node.elts])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        if node.keywords:
            raise CalcError("no keyword arguments")
        arguments = [_walk(argument, literals) for argument in node.args]
        name = node.func.id
        try:
            if name in {"sum", "min", "max", "count", "mean"}:
                return _FUNCTIONS[name](*_flatten(arguments))
            if any(isinstance(a, list) for a in arguments):
                raise CalcError(f"{name} needs plain numbers")
            return _FUNCTIONS[name](*arguments)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            raise CalcError(f"{name}: {exc}") from exc
    raise CalcError(f"not allowed: {ast.dump(node)[:80]}")


def evaluate(expression: str) -> tuple[float, list[float]]:
    """Return the value and every literal number of the expression."""
    if len(expression) > 4000:
        raise CalcError("the expression is too long")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise CalcError(f"syntax: {exc.msg}") from exc
    literals: list[float] = []
    value = _walk(tree, literals)
    if isinstance(value, list):
        raise CalcError("the result is a list, use sum, count, min, max or mean")
    if not math.isfinite(value):
        raise CalcError("the result is not finite")
    return value, literals
