"""Opérations et transformations de colonnes (Phase 8).

Deux familles distinctes : les opérations de structure (renommer, dupliquer,
supprimer, réordonner) et les transformations qui dérivent une nouvelle colonne
d'une colonne existante (découpage en classes, encodage, décalage, fenêtre
glissante).
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type

NUMERIC_TYPES = ("integer", "float")
MAX_BINS = 100
MAX_ONEHOT_LEVELS = 50
MAX_NEW_COLUMNS = 60

ROLLING_FUNCS = {"mean", "sum", "min", "max", "std", "median", "count", "var"}


def _require(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise column_not_found(column)


def _require_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    _require(df, column)
    if detect_column_type(df[column]) not in NUMERIC_TYPES:
        raise AppError(400, "INVALID_COLUMN_TYPE",
                       f"La colonne '{column}' doit être numérique pour cette transformation.")
    return pd.to_numeric(df[column], errors="coerce")


def _check_name_available(df: pd.DataFrame, name: str, replace: bool) -> None:
    if not name.strip():
        raise AppError(400, "INVALID_COLUMN_NAME", "Le nom de la nouvelle colonne est requis.")
    if name in df.columns and not replace:
        raise AppError(409, "COLUMN_ALREADY_EXISTS",
                       f"La colonne '{name}' existe déjà. Choisissez un autre nom ou autorisez le remplacement.")


# --------------------------------------------------------------------------
# Opérations de structure
# --------------------------------------------------------------------------

def apply_column_operation(session, op: str, columns: list[str], new_name: Optional[str],
                           order: Optional[list[str]]) -> dict[str, Any]:
    df = session.df

    if op == "reorder":
        if not order:
            raise AppError(400, "MISSING_ORDER", "L'ordre des colonnes est requis.")
        if sorted(order) != sorted(str(c) for c in df.columns):
            raise AppError(400, "INVALID_ORDER",
                           "L'ordre fourni doit contenir exactement les colonnes existantes, une seule fois chacune.")
        session.df = df[order]

    elif op == "rename":
        if len(columns) != 1:
            raise AppError(400, "INVALID_SELECTION", "Le renommage porte sur une seule colonne à la fois.")
        _require(df, columns[0])
        if not new_name or not new_name.strip():
            raise AppError(400, "INVALID_COLUMN_NAME", "Le nouveau nom est requis.")
        if new_name in df.columns and new_name != columns[0]:
            raise AppError(409, "COLUMN_ALREADY_EXISTS", f"Une colonne '{new_name}' existe déjà.")
        session.df = df.rename(columns={columns[0]: new_name})

    elif op == "duplicate":
        if len(columns) != 1:
            raise AppError(400, "INVALID_SELECTION", "La duplication porte sur une seule colonne à la fois.")
        _require(df, columns[0])
        target = new_name or f"{columns[0]}_copie"
        _check_name_available(df, target, replace=False)
        position = list(df.columns).index(columns[0]) + 1
        df.insert(position, target, df[columns[0]].copy())

    elif op == "delete":
        if not columns:
            raise AppError(400, "INVALID_SELECTION", "Sélectionnez au moins une colonne à supprimer.")
        for column in columns:
            _require(df, column)
        if len(columns) >= df.shape[1]:
            raise AppError(400, "CANNOT_DELETE_ALL",
                           "Impossible de supprimer toutes les colonnes : le jeu de données serait vide.")
        session.df = df.drop(columns=columns)

    else:  # pragma: no cover - garanti par Literal
        raise AppError(400, "UNKNOWN_OPERATION", f"Opération inconnue : {op}")

    _refresh_filter(session)
    return _columns_state(session)


def _refresh_filter(session) -> None:
    """Réapplique le filtre actif après modification de la structure.

    Si le filtre portait sur une colonne disparue, il devient invalide : on
    l'abandonne plutôt que de laisser la session dans un état incohérent.
    """
    from app.filtering import evaluate_filter

    session.touch()
    if session.active_filter is None:
        session.filtered_df = None
        return
    try:
        session.filtered_df = session.df[evaluate_filter(session.df, session.active_filter)]
    except AppError:
        session.active_filter = None
        session.filtered_df = None


def _columns_state(session) -> dict[str, Any]:
    df = session.df
    return {
        "session_id": session.session_id,
        "columns": [str(c) for c in df.columns],
        "column_types": {str(c): detect_column_type(df[c]) for c in df.columns},
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "filter_dropped": session.active_filter is None and session.filtered_df is None,
    }


def describe_columns(session) -> dict[str, Any]:
    """Liste des colonnes avec ce qu'il faut pour les gérer dans l'interface."""
    df = session.df
    items = []
    for position, column in enumerate(df.columns):
        series = df[column]
        column_type = detect_column_type(series)
        n_missing = int(series.isna().sum())
        items.append({
            "name": str(column),
            "position": position,
            "type": column_type,
            "missing": n_missing,
            "missing_pct": round(n_missing / df.shape[0] * 100, 2) if df.shape[0] else 0.0,
            "unique": int(series.nunique(dropna=True)),
            "is_numeric": column_type in NUMERIC_TYPES,
            "sample": [
                None if pd.isna(v) else str(v)
                for v in series.dropna().head(3)
            ],
        })
    return {**_columns_state(session), "items": items}


# --------------------------------------------------------------------------
# Transformations
# --------------------------------------------------------------------------

def _binning(df: pd.DataFrame, source: str, params: dict) -> tuple[pd.Series, str]:
    values = _require_numeric(df, source)
    method = params.get("method", "equal_width")
    bins = int(params.get("bins", 5))
    if not 2 <= bins <= MAX_BINS:
        raise AppError(400, "INVALID_BINS", f"Le nombre de classes doit être compris entre 2 et {MAX_BINS}.")

    if method == "equal_width":
        clean = values.dropna()
        if clean.empty:
            raise AppError(422, "INSUFFICIENT_DATA", f"La colonne '{source}' ne contient aucune valeur exploitable.")
        low, high = float(clean.min()), float(clean.max())
        if low == high:
            raise AppError(422, "CONSTANT_COLUMN",
                           f"La colonne '{source}' est constante : elle ne peut pas être découpée en classes.")
        # Bornes calculées explicitement : pandas 2.1.0 (version épinglée par le
        # projet) plante sur `pd.cut(series, bins=<entier>)` dès que la colonne
        # contient une valeur manquante. Passer les bornes contourne le défaut.
        edges = np.linspace(low, high, bins + 1)
        result = pd.cut(values, bins=edges, include_lowest=True, duplicates="drop")
        description = f"{bins} classes de largeur égale"
    elif method == "quantile":
        try:
            result = pd.qcut(values, q=bins, duplicates="drop")
        except ValueError as exc:
            raise AppError(422, "BINNING_FAILED",
                           f"Découpage par quantiles impossible : {exc}. "
                           "La colonne a probablement trop de valeurs identiques.")
        description = f"{bins} classes d'effectifs égaux (quantiles)"
    elif method == "custom":
        edges = params.get("edges") or []
        if len(edges) < 2:
            raise AppError(400, "INVALID_EDGES", "Fournissez au moins deux bornes de découpage.")
        edges = sorted(float(e) for e in edges)
        result = pd.cut(values, bins=edges, include_lowest=True)
        description = f"classes définies par les bornes {edges}"
    else:
        raise AppError(400, "UNKNOWN_BINNING_METHOD", f"Méthode de découpage inconnue : {method}")

    if params.get("as_label", True):
        # Les valeurs hors classe (issues de cellules vides) doivent rester
        # nulles : `astype(str)` les transformerait en la chaîne « nan ».
        missing = result.isna()
        labels = result.astype(str).astype(object)
        labels[missing] = None
        result = labels
    else:
        result = result.cat.codes.replace(-1, np.nan)
    return result, description


def _encoding(df: pd.DataFrame, source: str, params: dict) -> tuple[Any, str]:
    _require(df, source)
    method = params.get("method", "label")
    series = df[source]

    if method == "label":
        categories = series.astype("category")
        codes = categories.cat.codes.replace(-1, np.nan)
        mapping = {str(c): i for i, c in enumerate(categories.cat.categories)}
        return codes, f"encodage ordinal ({len(mapping)} modalités, ordre alphabétique)"

    if method == "frequency":
        counts = series.map(series.value_counts())
        return counts, "encodage par fréquence (effectif de chaque modalité)"

    if method == "onehot":
        levels = int(series.nunique(dropna=True))
        if levels > MAX_ONEHOT_LEVELS:
            raise AppError(422, "TOO_MANY_LEVELS",
                           f"L'encodage one-hot créerait {levels} colonnes (maximum {MAX_ONEHOT_LEVELS}). "
                           "Regroupez les modalités rares avant d'encoder.")
        dummies = pd.get_dummies(series, prefix=source, dtype=int)
        return dummies, f"encodage one-hot ({levels} colonnes indicatrices)"

    raise AppError(400, "UNKNOWN_ENCODING_METHOD", f"Méthode d'encodage inconnue : {method}")


def _lag(df: pd.DataFrame, source: str, params: dict) -> tuple[pd.Series, str]:
    _require(df, source)
    periods = int(params.get("periods", 1))
    if periods == 0:
        raise AppError(400, "INVALID_PERIODS", "Le décalage doit être différent de zéro.")
    group_by = params.get("group_by")

    if group_by:
        _require(df, group_by)
        result = df.groupby(group_by, dropna=False, observed=True)[source].shift(periods)
        suffix = f", indépendamment dans chaque groupe de '{group_by}'"
    else:
        result = df[source].shift(periods)
        suffix = ""

    direction = "vers le bas" if periods > 0 else "vers le haut"
    return result, f"décalage de {abs(periods)} ligne(s) {direction}{suffix}"


def _rolling(df: pd.DataFrame, source: str, params: dict) -> tuple[pd.Series, str]:
    values = _require_numeric(df, source)
    window = int(params.get("window", 3))
    function = params.get("function", "mean")
    if window < 2:
        raise AppError(400, "INVALID_WINDOW", "La fenêtre doit compter au moins 2 lignes.")
    if window > df.shape[0]:
        raise AppError(422, "WINDOW_TOO_LARGE",
                       f"La fenêtre ({window}) dépasse le nombre de lignes ({df.shape[0]}).")
    if function not in ROLLING_FUNCS:
        raise AppError(400, "UNKNOWN_ROLLING_FUNCTION",
                       f"Fonction inconnue : {function}. Disponibles : {', '.join(sorted(ROLLING_FUNCS))}.")

    min_periods = int(params.get("min_periods", window))
    center = bool(params.get("center", False))
    group_by = params.get("group_by")

    if group_by:
        _require(df, group_by)
        frame = pd.DataFrame({"value": values, "group": df[group_by]})
        rolled = frame.groupby("group", dropna=False, observed=True)["value"].transform(
            lambda s: getattr(s.rolling(window=window, min_periods=min_periods, center=center), function)()
        )
        suffix = f", indépendamment dans chaque groupe de '{group_by}'"
    else:
        rolled = getattr(values.rolling(window=window, min_periods=min_periods, center=center), function)()
        suffix = ""

    position = "centrée" if center else "sur les lignes précédentes"
    return rolled, f"{function} sur une fenêtre glissante de {window} lignes, {position}{suffix}"


TRANSFORMS = {
    "binning": _binning,
    "encoding": _encoding,
    "lag": _lag,
    "rolling": _rolling,
}


def apply_transform(session, transform: str, source: str, params: dict,
                    new_name: Optional[str], replace: bool) -> dict[str, Any]:
    df = session.df
    if transform not in TRANSFORMS:
        raise AppError(400, "UNKNOWN_TRANSFORM", f"Transformation inconnue : {transform}")

    result, description = TRANSFORMS[transform](df, source, params or {})

    # L'encodage one-hot produit plusieurs colonnes d'un coup.
    if isinstance(result, pd.DataFrame):
        if df.shape[1] + result.shape[1] > MAX_NEW_COLUMNS + df.shape[1]:  # pragma: no cover - borne large
            raise AppError(422, "TOO_MANY_COLUMNS", "Trop de colonnes seraient créées.")
        for column in result.columns:
            if column in df.columns and not replace:
                raise AppError(409, "COLUMN_ALREADY_EXISTS",
                               f"La colonne '{column}' existe déjà. Autorisez le remplacement ou renommez.")
        for column in result.columns:
            df[column] = result[column]
        created = [str(c) for c in result.columns]
    else:
        target = (new_name or f"{source}_{transform}").strip()
        _check_name_available(df, target, replace)
        df[target] = result
        created = [target]

    _refresh_filter(session)
    state = _columns_state(session)
    state["created_columns"] = created
    state["description"] = description
    state["preview"] = [
        {str(k): (None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.number)) else str(v)))
         for k, v in row.items()}
        for row in df[[source, *created]].head(10).to_dict(orient="records")
    ]
    state["null_count"] = {column: int(df[column].isna().sum()) for column in created}
    return state
