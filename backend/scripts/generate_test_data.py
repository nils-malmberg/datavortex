"""Génération de jeux de données de test volumineux (Phase 9, §7.1).

    python scripts/generate_test_data.py --rows 500000 --out test_data/large_500k.csv

Les données sont plausibles plutôt qu'aléatoires uniformes : les départements
suivent une répartition déséquilibrée et les salaires en dépendent. Un jeu
parfaitement uniforme rendrait les agrégations anormalement régulières et
donnerait des mesures de performance trop optimistes.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import polars as pl

DEPARTMENTS = ["Sales", "IT", "HR", "Finance", "Marketing", "Support"]
# Répartition volontairement déséquilibrée : les groupes réels le sont.
DEPT_WEIGHTS = [0.30, 0.22, 0.10, 0.13, 0.12, 0.13]
DEPT_BASE_SALARY = {
    "Sales": 45_000, "IT": 62_000, "HR": 41_000,
    "Finance": 58_000, "Marketing": 48_000, "Support": 38_000,
}
CITIES = ["Paris", "Lyon", "Marseille", "Toulouse", "Nantes", "Bordeaux", "Lille"]


def generate(n_rows: int, seed: int = 20240901) -> pl.DataFrame:
    rng = np.random.default_rng(seed)

    dept_idx = rng.choice(len(DEPARTMENTS), size=n_rows, p=DEPT_WEIGHTS)
    departments = np.array(DEPARTMENTS)[dept_idx]
    base = np.array([DEPT_BASE_SALARY[d] for d in DEPARTMENTS])[dept_idx]

    age = rng.integers(18, 66, size=n_rows)
    # L'ancienneté fait monter le salaire : une corrélation réelle donne aux
    # agrégations et aux modèles quelque chose à trouver.
    seniority_bonus = (age - 18) * rng.normal(420, 90, size=n_rows)
    salary = np.maximum(20_000, base + seniority_bonus + rng.normal(0, 6_000, size=n_rows))

    frame = pl.DataFrame({
        "id": np.arange(n_rows, dtype=np.int64),
        "name": [f"user_{i}" for i in range(n_rows)],
        "age": age,
        "salary": np.round(salary, 2),
        "department": departments,
        "city": np.array(CITIES)[rng.integers(0, len(CITIES), size=n_rows)],
        "score": np.round(rng.beta(2.5, 2.0, size=n_rows) * 100, 3),
        "date": [
            f"2024-{m:02d}-{d:02d}"
            for m, d in zip(rng.integers(1, 13, n_rows), rng.integers(1, 29, n_rows))
        ],
        "active": rng.random(n_rows) > 0.25,
    })

    # ~2% de valeurs manquantes sur `score` : les données réelles en ont, et
    # leur gestion a un coût que le benchmark doit inclure.
    missing = rng.random(n_rows) < 0.02
    return frame.with_columns(
        pl.when(pl.Series(missing)).then(None).otherwise(pl.col("score")).alias("score")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=500_000)
    parser.add_argument("--out", type=Path, default=Path("test_data/large_500k.csv"))
    parser.add_argument("--seed", type=int, default=20240901)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    frame = generate(args.rows, args.seed)
    frame.write_csv(args.out)
    elapsed = time.perf_counter() - start

    size_mb = args.out.stat().st_size / 1024 / 1024
    print(f"{args.out} — {args.rows:,} lignes, {frame.width} colonnes, {size_mb:.1f} Mo ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
