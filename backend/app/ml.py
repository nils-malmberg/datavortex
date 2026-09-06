"""Analyses de Machine Learning (Phase 7, étendu en Phase 8.1) : régression,
classification, clustering et réduction de dimension. Basé sur scikit-learn.

Chaque fonction `run_*` retourne un dict de résultats (nombres, tableaux
JSON-safe) plus une clé interne `_fig` (objet `plotly.graph_objects.Figure`,
la visualisation principale), éventuellement `_extra_figs` (dict de figures
secondaires, ex: importance des variables, courbe du coude, résidus), et pour
les modèles supervisés `_model` (l'estimateur entraîné, pour export Phase 8.1)
+ `_model_meta` (dict décrivant le modèle pour le registre de session). Ces
clés internes sont retirées et converties en JSON par la couche API
(`app.main._finalize_ml_result`) ou consommées directement par le générateur
de rapport PDF (`app.report`) pour l'export en image.
"""
from __future__ import annotations

import base64
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.cluster.hierarchy import dendrogram, linkage
from sklearn.base import clone
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans, MeanShift, estimate_bandwidth
from sklearn.decomposition import PCA
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
    StackingClassifier,
    VotingClassifier,
)
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, LogisticRegression, Ridge
from sklearn.manifold import TSNE
from sklearn.metrics import (
    accuracy_score,
    calinski_harabasz_score,
    confusion_matrix,
    davies_bouldin_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
    roc_auc_score,
    roc_curve,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelBinarizer, PolynomialFeatures, StandardScaler
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier

from app.errors import AppError
from app.parsing import detect_column_type

PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
]

TEST_SIZE = 0.25
RANDOM_STATE = 42
MIN_SAMPLES_FOR_CV = 15
MIN_SAMPLES_FOR_PERMUTATION = 20

# Certains algorithmes ont une complexité quadratique ou cubique en nombre de
# lignes (noyau RBF, processus gaussien, classification hiérarchique) : sans
# garde-fou, une exécution sur un fichier de 100k lignes prend des dizaines de
# minutes voire épuise la mémoire, plutôt que d'échouer proprement.
MAX_SAMPLES_KERNEL_METHOD = 15_000  # SVR / SVM (noyau RBF/poly) : O(n²) à O(n³)
MAX_SAMPLES_GPR = 5_000  # processus gaussien : inversion de matrice O(n³)
MAX_SAMPLES_HIERARCHICAL = 5_000  # linkage scipy : matrice de distances O(n²) en mémoire
MAX_SAMPLES_SILHOUETTE = 5_000  # silhouette_score : distances par paire, O(n²) en temps
MAX_SAMPLES_DENSITY_CLUSTERING = 30_000  # DBSCAN : dégrade si eps couvre une grande partie du nuage
MAX_SAMPLES_MEAN_SHIFT = 3_000  # mean shift : convergence lente par point, ne passe pas à l'échelle

# Random Forest sans limite de profondeur construit des arbres jusqu'à isoler
# chaque ligne individuellement : sur 100k lignes, cela mesure plusieurs
# dizaines de secondes par arbre. Une profondeur par défaut qui grandit avec
# le nombre de lignes (au lieu de "illimitée") garde des temps de réponse
# raisonnables, reste ajustable via le paramètre max_depth explicite.
def _default_forest_depth(n_samples: int) -> int | None:
    if n_samples <= 5_000:
        return None
    if n_samples <= 20_000:
        return 20
    return 12


def _forest_n_jobs(n_samples: int) -> int | None:
    """Le parallélisme a un coût fixe (lancement du pool de threads) qui
    dépasse le gain sur un petit jeu de données : ne paralléliser qu'à partir
    d'une taille où la construction des arbres domine ce coût."""
    return -1 if n_samples > 5_000 else None


def _require_sample_limit(n_samples: int, limit: int, method_label: str) -> None:
    if n_samples > limit:
        raise AppError(
            422,
            "TOO_MANY_SAMPLES",
            f"{method_label} n'est pas adapté à {n_samples} lignes (limite {limit} pour rester réactif : "
            "cette méthode a une complexité qui croît au moins comme le carré du nombre de lignes). "
            "Filtrez le jeu de données, ou choisissez une méthode qui passe mieux à l'échelle "
            "(random forest, gradient boosting).",
        )


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


