"""Analyses de Machine Learning (Phase 7) : régression, classification,
clustering et réduction de dimension. Basé sur scikit-learn.

Chaque fonction `run_*` retourne un dict de résultats (nombres, tableaux
JSON-safe) plus une clé interne `_fig` (objet `plotly.graph_objects.Figure`,
la visualisation principale) et éventuellement `_extra_figs` (dict de
figures secondaires, ex: importance des variables, courbe du coude). Ces
clés internes sont retirées et converties en JSON par la couche API
(`app.main._finalize_ml_result`) ou consommées directement par le
générateur de rapport PDF (`app.report`) pour l'export en image.
"""
from __future__ import annotations

import base64
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.manifold import TSNE
from sklearn.metrics import accuracy_score, confusion_matrix, mean_squared_error, r2_score, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from app.errors import AppError
from app.parsing import detect_column_type

PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
]

TEST_SIZE = 0.25
RANDOM_STATE = 42


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col not in df.columns:
            raise AppError(404, "COLUMN_NOT_FOUND", f"Colonne '{col}' introuvable.")


def _require_numeric_columns(df: pd.DataFrame, columns: list[str]) -> None:
    _require_columns(df, columns)
    for col in columns:
        if detect_column_type(df[col]) not in ("integer", "float"):
            raise AppError(400, "INVALID_COLUMN_TYPE", f"La colonne '{col}' doit être numérique.")


