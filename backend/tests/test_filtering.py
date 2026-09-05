import pandas as pd
import pytest

from app.errors import AppError
from app.filtering import evaluate_filter
from app.models import FilterCondition, FilterGroup


def make_df():
    return pd.DataFrame(
        {
            "species": ["setosa", "versicolor", "virginica", "setosa"],
            "sepal_length": [5.1, 6.0, 7.2, 4.9],
        }
    )


def test_simple_condition():
    df = make_df()
    cond = FilterCondition(column="species", operator="eq", value="setosa")
    mask = evaluate_filter(df, cond)
    assert mask.tolist() == [True, False, False, True]


def test_and_group():
    df = make_df()
    group = FilterGroup(
        logic="AND",
        conditions=[
            FilterCondition(column="species", operator="eq", value="setosa"),
            FilterCondition(column="sepal_length", operator="gt", value=5.0),
        ],
    )
    mask = evaluate_filter(df, group)
    assert mask.tolist() == [True, False, False, False]


def test_or_group():
    df = make_df()
    group = FilterGroup(
        logic="OR",
        conditions=[
            FilterCondition(column="species", operator="eq", value="setosa"),
            FilterCondition(column="species", operator="eq", value="virginica"),
        ],
    )
    mask = evaluate_filter(df, group)
    assert mask.tolist() == [True, False, True, True]


def test_in_operator():
    df = make_df()
    cond = FilterCondition(column="species", operator="in", value=["setosa", "virginica"])
    mask = evaluate_filter(df, cond)
    assert mask.tolist() == [True, False, True, True]


def test_not_in_operator():
    df = make_df()
    cond = FilterCondition(column="species", operator="not_in", value=["setosa"])
    mask = evaluate_filter(df, cond)
    assert mask.tolist() == [False, True, True, False]


def test_contains_operator():
    df = make_df()
    cond = FilterCondition(column="species", operator="contains", value="vir")
    mask = evaluate_filter(df, cond)
    assert mask.tolist() == [False, False, True, False]


def test_between_operator():
    df = make_df()
    cond = FilterCondition(column="sepal_length", operator="between", value=[5.0, 6.5])
    mask = evaluate_filter(df, cond)
    assert mask.tolist() == [True, True, False, False]


def test_is_null():
    df = pd.DataFrame({"x": [1, None, 3]})
    cond = FilterCondition(column="x", operator="is_null")
    mask = evaluate_filter(df, cond)
    assert mask.tolist() == [False, True, False]


def test_unknown_column_raises():
    df = make_df()
    cond = FilterCondition(column="does_not_exist", operator="eq", value="x")
    with pytest.raises(AppError):
        evaluate_filter(df, cond)


def test_missing_value_for_required_operator_raises():
    df = make_df()
    cond = FilterCondition(column="sepal_length", operator="gt", value=None)
    with pytest.raises(AppError):
        evaluate_filter(df, cond)


def test_none_filter_selects_everything():
    df = make_df()
    mask = evaluate_filter(df, None)
    assert mask.tolist() == [True, True, True, True]
