"""Export de modèles ML entraînés (Phase 8.1) : joblib / pickle / JSON / ONNX /
TFLite, métadonnées de reproductibilité, et notebook de ré-entraînement.

Les fichiers sont renvoyés en mémoire (bytes) à l'API, qui les sert comme
n'importe quel autre export de l'application (CSV, PDF...) : c'est le
frontend (Phase 8.1, étape 3 — dialogues d'enregistrement) qui décide où les
écrire, jamais le serveur. Aucune route n'accepte de chemin de fichier fourni
par le client.
"""
from __future__ import annotations

import hashlib
import io
import json
import pickle
from datetime import datetime
from typing import Any

import joblib
import numpy as np

from app.errors import AppError
from app.ml_registry import TrainedModel

LINEAR_MODEL_TYPES = {"linear", "ridge", "lasso", "elastic_net", "logistic"}
TREE_MODEL_TYPES = {"decision_tree"}

FORMAT_EXTENSIONS = {"joblib": "joblib", "pickle": "pkl", "json": "json", "onnx": "onnx", "tflite": "tflite"}
FORMAT_MEDIA_TYPES = {
    "joblib": "application/octet-stream",
    "pickle": "application/octet-stream",
    "json": "application/json",
    "onnx": "application/octet-stream",
    "tflite": "application/octet-stream",
}


def _bundle(model: TrainedModel) -> dict:
    return {
        "model": model.estimator,
        "feature_names": model.feature_names,
        "encoded_columns": model.encoded_columns,
        "target_name": model.target_name,
        "target_classes": model.target_classes,
        "task": model.task,
        "model_type": model.model_type,
        "config": model.config,
    }


def _tree_to_dict(tree, feature_names: list[str], node: int = 0) -> dict:
    """Sérialise récursivement un arbre scikit-learn (`estimator.tree_`) en un
    dict JSON : seuls les modèles à arbre unique (decision_tree) sont exportés
    fidèlement ; les ensembles (random_forest, gradient_boosting) contiennent
    trop d'arbres pour rester lisibles et sont couverts par joblib/ONNX."""
    left, right = tree.children_left[node], tree.children_right[node]
    if left == right:  # feuille
        value = tree.value[node].tolist()
        return {"leaf": True, "value": value, "n_samples": int(tree.n_node_samples[node])}
    return {
        "leaf": False,
        "feature": feature_names[tree.feature[node]],
        "threshold": float(tree.threshold[node]),
        "left": _tree_to_dict(tree, feature_names, left),
        "right": _tree_to_dict(tree, feature_names, right),
        "n_samples": int(tree.n_node_samples[node]),
    }


def _export_json(model: TrainedModel) -> bytes:
    feature_names = model.encoded_columns or model.feature_names
    payload: dict[str, Any] = {
        "model_type": model.model_type,
        "task": model.task,
        "feature_names": feature_names,
        "target_classes": model.target_classes,
    }
    if model.model_type in LINEAR_MODEL_TYPES:
        estimator = model.estimator
        coef = np.atleast_2d(estimator.coef_)
        payload["coefficients"] = coef.tolist()
        payload["intercept"] = np.atleast_1d(estimator.intercept_).tolist()
        payload["classes"] = [str(c) for c in estimator.classes_] if hasattr(estimator, "classes_") else None
    elif model.model_type in TREE_MODEL_TYPES:
        estimator = model.estimator
        payload["tree"] = _tree_to_dict(estimator.tree_, feature_names)
        payload["classes"] = [str(c) for c in estimator.classes_] if hasattr(estimator, "classes_") else None
    else:
        raise AppError(
            400,
            "FORMAT_NOT_SUPPORTED",
            f"L'export JSON n'est disponible que pour les modèles linéaires et l'arbre de décision unique "
            f"(pas '{model.model_type}', qui combine trop de paramètres/arbres pour un JSON lisible). "
            "Utilisez le format joblib ou ONNX.",
        )
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def _export_onnx(model: TrainedModel) -> bytes:
    if model.task == "neural_network":
        raise AppError(400, "FORMAT_NOT_SUPPORTED", "Utilisez le format TFLite pour un réseau de neurones.")
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
    except ImportError as exc:  # pragma: no cover - dépendance toujours installée en prod
        raise AppError(501, "ONNX_UNAVAILABLE", "Support ONNX indisponible sur ce serveur.") from exc

    n_features = len(model.encoded_columns or model.feature_names)
    initial_types = [("input", FloatTensorType([None, n_features]))]
    try:
        onnx_model = convert_sklearn(model.estimator, initial_types=initial_types)
    except Exception as exc:
        raise AppError(
            501,
            "ONNX_CONVERSION_FAILED",
            f"Ce type de modèle ('{model.model_type}') n'est pas convertible en ONNX : {exc}",
        ) from exc
    return onnx_model.SerializeToString()


