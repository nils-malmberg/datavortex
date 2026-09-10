"""Phase 10, §5.3 : non-régression de performance sur un jeu de données volumineux.

Les seuils sont volontairement bien plus larges que ceux de la spec (qui vise
un poste de développement dédié) : un runner CI partagé peut être plusieurs
fois plus lent qu'une machine de développement sans qu'il s'agisse d'une
régression réelle. Le but est d'attraper une réintroduction accidentelle
d'une boucle Python ligne à ligne ou d'un comportement quadratique — pas de
mesurer une performance absolue, ce que fait `scripts/benchmark.py` (Phase 9)
en dehors de la suite de tests.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from app.groupby_service import run_groupby
from app.models import AggregationSpec
from app.stats import dataframe_summary
from app.stats_service import advanced_stats

N_ROWS = 300_000


@pytest.fixture(scope="module")
def large_df():
    rng = np.random.default_rng(20241010)
    departments = rng.choice(["Sales", "IT", "HR", "Finance", "Marketing"], size=N_ROWS)
    age = rng.integers(18, 66, size=N_ROWS)
    salary = rng.normal(45_000, 12_000, size=N_ROWS)
    score = rng.normal(0, 1, size=N_ROWS)
    return pd.DataFrame({"department": departments, "age": age, "salary": salary, "score": score})


def test_groupby_scales_to_hundreds_of_thousands_of_rows(large_df):
    aggregations = [AggregationSpec(column="salary", func="mean"), AggregationSpec(column="age", func="max")]
    start = time.perf_counter()
    result = run_groupby(large_df, group_by=["department"], aggregations=aggregations)
    duration = time.perf_counter() - start
    assert len(result["table"]) == large_df["department"].nunique()
    assert duration < 5.0, f"GroupBy sur {N_ROWS} lignes trop lent : {duration:.2f}s"


def test_stats_summary_scales_to_hundreds_of_thousands_of_rows(large_df):
    start = time.perf_counter()
    summary = dataframe_summary(large_df)
    duration = time.perf_counter() - start
    assert "salary" in summary["columns"]
    assert duration < 5.0, f"Stats sur {N_ROWS} lignes trop lentes : {duration:.2f}s"


def test_advanced_stats_scales_to_hundreds_of_thousands_of_rows(large_df):
    start = time.perf_counter()
    advanced_stats(large_df[["age", "salary", "score"]])
    duration = time.perf_counter() - start
    assert duration < 10.0, f"Stats avancées sur {N_ROWS} lignes trop lentes : {duration:.2f}s"


def test_polars_csv_parse_beats_python_engine_on_large_file():
    """Confirme le gain Phase 9 : Polars doit rester nettement plus rapide que
    le moteur Python de pandas sur un CSV de taille significative."""
    import polars as pl

    from app.data_engine import parse_csv_polars
    from app.parsing import parse_csv as parse_csv_pandas_python

    rng = np.random.default_rng(1)
    n = 100_000
    df = pl.DataFrame({
        "a": rng.integers(0, 1000, size=n),
        "b": rng.normal(size=n),
        "c": [f"row_{i}" for i in range(n)],
    })
    csv_bytes = df.write_csv().encode("utf-8")

    start = time.perf_counter()
    parse_csv_polars(csv_bytes, separator=",")
    polars_duration = time.perf_counter() - start

    start = time.perf_counter()
    parse_csv_pandas_python(csv_bytes, encoding="utf-8", separator=",")
    pandas_duration = time.perf_counter() - start

    assert polars_duration < pandas_duration, (
        f"Polars ({polars_duration:.3f}s) devrait rester plus rapide que le moteur "
        f"Python de pandas ({pandas_duration:.3f}s) sur {n} lignes."
    )
