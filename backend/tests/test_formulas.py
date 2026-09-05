import pandas as pd
import pytest

from app.errors import AppError
from app.formulas import evaluate_formula


def test_simple_arithmetic():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    result, errors = evaluate_formula(df, "{a} + {b}")
    assert result.tolist() == [5, 7, 9]
    assert errors == 0


def test_bare_column_name_reference():
    df = pd.DataFrame({"a": [1, 2, 3]})
    result, _ = evaluate_formula(df, "a * 2")
    assert result.tolist() == [2, 4, 6]


def test_if_function():
    df = pd.DataFrame({"age": [10, 20, 30]})
    result, _ = evaluate_formula(df, 'if({age} > 18, "adult", "minor")')
    assert result.tolist() == ["minor", "adult", "adult"]


def test_string_functions():
    df = pd.DataFrame({"name": ["alice", "bob"]})
    result, _ = evaluate_formula(df, "upper({name})")
    assert result.tolist() == ["ALICE", "BOB"]


def test_math_functions():
    df = pd.DataFrame({"x": [4, 9, 16]})
    result, _ = evaluate_formula(df, "sqrt({x})")
    assert result.tolist() == [2.0, 3.0, 4.0]


def test_round_function():
    df = pd.DataFrame({"x": [1.2345]})
    result, _ = evaluate_formula(df, "round({x}, 2)")
    assert result.tolist() == [1.23]


def test_unknown_column_raises():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(AppError):
        evaluate_formula(df, "{unknown} * 2")


def test_unknown_function_raises():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(AppError):
        evaluate_formula(df, "hack({a})")


def test_syntax_error_raises():
    df = pd.DataFrame({"a": [1, 2]})
    with pytest.raises(AppError):
        evaluate_formula(df, "{a} +")


def test_division_by_zero_is_per_row_none():
    df = pd.DataFrame({"a": [1, 2, 3]})
    result, errors = evaluate_formula(df, "{a} / 0")
    assert result.tolist() == [None, None, None]
    assert errors == 3


@pytest.mark.parametrize(
    "formula",
    [
        '__import__("os").system("echo pwned")',
        "().__class__.__bases__[0]",
        "[x for x in range(10)]",
        "(lambda: 1)()",
        "open('/etc/passwd')",
    ],
)
def test_sandbox_escape_attempts_rejected(formula):
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(AppError):
        evaluate_formula(df, formula)