def _export_tflite(model: TrainedModel) -> bytes:
    if model.task != "neural_network":
        raise AppError(400, "FORMAT_NOT_SUPPORTED", "Le format TFLite n'est disponible que pour les réseaux de neurones.")
    import tensorflow as tf

    converter = tf.lite.TFLiteConverter.from_keras_model(model.estimator)
    try:
        return converter.convert()
    except Exception as exc:
        raise AppError(501, "TFLITE_CONVERSION_FAILED", f"Conversion TFLite impossible : {exc}") from exc


def export_model_file(model: TrainedModel, fmt: str) -> tuple[bytes, str, str, str]:
    """Retourne (contenu, nom_de_fichier, media_type, empreinte_md5)."""
    if fmt == "joblib":
        if model.task == "neural_network":
            raise AppError(400, "FORMAT_NOT_SUPPORTED", "Utilisez le format TFLite pour un réseau de neurones.")
        buffer = io.BytesIO()
        joblib.dump(_bundle(model), buffer)
        content = buffer.getvalue()
    elif fmt == "pickle":
        if model.task == "neural_network":
            raise AppError(400, "FORMAT_NOT_SUPPORTED", "Utilisez le format TFLite pour un réseau de neurones.")
        content = pickle.dumps(_bundle(model))
    elif fmt == "json":
        content = _export_json(model)
    elif fmt == "onnx":
        content = _export_onnx(model)
    elif fmt == "tflite":
        content = _export_tflite(model)
    else:
        raise AppError(400, "UNKNOWN_FORMAT", f"Format d'export inconnu : {fmt}")

    checksum = hashlib.md5(content).hexdigest()
    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    filename = f"modele_{model.model_type}_{timestamp}.{FORMAT_EXTENSIONS[fmt]}"
    return content, filename, FORMAT_MEDIA_TYPES[fmt], checksum


def build_metadata(model: TrainedModel) -> dict:
    return {
        "model_type": model.model_type,
        "task": model.task,
        "training_date": model.created_at,
        "dataset": {
            "rows": model.dataset_shape[0],
            "columns": model.dataset_shape[1],
            "feature_names": model.feature_names,
            "target_name": model.target_name,
            "target_classes": model.target_classes,
        },
        "preprocessing": {
            "encoding": "one-hot (pandas.get_dummies, drop_first=True)" if model.encoded_columns else None,
            "encoded_columns": model.encoded_columns,
        },
        "model_config": model.config,
        "performance": model.performance,
        "feature_importance": (
            {d["feature"]: round(d["importance"], 6) for d in model.feature_importance}
            if model.feature_importance else None
        ),
        "n_train": model.n_train,
        "n_test": model.n_test,
    }


_SKLEARN_IMPORTS = {
    "linear": "from sklearn.linear_model import LinearRegression",
    "ridge": "from sklearn.linear_model import Ridge",
    "lasso": "from sklearn.linear_model import Lasso",
    "elastic_net": "from sklearn.linear_model import ElasticNet",
    "svr": "from sklearn.svm import SVR",
    "gpr": "from sklearn.gaussian_process import GaussianProcessRegressor",
    "gradient_boosting": "from sklearn.ensemble import GradientBoostingRegressor  # ou GradientBoostingClassifier",
    "random_forest": "from sklearn.ensemble import RandomForestRegressor  # ou RandomForestClassifier",
    "logistic": "from sklearn.linear_model import LogisticRegression",
    "decision_tree": "from sklearn.tree import DecisionTreeClassifier",
    "svm": "from sklearn.svm import SVC",
    "knn": "from sklearn.neighbors import KNeighborsClassifier",
    "naive_bayes": "from sklearn.naive_bayes import GaussianNB",
    "mlp": "from sklearn.neural_network import MLPClassifier",
}