def _sorted_importance(feature_names, values) -> list[dict]:
    return sorted(
        [{"feature": str(f), "importance": float(v)} for f, v in zip(feature_names, values)],
        key=lambda d: d["importance"], reverse=True,
    )


def _permutation_feature_importance(model, X, y, scoring, feature_names, n_repeats=8) -> list[dict] | None:
    """Importance par permutation : fonctionne avec n'importe quel estimateur/pipeline
    déjà entraîné exposant `.predict`, y compris SVR/GPR/KNN/réseaux de neurones,
    pour qui aucune importance native n'existe."""
    if len(X) < MIN_SAMPLES_FOR_PERMUTATION:
        return None
    result = permutation_importance(
        model, X, y, scoring=scoring, n_repeats=n_repeats, random_state=RANDOM_STATE,
    )
    return _sorted_importance(feature_names, result.importances_mean)


def _cross_validate(estimator, X, y, scoring, n_samples) -> dict | None:
    """Score de validation croisée (moyenne + écart-type + scores par pli), pour
    donner une idée de la variabilité plutôt qu'un seul chiffre sur-optimiste."""
    if n_samples < MIN_SAMPLES_FOR_CV:
        return None
    cv = min(5, max(2, n_samples // 5))
    try:
        scores = cross_val_score(clone(estimator), X, y, cv=cv, scoring=scoring)
    except ValueError:
        return None
    return {
        "cv": int(cv),
        "mean": float(scores.mean()),
        "std": float(scores.std()),
        "scores": [float(s) for s in scores],
    }


def _residuals_figure(y_pred: np.ndarray, residuals: np.ndarray) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y_pred, y=residuals, mode="markers", marker=dict(color=PALETTE[0], opacity=0.7), name="Résidus",
    ))
    fig.add_hline(y=0, line=dict(color=PALETTE[3], dash="dash"))
    fig.update_layout(title="Résidus vs valeurs prédites", xaxis_title="Valeur prédite", yaxis_title="Résidu")
    return fig


def _importance_figure(feature_importance: list[dict], title: str) -> go.Figure:
    ordered = feature_importance[::-1]  # barh : le plus important en haut
    fig = go.Figure(go.Bar(
        x=[d["importance"] for d in ordered], y=[d["feature"] for d in ordered],
        orientation="h", marker_color=PALETTE[0],
    ))
    fig.update_layout(title=title, xaxis_title="Importance", yaxis_title="")
    return fig


# --------------------------------------------------------------------------
# Régression
# --------------------------------------------------------------------------