def _clean_subset(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    subset = df[columns].dropna()
    if subset.empty:
        raise AppError(
            422,
            "INSUFFICIENT_DATA",
            "Aucune ligne complète (sans valeur manquante) pour les colonnes sélectionnées.",
        )
    return subset


def _encode_features(X: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode les colonnes non numériques (ex: 'Sex') pour les modèles scikit-learn."""
    categorical = [c for c in X.columns if detect_column_type(X[c]) not in ("integer", "float")]
    if categorical:
        X = pd.get_dummies(X, columns=categorical, drop_first=True)
    return X


# --------------------------------------------------------------------------
# Régression
# --------------------------------------------------------------------------

def run_regression(df: pd.DataFrame, features: list[str], target: str, model_type: str, degree: int = 2) -> dict:
    if not features:
        raise AppError(400, "MISSING_FEATURES", "Au moins une colonne de features est requise.")
    _require_numeric_columns(df, [*features, target])
    subset = _clean_subset(df, [*features, target])
    X = subset[features]
    y = subset[target]

    if model_type == "polynomial":
        degree = max(1, min(10, int(degree)))
        poly = PolynomialFeatures(degree=degree, include_bias=False)
        X_fit = poly.fit_transform(X)
        model = LinearRegression().fit(X_fit, y)
        y_pred = model.predict(X_fit)
    elif model_type == "linear":
        model = LinearRegression().fit(X, y)
        y_pred = model.predict(X)
    else:
        raise AppError(400, "UNKNOWN_MODEL_TYPE", f"Type de modèle inconnu : {model_type}")

    r2 = float(r2_score(y, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y, y_pred)))

    if model_type == "linear" and len(features) == 1:
        equation = f"{target} = {model.coef_[0]:.4f} × {features[0]} + {model.intercept_:.4f}"
    elif model_type == "linear":
        terms = " + ".join(f"{c:.4f}·{f}" for c, f in zip(model.coef_, features))
        equation = f"{target} = {terms} + {model.intercept_:.4f}"
    elif len(features) == 1:
        terms = " + ".join(f"{c:.4f}·{features[0]}^{i + 1}" for i, c in enumerate(model.coef_))
        equation = f"{target} = {terms} + {model.intercept_:.4f}"
    else:
        equation = f"Régression polynomiale (degré {degree}) sur {len(features)} variables"

    fig = go.Figure()
    if len(features) == 1:
        order = np.argsort(X[features[0]].to_numpy())
        x_vals = X[features[0]].to_numpy()
        fig.add_trace(go.Scatter(
            x=x_vals, y=y, mode="markers", name="Données",
            marker=dict(color=PALETTE[0], opacity=0.7),
        ))
        fig.add_trace(go.Scatter(
            x=x_vals[order], y=y_pred[order], mode="lines", name="Régression",
            line=dict(color=PALETTE[3], width=3),
        ))
        fig.update_layout(
            title=f"Régression {model_type} : {target} ~ {features[0]}",
            xaxis_title=features[0], yaxis_title=target,
        )
    else:
        fig.add_trace(go.Scatter(x=y, y=y_pred, mode="markers", marker=dict(color=PALETTE[0], opacity=0.7)))
        lo, hi = float(min(y.min(), y_pred.min())), float(max(y.max(), y_pred.max()))
        fig.add_trace(go.Scatter(
            x=[lo, hi], y=[lo, hi], mode="lines", name="Prédiction parfaite",
            line=dict(color=PALETTE[3], dash="dash"),
        ))
        fig.update_layout(
            title=f"Valeurs prédites vs réelles ({target})",
            xaxis_title="Valeur réelle", yaxis_title="Valeur prédite",
        )

    predictions = [
        {"actual": float(a), "predicted": float(p)}
        for a, p in list(zip(y.tolist(), y_pred.tolist()))[:500]
    ]

    return {
        "equation": equation,
        "r2": r2,
        "rmse": rmse,
        "n_samples": int(len(subset)),
        "predictions": predictions,
        "_fig": fig,
    }


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def _decision_tree_image_base64(model, feature_names, class_names) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.tree import plot_tree

    fig, ax = plt.subplots(figsize=(12, 8), dpi=110)
    plot_tree(
        model, feature_names=list(feature_names), class_names=[str(c) for c in class_names],
        filled=True, rounded=True, fontsize=8, ax=ax,
    )
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def run_classification(
    df: pd.DataFrame, features: list[str], target: str, model_type: str, params: dict | None = None,
) -> dict:
    params = params or {}
    if not features:
        raise AppError(400, "MISSING_FEATURES", "Au moins une colonne de features est requise.")
    _require_columns(df, [*features, target])
    subset = _clean_subset(df, [*features, target])

    X_raw = subset[features]
    y = subset[target].astype(str)
    X = _encode_features(X_raw)

    if y.nunique() < 2:
        raise AppError(422, "INSUFFICIENT_CLASSES", "La cible doit contenir au moins 2 classes distinctes.")

    can_stratify = y.value_counts().min() >= 2
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y if can_stratify else None,
    )

    tree_image_base64 = None
    if model_type == "logistic":
        model = LogisticRegression(max_iter=1000)
    elif model_type == "decision_tree":
        max_depth = params.get("max_depth", 4)
        model = DecisionTreeClassifier(max_depth=max_depth, random_state=RANDOM_STATE)
    elif model_type == "random_forest":
        model = RandomForestClassifier(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=params.get("max_depth"),
            random_state=RANDOM_STATE,
        )
    else:
        raise AppError(400, "UNKNOWN_MODEL_TYPE", f"Type de modèle inconnu : {model_type}")

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))

    labels = sorted(y.unique().tolist())
    cm = confusion_matrix(y_test, y_pred, labels=labels)

    if model_type == "logistic":
        coefs = np.atleast_2d(model.coef_)
        importance = np.abs(coefs).mean(axis=0)
    else:
        importance = model.feature_importances_
    feature_importance = sorted(
        [{"feature": c, "importance": float(v)} for c, v in zip(X.columns, importance)],
        key=lambda d: d["importance"], reverse=True,
    )

    if model_type == "decision_tree":
        tree_image_base64 = _decision_tree_image_base64(model, X.columns, model.classes_)

    cm_fig = go.Figure(go.Heatmap(
        z=cm, x=[str(label) for label in labels], y=[str(label) for label in labels],
        colorscale="Blues", text=cm, texttemplate="%{text}", showscale=False,
    ))
    cm_fig.update_layout(
        title="Matrice de confusion", xaxis_title="Prédit", yaxis_title="Réel",
        yaxis=dict(autorange="reversed"),
    )

    fi_fig = go.Figure(go.Bar(
        x=[d["importance"] for d in feature_importance],
        y=[d["feature"] for d in feature_importance],
        orientation="h", marker_color=PALETTE[0],
    ))
    fi_fig.update_layout(
        title="Importance des variables", xaxis_title="Importance", yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )

    return {
        "accuracy": accuracy,
        "confusion_matrix": {"labels": [str(label) for label in labels], "matrix": cm.tolist()},
        "feature_importance": feature_importance,
        "tree_image_base64": tree_image_base64,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "_fig": cm_fig,
        "_extra_figs": {"feature_importance": fi_fig},
    }


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------

def run_clustering(
    df: pd.DataFrame, features: list[str], model_type: str, params: dict | None = None,
    color_by: str | None = None,
) -> dict:
    params = params or {}
    if len(features) < 1:
        raise AppError(400, "MISSING_FEATURES", "Au moins une colonne de features est requise.")
    _require_numeric_columns(df, features)
    columns = [*features, color_by] if color_by else features
    subset = _clean_subset(df, columns)
    X = subset[features]
    X_scaled = StandardScaler().fit_transform(X)

    if model_type == "kmeans":
        k = int(params.get("k", 3))
        if k < 2:
            raise AppError(400, "INVALID_PARAM", "Le nombre de clusters k doit être supérieur ou égal à 2.")
        if k >= len(X_scaled):
            raise AppError(400, "INVALID_PARAM", "k doit être inférieur au nombre de lignes disponibles.")
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = model.fit_predict(X_scaled)
    elif model_type == "dbscan":
        eps = float(params.get("eps", 0.5))
        min_samples = int(params.get("min_samples", 5))
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(X_scaled)
    else:
        raise AppError(400, "UNKNOWN_MODEL_TYPE", f"Type de modèle inconnu : {model_type}")

    n_clusters_found = len(set(labels)) - (1 if -1 in labels else 0)
    silhouette = None
    if 2 <= n_clusters_found < len(X_scaled):
        try:
            silhouette = float(silhouette_score(X_scaled, labels))
        except ValueError:
            silhouette = None

    if len(features) >= 3:
        coords = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(X_scaled)
        axis_titles = ["Composante principale 1", "Composante principale 2"]
    elif len(features) == 2:
        coords = X_scaled
        axis_titles = features
    else:
        coords = np.column_stack([X_scaled[:, 0], np.zeros(len(X_scaled))])
        axis_titles = [features[0], ""]

    fig = go.Figure()
    for i, lab in enumerate(sorted(set(labels))):
        mask = labels == lab
        name = "Bruit" if lab == -1 else f"Cluster {lab}"
        fig.add_trace(go.Scatter(
            x=coords[mask, 0], y=coords[mask, 1], mode="markers", name=name,
            marker=dict(color=PALETTE[i % len(PALETTE)], opacity=0.75),
        ))
    fig.update_layout(
        title=f"Clustering ({model_type})", xaxis_title=axis_titles[0], yaxis_title=axis_titles[1],
    )

    extra_figs = {}
    if model_type == "kmeans":
        max_k = min(10, len(X_scaled) - 1)
        if max_k >= 2:
            ks = list(range(1, max_k + 1))
            inertias = [KMeans(n_clusters=kk, random_state=RANDOM_STATE, n_init=10).fit(X_scaled).inertia_ for kk in ks]
            elbow_fig = go.Figure(go.Scatter(x=ks, y=inertias, mode="lines+markers", marker_color=PALETTE[0]))
            elbow_fig.update_layout(title="Courbe du coude", xaxis_title="Nombre de clusters (k)", yaxis_title="Inertie")
            extra_figs["elbow_curve"] = elbow_fig

    return {
        "labels": [int(lab) for lab in labels],
        "n_clusters": int(n_clusters_found),
        "silhouette_score": silhouette,
        "n_samples": int(len(subset)),
        "_fig": fig,
        "_extra_figs": extra_figs,
    }


# --------------------------------------------------------------------------
# Réduction de dimension (PCA / t-SNE)
# --------------------------------------------------------------------------

def run_dimensionality_reduction(
    df: pd.DataFrame, features: list[str], n_components: int, method: str, color_by: str | None = None,
) -> dict:
    if len(features) < 2:
        raise AppError(400, "MISSING_FEATURES", "Au moins 2 colonnes de features sont requises.")
    if n_components not in (2, 3):
        raise AppError(400, "INVALID_PARAM", "n_components doit être 2 ou 3.")
    _require_numeric_columns(df, features)
    columns = [*features, color_by] if color_by else features
    subset = _clean_subset(df, columns)
    X = subset[features]
    X_scaled = StandardScaler().fit_transform(X)

    explained_variance = None
    if method == "pca":
        if n_components > len(features):
            raise AppError(400, "INVALID_PARAM", "n_components ne peut pas dépasser le nombre de features.")
        model = PCA(n_components=n_components, random_state=RANDOM_STATE)
        transformed = model.fit_transform(X_scaled)
        explained_variance = [float(v) for v in model.explained_variance_ratio_]
    elif method == "tsne":
        perplexity = float(min(30, max(5, (len(X_scaled) - 1) // 3)))
        model = TSNE(n_components=n_components, random_state=RANDOM_STATE, perplexity=perplexity, init="pca")
        transformed = model.fit_transform(X_scaled)
    elif method == "umap":
        raise AppError(
            501,
            "METHOD_NOT_AVAILABLE",
            "UMAP n'est pas disponible sur ce serveur (dépendance 'umap-learn' non installée). "
            "Utilisez PCA ou t-SNE.",
        )
    else:
        raise AppError(400, "UNKNOWN_METHOD", f"Méthode inconnue : {method}")

    color_values = subset[color_by] if color_by else None
    is_categorical_color = color_values is not None and detect_column_type(color_values) not in ("integer", "float")

    fig = go.Figure()
    scatter_cls = go.Scatter3d if n_components == 3 else go.Scatter
    if is_categorical_color:
        for i, val in enumerate(sorted(color_values.unique().tolist(), key=str)):
            mask = (color_values == val).to_numpy()
            coords = dict(x=transformed[mask, 0], y=transformed[mask, 1])
            if n_components == 3:
                coords["z"] = transformed[mask, 2]
            fig.add_trace(scatter_cls(
                **coords, mode="markers", name=str(val),
                marker=dict(size=4, color=PALETTE[i % len(PALETTE)]),
            ))
    else:
        coords = dict(x=transformed[:, 0], y=transformed[:, 1])
        if n_components == 3:
            coords["z"] = transformed[:, 2]
        marker = dict(size=4, color=PALETTE[0])
        if color_values is not None:
            marker = dict(size=4, color=color_values, colorscale="Viridis", showscale=True)
        fig.add_trace(scatter_cls(**coords, mode="markers", marker=marker))

    axis_titles = [f"Dimension {i + 1}" for i in range(n_components)]
    title = f"{method.upper()} ({n_components}D)"
    if n_components == 3:
        fig.update_layout(title=title, scene=dict(
            xaxis_title=axis_titles[0], yaxis_title=axis_titles[1], zaxis_title=axis_titles[2],
        ))
    else:
        fig.update_layout(title=title, xaxis_title=axis_titles[0], yaxis_title=axis_titles[1])

    return {
        "transformed_data": [row[:n_components] for row in transformed.tolist()[:1000]],
        "explained_variance": explained_variance,
        "n_samples": int(len(subset)),
        "_fig": fig,
    }
