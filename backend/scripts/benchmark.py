"""Mesures de performance Phase 9 (§7.2).

    python scripts/benchmark.py --csv test_data/large_500k.csv

Compare, sur un même fichier, les chemins d'avant et d'après la Phase 9 :
analyse CSV, détection d'encoding, agrégation, filtrage et export. Chaque
mesure est répétée et c'est la médiane qui est retenue — la première exécution
paie le chargement des modules et le cache disque à froid.
"""
from __future__ import annotations

import argparse
import gc
import io
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Callable

# Exécutable directement depuis backend/ sans installation préalable du paquet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chardet
import pandas as pd
import polars as pl
import psutil

from app.data_engine import parse_csv_pandas_c, parse_csv_polars, sniff_sample
from app.parsing import detect_separator
from app.parsing import parse_csv as parse_csv_pandas_python
from app.streaming import iter_csv_chunks

PROCESS = psutil.Process()


def rss_mb() -> float:
    return PROCESS.memory_info().rss / 1024 / 1024


def measure(label: str, fn: Callable[[], object], repeats: int = 3, track: str = "rss") -> dict:
    """Chronomètre une opération et relève son pic mémoire.

    Deux instruments, parce qu'aucun ne convient aux deux cas :

    - `track="rss"` mesure la mémoire résidente du processus. C'est le bon
      instrument pour l'analyse CSV, dont l'essentiel des allocations est fait
      en natif par Polars ou NumPy, invisible depuis Python. En revanche il ne
      voit qu'un état *après* l'appel : un pic transitoire déjà relâché lui
      échappe.
    - `track="python"` utilise tracemalloc, qui suit les allocations Python et
      retient leur maximum même transitoire. C'est le bon instrument pour
      l'export CSV, construit de bout en bout en chaînes Python — et le seul
      capable de montrer le pic que l'export en flux supprime.
    """
    durations = []
    peak_rss = 0.0
    peak_python = 0.0

    for _ in range(repeats):
        gc.collect()
        if track == "python":
            tracemalloc.start()
        before = rss_mb()
        start = time.perf_counter()
        result = fn()
        durations.append(time.perf_counter() - start)
        # Relevé avant de relâcher le résultat : c'est lui qui porte le pic.
        peak_rss = max(peak_rss, rss_mb() - before)
        if track == "python":
            peak_python = max(peak_python, tracemalloc.get_traced_memory()[1] / 1024 / 1024)
            tracemalloc.stop()
        del result
    gc.collect()

    return {
        "label": label,
        "median_s": statistics.median(durations),
        "best_s": min(durations),
        "peak_mb": peak_python if track == "python" else peak_rss,
        "track": track,
    }


def _print_table(title: str, rows: list[dict], baseline: str | None = None, memory_note: str = "RSS") -> None:
    print(f"\n{title}")
    print("-" * len(title))
    base = next((r["median_s"] for r in rows if r["label"] == baseline), None)
    width = max(len(r["label"]) for r in rows)
    for row in rows:
        speedup = ""
        if base and row["label"] != baseline and row["median_s"] > 0:
            speedup = f"   {base / row['median_s']:6.1f}x"
        print(
            f"  {row['label']:<{width}}  {row['median_s']:8.3f}s"
            f"   {memory_note} {row['peak_mb']:7.1f} Mo{speedup}"
        )


def bench_parsing(raw: bytes, path: Path, repeats: int) -> None:
    rows = [
        measure("pandas (moteur Python)  [avant]", lambda: parse_csv_pandas_python(raw, "utf-8", ","), repeats),
        measure("pandas (moteur C)", lambda: parse_csv_pandas_c(raw, "utf-8", ","), repeats),
        measure("polars (octets)", lambda: parse_csv_polars(raw, ","), repeats),
        measure("polars (chemin disque)  [après]", lambda: parse_csv_polars(path, ","), repeats),
    ]
    _print_table("1. Analyse CSV", rows, baseline="pandas (moteur Python)  [avant]")


def bench_detection(raw: bytes, repeats: int) -> None:
    rows = [
        measure("chardet sur le fichier entier  [avant]", lambda: chardet.detect(raw), repeats),
        measure("chardet sur échantillon 256Ko  [après]", lambda: chardet.detect(sniff_sample(raw)), repeats),
        measure(
            "séparateur, fichier entier     [avant]",
            lambda: detect_separator(raw.decode("utf-8", errors="replace")),
            repeats,
        ),
        measure(
            "séparateur, échantillon        [après]",
            lambda: detect_separator(sniff_sample(raw).decode("utf-8", errors="replace")),
            repeats,
        ),
    ]
    _print_table("2. Détection d'encoding et de séparateur", rows)


def bench_operations(df: pd.DataFrame, frame: pl.DataFrame, repeats: int) -> None:
    rows = [
        measure("groupby pandas", lambda: df.groupby("department", observed=True)["salary"].mean(), repeats),
        measure(
            "groupby polars",
            lambda: frame.group_by("department").agg(pl.col("salary").mean()),
            repeats,
        ),
        measure("filtre pandas", lambda: df[df["age"] > 30], repeats),
        measure("filtre polars", lambda: frame.filter(pl.col("age") > 30), repeats),
        measure("tri pandas", lambda: df.sort_values("salary"), repeats),
        measure("tri polars", lambda: frame.sort("salary"), repeats),
    ]
    _print_table("3. Opérations analytiques", rows)
    print("  (colonne mémoire non significative ici : Polars conserve des arènes réutilisées)")


def bench_export(df: pd.DataFrame, repeats: int) -> None:
    def buffered() -> int:
        """Chemin historique : le CSV entier est construit puis encodé."""
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        return len(buffer.getvalue().encode("utf-8"))

    def streamed() -> int:
        """Chemin Phase 9 : rien de plus qu'une tranche n'existe à la fois."""
        return sum(len(chunk) for chunk in iter_csv_chunks(df, chunk_rows=10_000))

    rows = [
        measure("export en mémoire  [avant]", buffered, repeats, track="python"),
        measure("export en flux     [après]", streamed, repeats, track="python"),
    ]
    _print_table("4. Export CSV", rows, memory_note="pic Python")
    print("  (tracemalloc ralentit les deux lignes de façon comparable ; c'est le pic qui compte)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("test_data/large_500k.csv"))
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(
            f"Fichier introuvable : {args.csv}\n"
            "Générez-le d'abord : python scripts/generate_test_data.py --rows 500000"
        )

    size_mb = args.csv.stat().st_size / 1024 / 1024
    raw = args.csv.read_bytes()
    df = parse_csv_polars(args.csv, ",")
    frame = pl.read_csv(args.csv)

    print(f"Fichier   : {args.csv} ({size_mb:.1f} Mo)")
    print(f"Dimensions: {df.shape[0]:,} lignes x {df.shape[1]} colonnes")
    print(f"Répétitions: {args.repeats} (médiane retenue)")
    print(f"RSS initial: {rss_mb():.1f} Mo")
    print(f"DataFrame pandas en mémoire: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} Mo")

    bench_parsing(raw, args.csv, args.repeats)
    bench_detection(raw, args.repeats)
    bench_operations(df, frame, args.repeats)
    bench_export(df, args.repeats)

    print(f"\nRSS final : {rss_mb():.1f} Mo")


if __name__ == "__main__":
    main()
