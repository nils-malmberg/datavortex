from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

IRIS_CONTENT = None
TITANIC_CONTENT = (
    b"PassengerId,Survived,Pclass,Sex,Age\n"
    + b"".join(
        f"{i},{1 if i % 3 == 0 else 0},{(i % 3) + 1},{'female' if i % 2 == 0 else 'male'},{20 + (i % 40)}\n".encode()
        for i in range(1, 121)
    )
)


def _load_iris_csv() -> bytes:
    import csv
    import io
    import random

    random.seed(0)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["sepal_length", "sepal_width", "petal_length", "petal_width", "species"])
    species_params = {
        "setosa": (5.0, 3.4, 1.5, 0.2),
        "versicolor": (6.0, 2.8, 4.3, 1.3),
        "virginica": (6.5, 3.0, 5.5, 2.0),
    }
    for species, (sl, sw, pl, pw) in species_params.items():
        for _ in range(30):
            writer.writerow(
                [
                    round(sl + random.uniform(-0.3, 0.3), 2),
                    round(sw + random.uniform(-0.3, 0.3), 2),
                    round(pl + random.uniform(-0.3, 0.3), 2),
                    round(pw + random.uniform(-0.2, 0.2), 2),
                    species,
                ]
            )
    return buf.getvalue().encode()


def _upload_and_parse(content, filename="test.csv"):
    resp = client.post("/api/upload", files={"file": (filename, content, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def _iris_session():
    return _upload_and_parse(_load_iris_csv(), "iris.csv")


def _titanic_session():
    return _upload_and_parse(TITANIC_CONTENT, "titanic.csv")


# --------------------------------------------------------------------------
# Régression
# --------------------------------------------------------------------------

def test_regression_linear_iris():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/regression",
        json={
            "session_id": session_id,
            "features": ["sepal_length"],
            "target": "petal_length",
            "model_type": "linear",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "sepal_length" in body["equation"]
    assert 0 <= body["r2"] <= 1
    assert body["rmse"] >= 0
    assert "main" in body["plot_data"]


def test_regression_polynomial():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/regression",
        json={
            "session_id": session_id,
            "features": ["sepal_length"],
            "target": "petal_length",
            "model_type": "polynomial",
            "degree": 3,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["r2"] >= 0


def test_regression_rejects_non_numeric_feature():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/regression",
        json={"session_id": session_id, "features": ["species"], "target": "petal_length"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def test_classification_logistic_iris():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/classification",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "target": "species",
            "model_type": "logistic",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["accuracy"] <= 1
    assert set(body["confusion_matrix"]["labels"]) == {"setosa", "versicolor", "virginica"}
    assert body["tree_image_base64"] is None


def test_classification_decision_tree_has_image():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/classification",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "target": "species",
            "model_type": "decision_tree",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tree_image_base64"]
    import base64
    assert base64.b64decode(body["tree_image_base64"])[:8] == b"\x89PNG\r\n\x1a\n"


def test_classification_random_forest_feature_importance():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/classification",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "target": "species",
            "model_type": "random_forest",
            "params": {"n_estimators": 20},
        },
    )
    assert resp.status_code == 200
    importances = resp.json()["feature_importance"]
    assert len(importances) == 4
    assert sum(f["importance"] for f in importances) > 0


def test_classification_titanic_with_categorical_feature():
    session_id = _titanic_session()
    resp = client.post(
        "/api/ml/classification",
        json={
            "session_id": session_id,
            "features": ["Age", "Sex", "Pclass"],
            "target": "Survived",
            "model_type": "logistic",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 0 <= body["accuracy"] <= 1
    feature_names = [f["feature"] for f in body["feature_importance"]]
    assert any("Sex" in name for name in feature_names)


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------

def test_clustering_kmeans_separates_iris_species():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/clustering",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "model_type": "kmeans",
            "params": {"k": 3},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_clusters"] == 3
    assert body["silhouette_score"] > 0.3
    assert "elbow_curve" in body["plot_data"]


def test_clustering_dbscan():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/clustering",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "model_type": "dbscan",
            "params": {"eps": 0.9, "min_samples": 5},
        },
    )
    assert resp.status_code == 200
    assert "main" in resp.json()["plot_data"]


def test_clustering_invalid_k_rejected():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/clustering",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width"],
            "model_type": "kmeans",
            "params": {"k": 1},
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PARAM"


# --------------------------------------------------------------------------
# PCA / t-SNE
# --------------------------------------------------------------------------

def test_pca_4d_to_2d_iris():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/pca",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "n_components": 2,
            "method": "pca",
            "color_by": "species",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["explained_variance"]) == 2
    assert sum(body["explained_variance"]) > 0.8
    assert len(body["plot_data"]["main"]["data"]) == 3


def test_pca_3d():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/pca",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "n_components": 3,
            "method": "pca",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["plot_data"]["main"]["data"][0]["type"] == "scatter3d"


def test_tsne():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/pca",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "n_components": 2,
            "method": "tsne",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["explained_variance"] is None


def test_umap_returns_clear_unavailable_error():
    session_id = _iris_session()
    resp = client.post(
        "/api/ml/pca",
        json={
            "session_id": session_id,
            "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
            "n_components": 2,
            "method": "umap",
        },
    )
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "METHOD_NOT_AVAILABLE"


def test_ml_session_not_found():
    resp = client.post(
        "/api/ml/regression",
        json={"session_id": "nope", "features": ["a"], "target": "b"},
    )
    assert resp.status_code == 404
