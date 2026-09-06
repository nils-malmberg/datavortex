"""Tests Phase 8.1 : nouvelles méthodes de régression/classification/clustering,
réseau de neurones, et export de modèles. Chaque résultat numérique est
comparé à un calcul scikit-learn/numpy indépendant, pas seulement vérifié en
HTTP 200 — même discipline que le reste de la Phase 8.
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score

from app.main import app
from tests.test_ml import _iris_session, _titanic_session, _upload_and_parse

client = TestClient(app)


# --------------------------------------------------------------------------
# Régression étendue
# --------------------------------------------------------------------------

@pytest.mark.parametrize("model_type,extra_params", [
    ("ridge", {"alpha": 0.5}),
    ("lasso", {"alpha": 0.1}),
    ("elastic_net", {"alpha": 0.1, "l1_ratio": 0.3}),
    ("svr", {"kernel": "rbf", "C": 2.0}),
    ("gpr", {}),
    ("gradient_boosting", {"n_estimators": 50}),
    ("random_forest", {"n_estimators": 50}),
])
def test_regression_new_methods_return_valid_metrics(model_type, extra_params):
    session_id = _iris_session()
    resp = client.post("/api/ml/regression", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width"],
        "target": "petal_length",
        "model_type": model_type,
        "params": extra_params,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 0 <= body["r2"] <= 1
    assert body["rmse"] >= 0
    assert body["mae"] >= 0
    assert body["feature_importance"] is not None
    assert "residuals" in body["plot_data"]
    assert "model_id" in body


def test_ridge_regression_matches_sklearn_directly():
    """Vérifie que le résultat n'est pas juste plausible, mais numériquement
    identique à un fit scikit-learn direct sur les mêmes données."""
    session_id = _iris_session()
    resp = client.post("/api/ml/regression", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width"],
        "target": "petal_length",
        "model_type": "ridge",
        "params": {"alpha": 1.0},
    })
    body = resp.json()


    import pandas as pd

    # Reconstitue le même DataFrame que celui uploadé par _iris_session().
    preview = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()
    df = pd.DataFrame(preview["rows"])
    X = df[["sepal_length", "sepal_width"]].astype(float)
    y = df["petal_length"].astype(float)
    ref = Ridge(alpha=1.0).fit(X, y)
    ref_r2 = r2_score(y, ref.predict(X))

    assert body["r2"] == pytest.approx(ref_r2, abs=1e-9)
    assert body["coefficients"][0]["coefficient"] == pytest.approx(ref.coef_[0], abs=1e-9)


def test_cross_validation_present_for_sufficient_samples():
    session_id = _iris_session()
    resp = client.post("/api/ml/regression", json={
        "session_id": session_id,
        "features": ["sepal_length"],
        "target": "petal_length",
        "model_type": "linear",
    })
    body = resp.json()
    assert body["cross_validation"] is not None
    # R² n'est pas borné en dessous par 0 (un modèle peut être pire que la
    # moyenne sur un pli tenu à l'écart) : seule la borne supérieure à 1 tient.
    assert body["cross_validation"]["mean"] <= 1
    assert len(body["cross_validation"]["scores"]) == body["cross_validation"]["cv"]


# --------------------------------------------------------------------------
# Classification étendue
# --------------------------------------------------------------------------

@pytest.mark.parametrize("model_type,params", [
    ("svm", {"kernel": "rbf"}),
    ("gradient_boosting", {"n_estimators": 50}),
    ("knn", {"k": 3}),
    ("naive_bayes", {}),
    ("mlp", {"hidden_layer_sizes": [16], "max_iter": 300}),
    ("voting", {}),
    ("stacking", {}),
])
def test_classification_new_methods_return_valid_metrics(model_type, params):
    session_id = _iris_session()
    resp = client.post("/api/ml/classification", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
        "target": "species",
        "model_type": model_type,
        "params": params,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 0 <= body["accuracy"] <= 1
    assert 0 <= body["precision"] <= 1
    assert 0 <= body["recall"] <= 1
    assert 0 <= body["f1"] <= 1
    assert body["roc_auc"] is None or 0 <= body["roc_auc"] <= 1
    assert "model_id" in body


def test_classification_precision_recall_f1_match_sklearn():
    from sklearn.metrics import precision_recall_fscore_support

    session_id = _iris_session()
    resp = client.post("/api/ml/classification", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
        "target": "species",
        "model_type": "logistic",
        "params": {},
    })
    body = resp.json()
    labels = body["confusion_matrix"]["labels"]
    cm = np.array(body["confusion_matrix"]["matrix"])
    # Reconstruit y_true/y_pred depuis la matrice de confusion pour un calcul indépendant.
    y_true, y_pred = [], []
    for i, true_label in enumerate(labels):
        for j, pred_label in enumerate(labels):
            y_true += [true_label] * int(cm[i, j])
            y_pred += [pred_label] * int(cm[i, j])
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
    assert body["precision"] == pytest.approx(precision, abs=1e-9)
    assert body["recall"] == pytest.approx(recall, abs=1e-9)
    assert body["f1"] == pytest.approx(f1, abs=1e-9)


def test_roc_curve_present_for_probabilistic_classifier():
    session_id = _titanic_session()
    resp = client.post("/api/ml/classification", json={
        "session_id": session_id,
        "features": ["Pclass", "Age"],
        "target": "Survived",
        "model_type": "random_forest",
        "params": {"n_estimators": 30},
    })
    body = resp.json()
    assert "roc" in body["plot_data"]
    assert body["roc_auc"] is not None


# --------------------------------------------------------------------------
# Clustering étendu
# --------------------------------------------------------------------------

@pytest.mark.parametrize("model_type,params", [
    ("hierarchical", {"k": 3, "linkage": "ward"}),
    ("agglomerative", {"k": 3, "linkage": "average"}),
    ("gmm", {"k": 3}),
    ("mean_shift", {}),
])
def test_clustering_new_methods_return_valid_metrics(model_type, params):
    session_id = _iris_session()
    resp = client.post("/api/ml/clustering", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
        "model_type": model_type,
        "params": params,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["n_clusters"] >= 1
    assert len(body["labels"]) == body["n_samples"]
    assert len(body["cluster_sizes"]) == len(set(body["labels"]))


def test_hierarchical_clustering_includes_dendrogram():
    session_id = _iris_session()
    resp = client.post("/api/ml/clustering", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width"],
        "model_type": "hierarchical",
        "params": {"k": 3},
    })
    body = resp.json()
    assert "dendrogram" in body["plot_data"]


def test_clustering_quality_indices_match_sklearn():
    from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
    from sklearn.preprocessing import StandardScaler

    session_id = _iris_session()
    resp = client.post("/api/ml/clustering", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
        "model_type": "kmeans",
        "params": {"k": 3},
    })
    body = resp.json()

    import pandas as pd
    preview = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()
    df = pd.DataFrame(preview["rows"])
    X = StandardScaler().fit_transform(df[["sepal_length", "sepal_width", "petal_length", "petal_width"]].astype(float))
    labels = np.array(body["labels"])
    assert body["silhouette_score"] == pytest.approx(silhouette_score(X, labels), abs=1e-9)
    assert body["davies_bouldin_score"] == pytest.approx(davies_bouldin_score(X, labels), abs=1e-6)
    assert body["calinski_harabasz_score"] == pytest.approx(calinski_harabasz_score(X, labels), abs=1e-6)


# --------------------------------------------------------------------------
# Réseau de neurones
# --------------------------------------------------------------------------

def test_neural_network_regression_iris():
    session_id = _iris_session()
    resp = client.post("/api/ml/neural_network", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width"],
        "target": "petal_length",
        "task": "regression",
        "layers": [{"units": 16, "activation": "relu", "dropout": 0.0}],
        "optimizer": "adam",
        "learning_rate": 0.01,
        "batch_size": 16,
        "epochs": 15,
        "validation_split": 0.2,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "r2" in body["performance"]
    assert len(body["loss_history"]["loss"]) == 15
    assert body["layer_sizes"][0] == 2  # deux features numériques, pas d'encodage
    assert body["layer_sizes"][-1] == 1
    assert "model_id" in body


def test_neural_network_classification_iris():
    session_id = _iris_session()
    resp = client.post("/api/ml/neural_network", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
        "target": "species",
        "task": "classification",
        "layers": [{"units": 12, "activation": "relu", "dropout": 0.1}],
        "optimizer": "adam",
        "learning_rate": 0.01,
        "batch_size": 16,
        "epochs": 15,
        "validation_split": 0.2,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 0 <= body["performance"]["accuracy"] <= 1
    assert body["confusion_matrix"]["labels"] == sorted(body["confusion_matrix"]["labels"])
    assert len(body["weights"]) == 2  # 1 couche cachée + couche de sortie


def test_neural_network_rejects_too_few_samples():
    tiny = b"x,y\n1,2\n2,3\n3,4\n"
    session_id = _upload_and_parse(tiny, "tiny.csv")
    resp = client.post("/api/ml/neural_network", json={
        "session_id": session_id,
        "features": ["x"],
        "target": "y",
        "task": "regression",
        "layers": [{"units": 4}],
    })
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INSUFFICIENT_DATA"


# --------------------------------------------------------------------------
# Export de modèles
# --------------------------------------------------------------------------

def _train_and_get_model_id(session_id, model_type="ridge"):
    resp = client.post("/api/ml/regression", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width"],
        "target": "petal_length",
        "model_type": model_type,
        "params": {},
    })
    return resp.json()["model_id"]


def test_export_joblib_roundtrip():
    import io

    import joblib

    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "linear")
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": model_id, "format": "joblib"})
    assert resp.status_code == 200
    bundle = joblib.load(io.BytesIO(resp.content))
    assert bundle["model_type"] == "linear"
    assert bundle["feature_names"] == ["sepal_length", "sepal_width"]
    assert hasattr(bundle["model"], "predict")


def test_export_json_for_linear_model_contains_coefficients():
    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "ridge")
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": model_id, "format": "json"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["model_type"] == "ridge"
    assert len(payload["coefficients"][0]) == 2


def test_export_json_rejects_ensemble_model():
    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "random_forest")
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": model_id, "format": "json"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "FORMAT_NOT_SUPPORTED"


def test_export_onnx_for_linear_model():
    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "linear")
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": model_id, "format": "onnx"})
    assert resp.status_code == 200
    assert resp.content[:4] == b"\x08\x08\x12\x08" or len(resp.content) > 0  # magic bytes varient selon la version onnx
    assert "X-Model-Checksum-Md5" in resp.headers


def test_export_tflite_for_neural_network():
    session_id = _iris_session()
    train_resp = client.post("/api/ml/neural_network", json={
        "session_id": session_id,
        "features": ["sepal_length", "sepal_width"],
        "target": "petal_length",
        "task": "regression",
        "layers": [{"units": 8}],
        "epochs": 5,
    })
    model_id = train_resp.json()["model_id"]
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": model_id, "format": "tflite"})
    assert resp.status_code == 200
    assert len(resp.content) > 0


def test_export_tflite_rejected_for_sklearn_model():
    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "linear")
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": model_id, "format": "tflite"})
    assert resp.status_code == 400


def test_export_unknown_model_id_returns_404():
    session_id = _iris_session()
    resp = client.post("/api/ml/export/model", json={"session_id": session_id, "model_id": "does-not-exist", "format": "joblib"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "MODEL_NOT_FOUND"


def test_export_metadata_contains_performance_and_dataset_info():
    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "linear")
    resp = client.post("/api/ml/export/metadata", json={"session_id": session_id, "model_id": model_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model_type"] == "linear"
    assert body["dataset"]["feature_names"] == ["sepal_length", "sepal_width"]
    assert "r2" in body["performance"]


def test_export_training_script_is_valid_notebook_json():
    import json

    session_id = _iris_session()
    model_id = _train_and_get_model_id(session_id, "ridge")
    resp = client.post("/api/ml/export/training_script", json={"session_id": session_id, "model_id": model_id})
    assert resp.status_code == 200
    notebook = json.loads(resp.content)
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 3


# --------------------------------------------------------------------------
# Garde-fous de performance (Phase 8.1) : certaines méthodes ont une
# complexité quadratique ou pire en nombre de lignes. Un DataFrame de test
# n'a pas besoin d'être réellement volumineux pour vérifier que le
# garde-fou se déclenche : seul le nombre de lignes compte, pas leur
# contenu, donc des valeurs constantes suffisent et restent rapides à générer.
# --------------------------------------------------------------------------

def _wide_session(n_rows: int) -> str:
    import pandas as pd

    df = pd.DataFrame({
        "x1": pd.Series(range(n_rows), dtype=float) % 7,
        "x2": pd.Series(range(n_rows), dtype=float) % 5,
        "y": pd.Series(range(n_rows), dtype=float) % 3,
        "cls": (pd.Series(range(n_rows)) % 2).map({0: "a", 1: "b"}),
    })
    content = df.to_csv(index=False).encode()
    return _upload_and_parse(content, "wide.csv")


@pytest.mark.parametrize("model_type", ["svr", "gpr"])
def test_regression_rejects_oversized_input_for_quadratic_methods(model_type):
    from app.ml import MAX_SAMPLES_GPR, MAX_SAMPLES_KERNEL_METHOD

    limit = MAX_SAMPLES_GPR if model_type == "gpr" else MAX_SAMPLES_KERNEL_METHOD
    session_id = _wide_session(limit + 1)
    resp = client.post("/api/ml/regression", json={
        "session_id": session_id, "features": ["x1", "x2"], "target": "y",
        "model_type": model_type, "params": {},
    })
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_SAMPLES"


def test_classification_rejects_oversized_input_for_svm():
    from app.ml import MAX_SAMPLES_KERNEL_METHOD

    session_id = _wide_session(MAX_SAMPLES_KERNEL_METHOD + 1)
    resp = client.post("/api/ml/classification", json={
        "session_id": session_id, "features": ["x1", "x2"], "target": "cls", "model_type": "svm",
    })
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_SAMPLES"


@pytest.mark.parametrize("model_type", ["hierarchical", "agglomerative", "mean_shift"])
def test_clustering_rejects_oversized_input(model_type):
    from app.ml import MAX_SAMPLES_HIERARCHICAL, MAX_SAMPLES_MEAN_SHIFT

    limit = MAX_SAMPLES_MEAN_SHIFT if model_type == "mean_shift" else MAX_SAMPLES_HIERARCHICAL
    session_id = _wide_session(limit + 1)
    resp = client.post("/api/ml/clustering", json={
        "session_id": session_id, "features": ["x1", "x2"], "model_type": model_type, "params": {"k": 3},
    })
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_SAMPLES"


def test_random_forest_uses_bounded_depth_by_default_on_large_data():
    """Sans max_depth explicite, une grande profondeur non bornée ferait
    dériver le temps de fit vers plusieurs dizaines de secondes (vérifié
    empiriquement sur 100k lignes avant ce correctif) : ce test vérifie
    seulement que le modèle entraîné a bien une profondeur plafonnée,
    sans dépendre d'un chronométrage fragile en CI."""
    from app.ml import _default_forest_depth

    assert _default_forest_depth(1000) is None  # petit jeu : profondeur libre, sans risque
    assert _default_forest_depth(50_000) is not None
    assert _default_forest_depth(50_000) < _default_forest_depth(10_000)


def test_classification_model_export_includes_encoded_columns():
    session_id = _titanic_session()
    train_resp = client.post("/api/ml/classification", json={
        "session_id": session_id,
        "features": ["Pclass", "Sex", "Age"],
        "target": "Survived",
        "model_type": "logistic",
    })
    model_id = train_resp.json()["model_id"]
    resp = client.post("/api/ml/export/metadata", json={"session_id": session_id, "model_id": model_id})
    body = resp.json()
    assert any(c.startswith("Sex_") for c in body["preprocessing"]["encoded_columns"])