def run_regression(
    df: pd.DataFrame, features: list[str], target: str, model_type: str, degree: int = 2,
    params: dict | None = None,
) -> dict:
    params = params or {}
    if not features:
        raise AppError(400, "MISSING_FEATURES", "Au moins une colonne de features est requise.")
    _require_numeric_columns(df, [*features, target])
    subset = _clean_subset(df, [*features, target])
    X = subset[features]
    y = subset[target]
    n = len(subset)

    if model_type == "polynomial":
        degree = max(1, min(10, int(params.get("degree", degree))))
        model = Pipeline([
            ("poly", PolynomialFeatures(degree=degree, include_bias=False)),
            ("linreg", LinearRegression()),
        ])
    elif model_type == "linear":
        model = LinearRegression()
    elif model_type == "ridge":
        model = Ridge(alpha=float(params.get("alpha", 1.0)))
    elif model_type == "lasso":
        model = Lasso(alpha=float(params.get("alpha", 1.0)))
    elif model_type == "elastic_net":
        model = ElasticNet(alpha=float(params.get("alpha", 1.0)), l1_ratio=float(params.get("l1_ratio", 0.5)))
    elif model_type == "svr":
        _require_sample_limit(n, MAX_SAMPLES_KERNEL_METHOD, "La régression à vecteurs de support (SVR)")
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("svr", SVR(
                kernel=params.get("kernel", "rbf"), C=float(params.get("C", 1.0)),
                epsilon=float(params.get("epsilon", 0.1)),
            )),
        ])
    elif model_type == "gpr":
        _require_sample_limit(n, MAX_SAMPLES_GPR, "Le processus gaussien")
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("gpr", GaussianProcessRegressor(
                normalize_y=True, random_state=RANDOM_STATE, alpha=float(params.get("alpha", 1e-6)),
            )),
        ])
    elif model_type == "gradient_boosting":
        model = GradientBoostingRegressor(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.1)),
            random_state=RANDOM_STATE,
        )
    elif model_type == "random_forest":
        model = RandomForestRegressor(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=params.get("max_depth") or _default_forest_depth(n),
            random_state=RANDOM_STATE,
            n_jobs=_forest_n_jobs(n),
        )
    else:
        raise AppError(400, "UNKNOWN_MODEL_TYPE", f"Type de modèle inconnu : {model_type}")

    model.fit(X, y)
    y_pred = model.predict(X)

    r2 = float(r2_score(y, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y, y_pred)))
    mae = float(mean_absolute_error(y, y_pred))

    equation = None
    coefficients = None
    linear_family = model_type in ("linear", "ridge", "lasso", "elastic_net")
    if linear_family:
        if len(features) == 1:
            equation = f"{target} = {model.coef_[0]:.4f} × {features[0]} + {model.intercept_:.4f}"
        else:
            terms = " + ".join(f"{c:.4f}·{f}" for c, f in zip(model.coef_, features))
            equation = f"{target} = {terms} + {model.intercept_:.4f}"
        coefficients = [{"feature": f, "coefficient": float(c)} for f, c in zip(features, model.coef_)]
    elif model_type == "polynomial":
        linreg = model.named_steps["linreg"]
        if len(features) == 1:
            terms = " + ".join(f"{c:.4f}·{features[0]}^{i + 1}" for i, c in enumerate(linreg.coef_))
            equation = f"{target} = {terms} + {linreg.intercept_:.4f}"
        else:
            equation = f"Régression polynomiale (degré {degree}) sur {len(features)} variables"

    if model_type in ("gradient_boosting", "random_forest"):
        feature_importance = _sorted_importance(features, model.feature_importances_)
    elif linear_family:
        coefs = np.abs(model.coef_)
        total = coefs.sum() or 1.0
        feature_importance = _sorted_importance(features, coefs / total)
    else:
        feature_importance = _permutation_feature_importance(model, X, y, "r2", features)

    cross_val = _cross_validate(model, X, y, "r2", n)

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

    residuals = y.to_numpy() - y_pred
    extra_figs = {"residuals": _residuals_figure(y_pred, residuals)}
    if feature_importance:
        extra_figs["feature_importance"] = _importance_figure(feature_importance, "Importance des variables")

    predictions = [
        {"actual": float(a), "predicted": float(p)}
        for a, p in list(zip(y.tolist(), y_pred.tolist()))[:500]
    ]

    return {
        "equation": equation,
        "r2": r2,
        "rmse": rmse,
        "mae": mae,
        "n_samples": n,
        "predictions": predictions,
        "coefficients": coefficients,
        "feature_importance": feature_importance,
        "cross_validation": cross_val,
        "_fig": fig,
        "_extra_figs": extra_figs,
        "_model": model,
        "_model_meta": {
            "feature_names": features,
            "target_name": target,
            "target_classes": None,
            "encoded_columns": None,
            "config": {"model_type": model_type, "degree": degree if model_type == "polynomial" else None, **params},
            "performance": {"r2": r2, "rmse": rmse, "mae": mae, "cross_validation": cross_val},
            "feature_importance": feature_importance,
            "n_train": n,
            "n_test": 0,
            "dataset_shape": (int(df.shape[0]), int(df.shape[1])),
        },
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


def _roc_data(model, X_test, y_test, labels: list[str]) -> dict | None:
    """Courbe(s) ROC + AUC. Multiclasse : une courbe par classe (one-vs-rest)
    plus une AUC macro-moyenne, comme scikit-learn le recommande."""
    if not hasattr(model, "predict_proba"):
        return None
    try:
        proba = model.predict_proba(X_test)
    except Exception:
        return None

    binarizer = LabelBinarizer()
    y_bin = binarizer.fit_transform(y_test)
    if len(labels) == 2:
        # LabelBinarizer réduit le binaire à une seule colonne : on la reconstruit.
        y_bin = np.column_stack([1 - y_bin.ravel(), y_bin.ravel()])
    class_order = [str(c) for c in binarizer.classes_] if len(labels) > 2 else labels

    curves = []
    aucs = []
    for i, label in enumerate(class_order):
        col = proba[:, i] if proba.shape[1] == len(class_order) else proba[:, 0]
        fpr, tpr, _ = roc_curve(y_bin[:, i], col)
        try:
            class_auc = float(roc_auc_score(y_bin[:, i], col))
        except ValueError:
            continue
        aucs.append(class_auc)
        curves.append({"label": label, "fpr": fpr.tolist(), "tpr": tpr.tolist(), "auc": class_auc})

    if not curves:
        return None
    return {"curves": curves, "macro_auc": float(np.mean(aucs))}


def _roc_figure(roc: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#94a3b8", dash="dash"), name="Hasard"))
    for i, curve in enumerate(roc["curves"]):
        fig.add_trace(go.Scatter(
            x=curve["fpr"], y=curve["tpr"], mode="lines",
            name=f"{curve['label']} (AUC={curve['auc']:.3f})",
            line=dict(color=PALETTE[i % len(PALETTE)]),
        ))
    fig.update_layout(title="Courbe ROC", xaxis_title="Taux de faux positifs", yaxis_title="Taux de vrais positifs")
    return fig


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
        model = DecisionTreeClassifier(max_depth=params.get("max_depth", 4), random_state=RANDOM_STATE)
    elif model_type == "random_forest":
        model = RandomForestClassifier(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=params.get("max_depth") or _default_forest_depth(len(X)),
            random_state=RANDOM_STATE,
            n_jobs=_forest_n_jobs(len(X)),
        )
    elif model_type == "svm":
        _require_sample_limit(len(X), MAX_SAMPLES_KERNEL_METHOD, "Le SVM (machine à vecteurs de support)")
        model = SVC(
            kernel=params.get("kernel", "rbf"), C=float(params.get("C", 1.0)),
            probability=True, random_state=RANDOM_STATE,
        )
    elif model_type == "gradient_boosting":
        model = GradientBoostingClassifier(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=int(params.get("max_depth", 3)),
            learning_rate=float(params.get("learning_rate", 0.1)),
            random_state=RANDOM_STATE,
        )
    elif model_type == "knn":
        model = KNeighborsClassifier(n_neighbors=int(params.get("k", 5)))
    elif model_type == "naive_bayes":
        model = GaussianNB()
    elif model_type == "mlp":
        model = MLPClassifier(
            hidden_layer_sizes=tuple(params.get("hidden_layer_sizes", [32])),
            max_iter=int(params.get("max_iter", 500)),
            random_state=RANDOM_STATE,
        )
    elif model_type == "voting":
        model = VotingClassifier(estimators=[
            ("logistic", LogisticRegression(max_iter=1000)),
            ("random_forest", RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)),
            ("naive_bayes", GaussianNB()),
        ], voting="soft")
    elif model_type == "stacking":
        model = StackingClassifier(estimators=[
            ("logistic", LogisticRegression(max_iter=1000)),
            ("random_forest", RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE)),
            ("knn", KNeighborsClassifier(n_neighbors=5)),
        ], final_estimator=LogisticRegression(max_iter=1000))
    else:
        raise AppError(400, "UNKNOWN_MODEL_TYPE", f"Type de modèle inconnu : {model_type}")

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, y_pred))
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="weighted", zero_division=0,
    )

    labels = sorted(y.unique().tolist())
    cm = confusion_matrix(y_test, y_pred, labels=labels)

    if model_type == "logistic":
        coefs = np.atleast_2d(model.coef_)
        importance = np.abs(coefs).mean(axis=0)
        feature_importance = _sorted_importance(X.columns, importance)
    elif model_type in ("decision_tree", "random_forest", "gradient_boosting"):
        feature_importance = _sorted_importance(X.columns, model.feature_importances_)
    else:
        feature_importance = _permutation_feature_importance(model, X_test, y_test, "accuracy", X.columns)

    if model_type == "decision_tree":
        tree_image_base64 = _decision_tree_image_base64(model, X.columns, model.classes_)

    cross_val = _cross_validate(model, X, y, "accuracy", len(X))
    roc = _roc_data(model, X_test, y_test, labels)

    cm_fig = go.Figure(go.Heatmap(
        z=cm, x=[str(label) for label in labels], y=[str(label) for label in labels],
        colorscale="Blues", text=cm, texttemplate="%{text}", showscale=False,
    ))
    cm_fig.update_layout(
        title="Matrice de confusion", xaxis_title="Prédit", yaxis_title="Réel",
        yaxis=dict(autorange="reversed"),
    )

    extra_figs = {}
    if feature_importance:
        extra_figs["feature_importance"] = _importance_figure(feature_importance, "Importance des variables")
    if roc:
        extra_figs["roc"] = _roc_figure(roc)

    return {
        "accuracy": accuracy,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "confusion_matrix": {"labels": [str(label) for label in labels], "matrix": cm.tolist()},
        "feature_importance": feature_importance,
        "cross_validation": cross_val,
        "roc_auc": roc["macro_auc"] if roc else None,
        "tree_image_base64": tree_image_base64,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "_fig": cm_fig,
        "_extra_figs": extra_figs,
        "_model": model,
        "_model_meta": {
            "feature_names": features,
            "target_name": target,
            "target_classes": labels,
            "encoded_columns": list(X.columns),
            "config": {"model_type": model_type, **params},
            "performance": {
                "accuracy": accuracy, "precision": float(precision), "recall": float(recall), "f1": float(f1),
                "roc_auc": roc["macro_auc"] if roc else None, "cross_validation": cross_val,
            },
            "feature_importance": feature_importance,
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "dataset_shape": (int(df.shape[0]), int(df.shape[1])),
        },
    }


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------

