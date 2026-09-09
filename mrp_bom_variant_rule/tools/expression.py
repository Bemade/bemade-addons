# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Restricted arithmetic over named parameters.

Quantity expressions are authored as data by the people who maintain a
ruleset, so they must not be a way to run arbitrary code. Rather than filter a
denylist out of ``eval``, this walks the parsed tree and accepts only the node
types arithmetic actually needs. Anything else - a call, an attribute access,
a comprehension, a subscript, a name that is not a supplied parameter - is
refused before evaluation, not caught after it.

Evaluation then walks that validated tree directly instead of handing it to
``eval``. The validation alone would arguably be enough, but an explicit
interpreter cannot be defeated by an oversight in the node whitelist, and it
keeps the promise of "arithmetic only" checkable by reading fifty lines rather
than by trusting that nothing reachable from ``eval`` was missed.
"""

import ast
import math
import operator

# Arithmetic only. No calls, no attribute access, no subscripting, no
# comprehensions, no lambdas, no conditionals, no string or container
# literals: none of them are needed to express a component quantity.
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)


class ExpressionError(ValueError):
    """Raised for an expression that cannot be safely evaluated."""


def check_expression(expr):
    """Parse and validate ``expr``, returning the names it references.

    Raises ``ExpressionError`` if it is not restricted arithmetic.
    """
    if not expr or not expr.strip():
        raise ExpressionError("the expression is empty")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as err:
        raise ExpressionError(f"it cannot be parsed ({err.msg})") from err

    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ExpressionError(
                f"{type(node).__name__} is not permitted; only arithmetic "
                f"over parameter names is allowed"
            )
        if isinstance(node, ast.Constant) and not isinstance(
            node.value, (int, float)
        ):
            raise ExpressionError("only numeric constants are allowed")
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def evaluate_expression(expr, params):
    """Evaluate ``expr`` against ``params``.

    A name the parameters do not supply is an error rather than a default: a
    quantity that silently becomes zero drops the component out of the bill of
    materials, and out of the cost, without anyone noticing.
    """
    names = check_expression(expr)
    missing = sorted(names - set(params))
    if missing:
        raise ExpressionError(
            "no parameter supplies "
            + ", ".join(repr(name) for name in missing)
        )
    try:
        result = _eval_node(ast.parse(expr, mode="eval").body, params)
    except ZeroDivisionError as err:
        raise ExpressionError("it divides by zero") from err
    except (TypeError, ValueError, OverflowError) as err:
        raise ExpressionError(f"it could not be evaluated ({err})") from err

    if isinstance(result, bool) or not isinstance(result, (int, float)):
        raise ExpressionError("it does not produce a number")
    result = float(result)
    if math.isnan(result) or math.isinf(result):
        raise ExpressionError("it does not produce a finite number")
    if result < 0:
        raise ExpressionError(f"it produces a negative quantity ({result})")
    return result


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node, params):
    """Evaluate one validated node. Anything unexpected is a bug in the
    whitelist rather than user input, so it raises rather than returning."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return params[node.id]
    if isinstance(node, ast.BinOp):
        apply = _BINARY_OPERATORS[type(node.op)]
        return apply(
            _eval_node(node.left, params), _eval_node(node.right, params)
        )
    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPERATORS[type(node.op)](
            _eval_node(node.operand, params)
        )
    raise ExpressionError(
        f"{type(node).__name__} cannot be evaluated as arithmetic"
    )