def _notebook_cell(source: str, kind: str = "code") -> dict:
    return {
        "cell_type": kind,
        "metadata": {},
        "source": source.splitlines(keepends=True),
        **({"outputs": [], "execution_count": None} if kind == "code" else {}),
    }


def build_training_notebook(model: TrainedModel) -> bytes:
    """Notebook Jupyter (.ipynb) minimal permettant de reproduire l'entraînement :
    mêmes hyperparamètres, mêmes colonnes, même graine aléatoire. Suppose que
    l'utilisateur recharge un CSV avec les mêmes colonnes que le fichier original
    (le serveur ne conserve pas les données brutes après la session)."""
    is_neural = model.task == "neural_network"
    import_line = _SKLEARN_IMPORTS.get(model.model_type, "# Importez la classe scikit-learn correspondant à ce modèle")

    cells = [
        _notebook_cell(
            f"# Reproduction du modèle « {model.model_type} » (DataVortex)\n"
            f"Entraîné le {model.created_at} sur {model.dataset_shape[0]} lignes × {model.dataset_shape[1]} colonnes.\n\n"
            f"Performance obtenue : {json.dumps(model.performance, ensure_ascii=False)}\n",
            kind="markdown",
        ),
        _notebook_cell(
            "import pandas as pd\n"
            "import numpy as np\n"
            f"{'' if is_neural else import_line}\n"
            f"{'import tensorflow as tf' if is_neural else ''}\n"
        ),
        _notebook_cell(
            "# Rechargez ici le même fichier que celui utilisé dans DataVortex\n"
            "# (mêmes colonnes, mêmes noms).\n"
            "df = pd.read_csv('votre_fichier.csv')\n"
            f"features = {model.feature_names!r}\n"
            f"target = {model.target_name!r}\n"
            "df = df[[*features, target]].dropna()\n"
            "X = df[features]\n"
            "y = df[target]\n"
        ),
    ]

    if model.encoded_columns:
        cells.append(_notebook_cell(
            "# Encodage one-hot des colonnes non numériques, comme dans DataVortex\n"
            "categorical = [c for c in X.columns if X[c].dtype == object]\n"
            "X = pd.get_dummies(X, columns=categorical, drop_first=True)\n"
            f"X = X.reindex(columns={model.encoded_columns!r}, fill_value=0)\n"
        ))

    config = {k: v for k, v in model.config.items() if v is not None}
    if is_neural:
        cells.append(_notebook_cell(
            "from sklearn.model_selection import train_test_split\n"
            "from sklearn.preprocessing import LabelEncoder\n\n"
            "X_train, X_test, y_train, y_test = train_test_split(X.to_numpy(dtype=float), y, test_size=0.25, random_state=42)\n"
            f"config = {json.dumps(config, ensure_ascii=False)}\n"
            "# Reconstruisez l'architecture avec ces hyperparamètres (couches, activations,\n"
            "# optimiseur, taux d'apprentissage) via tf.keras.Sequential, comme dans\n"
            "# app/ml_neural_service.py::_build_model, puis model.fit(X_train, y_train, ...).\n"
        ))
    else:
        cells.append(_notebook_cell(
            f"config = {json.dumps(config, ensure_ascii=False)}\n"
            "# model = <ClasseDuModèle>(**{k: v for k, v in config.items() if k not in ('model_type',)})\n"
            "# model.fit(X, y)\n"
            "# predictions = model.predict(X)\n"
        ))

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(notebook, indent=1, ensure_ascii=False).encode("utf-8")
