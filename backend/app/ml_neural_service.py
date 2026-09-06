"""Constructeur de réseau de neurones (Phase 8.1), basé sur TensorFlow/Keras.

Contrairement au reste du module ML (scikit-learn), un vrai entraînement de
réseau de neurones (couches configurables, optimiseur, courbes de perte par
époque) demande un framework dédié : TensorFlow/Keras est utilisé tel quel,
comme le suggère la spec. L'import est fait une fois au chargement du module
(coût ~5s payé au démarrage du serveur, pas à chaque requête).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import tensorflow as tf
from sklearn.metrics import accuracy_score, confusion_matrix, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

from app.errors import AppError
from app.ml import PALETTE, _clean_subset, _encode_features, _permutation_feature_importance, _require_columns

RANDOM_STATE = 42
MAX_LAYERS = 8
MAX_UNITS = 512
MIN_SAMPLES = 20

tf.random.set_seed(RANDOM_STATE)


def _build_model(input_dim: int, layers: list[dict], output_units: int, output_activation: str, loss: str,
                  optimizer_name: str, learning_rate: float, normalizer: tf.keras.layers.Normalization) -> tf.keras.Model:
    """La normalisation (moyenne/écart-type appris sur le train) est une vraie
    couche du modèle, pas un `StandardScaler` externe : le modèle exporté
    (TFLite compris) reste autonome, entrée brute -> sortie, sans dépendance
    à un objet scikit-learn séparé qui ne survivrait pas à la conversion."""
    model = tf.keras.Sequential(name="datavortex_mlp")
    model.add(tf.keras.layers.Input(shape=(input_dim,)))
    model.add(normalizer)
    for layer in layers:
        units = max(1, min(MAX_UNITS, int(layer.get("units", 16))))
        activation = layer.get("activation", "relu")
        model.add(tf.keras.layers.Dense(units, activation=activation))
        dropout = float(layer.get("dropout", 0.0))
        if dropout > 0:
            model.add(tf.keras.layers.Dropout(min(0.5, max(0.0, dropout))))
    model.add(tf.keras.layers.Dense(output_units, activation=output_activation))

    optimizers = {
        "adam": tf.keras.optimizers.Adam,
        "sgd": tf.keras.optimizers.SGD,
        "rmsprop": tf.keras.optimizers.RMSprop,
    }
    optimizer_cls = optimizers.get(optimizer_name, tf.keras.optimizers.Adam)
    metrics = ["accuracy"] if loss != "mse" else ["mae"]
    model.compile(optimizer=optimizer_cls(learning_rate=learning_rate), loss=loss, metrics=metrics)
    return model


def _weights_payload(model: tf.keras.Model) -> list[dict]:
    """Poids/biais par couche dense, pour le diagramme de réseau côté frontend."""
    payload = []
    for layer in model.layers:
        if not isinstance(layer, tf.keras.layers.Dense):
            continue
        weights = layer.get_weights()
        if not weights:
            continue
        kernel, bias = weights[0], weights[1]
        payload.append({
            "name": layer.name,
            "activation": getattr(layer.activation, "__name__", None) if hasattr(layer, "activation") else None,
            "units": int(kernel.shape[1]),
            "kernel": kernel.tolist(),
            "bias": bias.tolist(),
        })
    return payload


def run_neural_network(
    df: pd.DataFrame, features: list[str], target: str, task: str, layers: list[dict],
    optimizer: str, learning_rate: float, batch_size: int, epochs: int, validation_split: float,
) -> dict:
    if not features:
        raise AppError(400, "MISSING_FEATURES", "Au moins une colonne de features est requise.")
    _require_columns(df, [*features, target])
    if not layers:
        raise AppError(400, "MISSING_LAYERS", "Au moins une couche cachée est requise.")
    if len(layers) > MAX_LAYERS:
        raise AppError(400, "TOO_MANY_LAYERS", f"Maximum {MAX_LAYERS} couches cachées.")

    subset = _clean_subset(df, [*features, target])
    if len(subset) < MIN_SAMPLES:
        raise AppError(422, "INSUFFICIENT_DATA", f"Au moins {MIN_SAMPLES} lignes complètes sont requises.")

    X_raw = subset[features]
    X_encoded = _encode_features(X_raw).astype(float)
    X_values = X_encoded.to_numpy()

    label_encoder = None
    target_classes = None
    if task == "classification":
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(subset[target].astype(str))
        target_classes = [str(c) for c in label_encoder.classes_]
        n_classes = len(target_classes)
        if n_classes < 2:
            raise AppError(422, "INSUFFICIENT_CLASSES", "La cible doit contenir au moins 2 classes distinctes.")
        output_units = 1 if n_classes == 2 else n_classes
        output_activation = "sigmoid" if n_classes == 2 else "softmax"
        loss = "binary_crossentropy" if n_classes == 2 else "sparse_categorical_crossentropy"
        stratify = y
    else:
        y = subset[target].to_numpy(dtype=float)
        output_units, output_activation, loss = 1, "linear", "mse"
        stratify = None

    X_train, X_test, y_train, y_test = train_test_split(
        X_values, y, test_size=0.25, random_state=RANDOM_STATE, stratify=stratify,
    )

    normalizer = tf.keras.layers.Normalization(axis=-1)
    normalizer.adapt(X_train)
    model = _build_model(X_values.shape[1], list(layers), output_units, output_activation,
                          loss, optimizer, learning_rate, normalizer)

    validation_split = min(0.4, max(0.05, validation_split))
    epochs = max(1, min(500, int(epochs)))
    batch_size = max(1, min(len(X_train), int(batch_size)))

    history = model.fit(
        X_train, y_train, validation_split=validation_split, epochs=epochs,
        batch_size=batch_size, verbose=0,
    )

    metric_key = "accuracy" if task == "classification" else "mae"
    loss_history = {
        "loss": [float(v) for v in history.history.get("loss", [])],
        "val_loss": [float(v) for v in history.history.get("val_loss", [])],
        "metric_name": metric_key,
        "metric": [float(v) for v in history.history.get(metric_key, [])],
        "val_metric": [float(v) for v in history.history.get(f"val_{metric_key}", [])],
    }

    if task == "classification":
        proba = model.predict(X_test, verbose=0)
        y_pred = (proba.ravel() > 0.5).astype(int) if output_units == 1 else np.argmax(proba, axis=1)
        accuracy = float(accuracy_score(y_test, y_pred))
        cm = confusion_matrix(y_test, y_pred, labels=list(range(len(target_classes))))
        performance = {"accuracy": accuracy}
        cm_fig = go.Figure(go.Heatmap(
            z=cm, x=target_classes, y=target_classes, colorscale="Blues",
            text=cm, texttemplate="%{text}", showscale=False,
        ))
        cm_fig.update_layout(title="Matrice de confusion", xaxis_title="Prédit", yaxis_title="Réel",
                              yaxis=dict(autorange="reversed"))
        confusion = {"labels": target_classes, "matrix": cm.tolist()}
    else:
        y_pred = model.predict(X_test, verbose=0).ravel()
        performance = {
            "r2": float(r2_score(y_test, y_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "mae": float(mean_absolute_error(y_test, y_pred)),
        }
        cm_fig = go.Figure(go.Scatter(x=y_test, y=y_pred, mode="markers", marker=dict(color=PALETTE[0], opacity=0.7)))
        lo, hi = float(min(y_test.min(), y_pred.min())), float(max(y_test.max(), y_pred.max()))
        cm_fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color=PALETTE[3], dash="dash")))
        cm_fig.update_layout(title="Valeurs prédites vs réelles", xaxis_title="Réel", yaxis_title="Prédit")
        confusion = None

    class _KerasPredictAdapter:
        """Adapte le modèle Keras à l'API scikit-learn (`.fit`/`.predict`)
        attendue par `permutation_importance`, pour réutiliser le même calcul
        que le reste du module ML plutôt que de dupliquer la logique de
        permutation. `.fit` est un no-op : le modèle est déjà entraîné, mais
        le validateur de paramètres de sklearn exige que la méthode existe."""

        def __init__(self, keras_model, is_classification, n_classes):
            self._model = keras_model
            self._is_classification = is_classification
            self._n_classes = n_classes

        def fit(self, X, y=None):
            return self

        def predict(self, X):
            pred = self._model.predict(X, verbose=0)
            if not self._is_classification:
                return pred.ravel()
            if self._n_classes == 2:
                return (pred.ravel() > 0.5).astype(int)
            return np.argmax(pred, axis=1)

    scoring = "accuracy" if task == "classification" else "r2"
    adapter = _KerasPredictAdapter(model, task == "classification", output_units if task == "classification" else 0)
    feature_importance = _permutation_feature_importance(
        adapter, X_test, y_test, scoring, list(X_encoded.columns), n_repeats=5,
    )

    loss_fig = go.Figure()
    loss_fig.add_trace(go.Scatter(y=loss_history["loss"], mode="lines", name="Perte (train)"))
    if loss_history["val_loss"]:
        loss_fig.add_trace(go.Scatter(y=loss_history["val_loss"], mode="lines", name="Perte (validation)"))
    loss_fig.update_layout(title="Courbe de perte", xaxis_title="Époque", yaxis_title="Perte")

    metric_fig = go.Figure()
    metric_fig.add_trace(go.Scatter(y=loss_history["metric"], mode="lines", name=f"{metric_key} (train)"))
    if loss_history["val_metric"]:
        metric_fig.add_trace(go.Scatter(y=loss_history["val_metric"], mode="lines", name=f"{metric_key} (validation)"))
    metric_fig.update_layout(title=f"Courbe de {metric_key}", xaxis_title="Époque", yaxis_title=metric_key)

    layer_sizes = [len(X_encoded.columns), *[max(1, min(MAX_UNITS, int(layer.get("units", 16)))) for layer in layers], output_units]

    extra_figs = {"loss": loss_fig, "metric": metric_fig}
    if feature_importance:
        from app.ml import _importance_figure
        extra_figs["feature_importance"] = _importance_figure(feature_importance, "Importance des variables (permutation)")

    return {
        "task": task,
        "performance": performance,
        "loss_history": loss_history,
        "confusion_matrix": confusion,
        "feature_importance": feature_importance,
        "layer_sizes": layer_sizes,
        "feature_names": list(X_encoded.columns),
        "target_classes": target_classes,
        "weights": _weights_payload(model),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "_fig": cm_fig,
        "_extra_figs": extra_figs,
        "_model": model,
        "_model_meta": {
            "feature_names": features,
            "target_name": target,
            "target_classes": target_classes,
            "encoded_columns": list(X_encoded.columns),
            "config": {
                "task": task, "layers": layers, "optimizer": optimizer, "learning_rate": learning_rate,
                "batch_size": batch_size, "epochs": epochs, "validation_split": validation_split,
            },
            "performance": performance,
            "feature_importance": feature_importance,
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "dataset_shape": (int(df.shape[0]), int(df.shape[1])),
        },
    }