MAX_DENDROGRAM_LABELS = 40  # au-delà, les étiquettes de feuilles se chevauchent et deviennent illisibles


def _dendrogram_figure(Z: np.ndarray, labels: list[str]) -> go.Figure:
    """Reconstruit le dendrogramme scipy en figure Plotly (segments de droite)."""
    dendro = dendrogram(Z, no_plot=True, labels=labels)
    fig = go.Figure()
    for xs, ys in zip(dendro["icoord"], dendro["dcoord"]):
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=PALETTE[0]), showlegend=False))
    tick_positions = [5 + 10 * i for i in range(len(dendro["ivl"]))]
    show_labels = len(dendro["ivl"]) <= MAX_DENDROGRAM_LABELS
    xaxis = (
        dict(tickmode="array", tickvals=tick_positions, ticktext=dendro["ivl"], tickangle=45)
        if show_labels
        else dict(tickmode="array", tickvals=[], ticktext=[])
    )
    fig.update_layout(
        title="Dendrogramme (classification hiérarchique)",
        xaxis={**xaxis, "title": None if show_labels else f"{len(dendro['ivl'])} échantillons (étiquettes masquées : trop nombreuses)"},
        yaxis_title="Distance",
    )
    return fig


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
    n = len(X_scaled)

    dendrogram_fig = None
    if model_type == "kmeans":
        k = int(params.get("k", 3))
        if k < 2:
            raise AppError(400, "INVALID_PARAM", "Le nombre de clusters k doit être supérieur ou égal à 2.")
        if k >= n:
            raise AppError(400, "INVALID_PARAM", "k doit être inférieur au nombre de lignes disponibles.")
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = model.fit_predict(X_scaled)
    elif model_type == "dbscan":
        # Ball-tree normalement sous-quadratique, mais dégénère vers un
        # comportement proche de O(n²) si eps couvre une grande partie du
        # nuage de points (données très denses) : garde-fou par prudence.
        _require_sample_limit(n, MAX_SAMPLES_DENSITY_CLUSTERING, "DBSCAN")
        model = DBSCAN(eps=float(params.get("eps", 0.5)), min_samples=int(params.get("min_samples", 5)))
        labels = model.fit_predict(X_scaled)
    elif model_type in ("hierarchical", "agglomerative"):
        label = "La classification hiérarchique" if model_type == "hierarchical" else "Le clustering agglomératif"
        _require_sample_limit(n, MAX_SAMPLES_HIERARCHICAL, label)
        k = int(params.get("k", 3))
        if k < 2 or k >= n:
            raise AppError(400, "INVALID_PARAM", "k doit être compris entre 2 et le nombre de lignes - 1.")
        linkage_method = params.get("linkage", "ward")
        model = AgglomerativeClustering(n_clusters=k, linkage=linkage_method)
        labels = model.fit_predict(X_scaled)
        if model_type == "hierarchical":
            max_points = 200  # un dendrogramme au-delà devient illisible et très lent à calculer
            if n <= max_points:
                Z = linkage(X_scaled, method=linkage_method)
                dendrogram_fig = _dendrogram_figure(Z, [str(i) for i in subset.index])
    elif model_type == "gmm":
        k = int(params.get("k", 3))
        if k < 2 or k >= n:
            raise AppError(400, "INVALID_PARAM", "k doit être compris entre 2 et le nombre de lignes - 1.")
        model = GaussianMixture(n_components=k, random_state=RANDOM_STATE)
        labels = model.fit_predict(X_scaled)
    elif model_type == "mean_shift":
        # Mean shift converge lentement sur des données denses (chaque point
        # itère jusqu'à convergence vers un mode local) : ne passe pas à
        # l'échelle, y compris sur des tailles où DBSCAN reste rapide.
        _require_sample_limit(n, MAX_SAMPLES_MEAN_SHIFT, "Mean Shift")
        bandwidth = params.get("bandwidth")
        bandwidth = float(bandwidth) if bandwidth else estimate_bandwidth(X_scaled, random_state=RANDOM_STATE)
        if bandwidth <= 0:
            bandwidth = 1.0
        model = MeanShift(bandwidth=bandwidth)
        labels = model.fit_predict(X_scaled)
    else:
        raise AppError(400, "UNKNOWN_MODEL_TYPE", f"Type de modèle inconnu : {model_type}")

    n_clusters_found = len(set(labels)) - (1 if -1 in labels else 0)
    silhouette = davies_bouldin = calinski_harabasz = None
    if 2 <= n_clusters_found < n:
        try:
            # silhouette_score est en O(n²) (distances par paire) : sur un
            # gros jeu de données, calculé sur un sous-échantillon plutôt que
            # sur toutes les lignes -- c'est l'usage documenté de scikit-learn
            # pour ce cas, la valeur reste représentative. Davies-Bouldin et
            # Calinski-Harabasz n'ont pas ce problème (juste les centroïdes).
            sample_size = MAX_SAMPLES_SILHOUETTE if n > MAX_SAMPLES_SILHOUETTE else None
            silhouette = float(silhouette_score(X_scaled, labels, sample_size=sample_size, random_state=RANDOM_STATE))
            davies_bouldin = float(davies_bouldin_score(X_scaled, labels))
            calinski_harabasz = float(calinski_harabasz_score(X_scaled, labels))
        except ValueError:
            pass

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

    cluster_sizes = [{"cluster": ("Bruit" if lab == -1 else f"Cluster {lab}"), "count": int((labels == lab).sum())}
                      for lab in sorted(set(labels))]

    extra_figs = {}
    if model_type == "kmeans":
        max_k = min(10, n - 1)
        if max_k >= 2:
            ks = list(range(1, max_k + 1))
            # n_init réduit à 3 (vs 10 pour le clustering final) : la courbe du
            # coude n'a besoin que de la tendance générale, pas de l'optimum
            # exact, et ce calcul refait déjà 10 fits (un par k testé).
            inertias = [KMeans(n_clusters=kk, random_state=RANDOM_STATE, n_init=3).fit(X_scaled).inertia_ for kk in ks]
            elbow_fig = go.Figure(go.Scatter(x=ks, y=inertias, mode="lines+markers", marker_color=PALETTE[0]))
            elbow_fig.update_layout(title="Courbe du coude", xaxis_title="Nombre de clusters (k)", yaxis_title="Inertie")
            extra_figs["elbow_curve"] = elbow_fig
    if dendrogram_fig is not None:
        extra_figs["dendrogram"] = dendrogram_fig

    return {
        "labels": [int(lab) for lab in labels],
        "n_clusters": int(n_clusters_found),
        "silhouette_score": silhouette,
        "davies_bouldin_score": davies_bouldin,
        "calinski_harabasz_score": calinski_harabasz,
        "cluster_sizes": cluster_sizes,
        "n_samples": n,
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
