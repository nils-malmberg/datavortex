"""Phase 10.4 : TensorFlow absent, bloqué ou désactivé → diagnostic, pas erreur interne.

Le cas réel : sur un Windows 11 d'entreprise, `import tensorflow` échoue
(DLL refusée) alors que le même paquet fonctionne sur un poste personnel.
L'utilisateur voyait « Erreur interne inattendue : DLL load failed while
importing _pywrap_tensorflow_internal… ». Ces tests simulent cet échec et
vérifient que chaque surface (capabilities, health, routes) l'explique — et
que les méthodes scikit-learn continuent de fonctionner.
"""
from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import ml_backend
from app.main import app

client = TestClient(app)

WINDOWS_DLL_ERROR = ImportError(
    "DLL load failed while importing _pywrap_tensorflow_internal: "
    "A dynamic link library (DLL) initialization routine failed."
)


@pytest.fixture(autouse=True)
def _fresh_backend_state(monkeypatch):
    """Chaque test repart sans résultat mémorisé ni variable de désactivation."""
    for name in ml_backend.DISABLE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    ml_backend.reset_cache()
    yield
    ml_backend.reset_cache()


def _broken_tensorflow(monkeypatch, exc: BaseException = WINDOWS_DLL_ERROR):
    def fail():
        raise exc

    monkeypatch.setattr(ml_backend, "_import_tensorflow", fail)


def _iris_session() -> str:
    df = pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0] * 5,
        "b": [2.0, 4.1, 5.9, 8.2, 9.8, 12.1, 14.0, 16.2] * 5,
        "label": ["x", "y"] * 20,
    })
    resp = client.post("/api/upload", files={"file": ("d.csv", df.to_csv(index=False).encode(), "text/csv")})
    session_id = resp.json()["session_id"]
    assert client.post("/api/parse", json={"session_id": session_id, "separator": ","}).status_code == 200
    return session_id


def _train_network(session_id: str):
    return client.post("/api/ml/neural_network", json={
        "session_id": session_id, "features": ["a", "b"], "target": "label", "task": "classification",
        "layers": [{"units": 4, "activation": "relu", "dropout": 0}],
        "optimizer": "adam", "learning_rate": 0.01, "batch_size": 8, "epochs": 2, "validation_split": 0.2,
    })


# --- Diagnostic --------------------------------------------------------------


def test_windows_dll_failure_with_recent_tensorflow_names_the_version(monkeypatch):
    """Le cas réel (v1.2.3 sur un poste d'entreprise) : TF 2.20 installé, DLL refusée."""
    monkeypatch.setattr(ml_backend.platform, "system", lambda: "Windows")
    monkeypatch.setattr(ml_backend, "installed_version", lambda: "2.20.0")
    reason, hint = ml_backend.diagnose(WINDOWS_DLL_ERROR)
    assert "TensorFlow 2.20.0" in reason and "bibliothèque native" in reason
    assert "2.16" in hint and "2.15" in hint and "Visual C++ 2022" in hint
    assert "uv tool install --force" in hint


def test_windows_dll_failure_with_known_good_tensorflow_lists_other_causes(monkeypatch):
    monkeypatch.setattr(ml_backend.platform, "system", lambda: "Windows")
    monkeypatch.setattr(ml_backend, "installed_version", lambda: "2.15.1")
    reason, hint = ml_backend.diagnose(WINDOWS_DLL_ERROR)
    assert "TensorFlow 2.15.1" in reason
    assert "AppLocker" in hint and "AVX" in hint and "Visual C++" in hint


def test_installed_version_reads_metadata_without_importing():
    pytest.importorskip("tensorflow")
    assert ml_backend.installed_version()


def test_missing_package_is_explained():
    reason, hint = ml_backend.diagnose(ModuleNotFoundError("No module named 'tensorflow'", name="tensorflow"))
    assert "pas installé" in reason
    assert "uv tool install" in hint


def test_unknown_failure_still_gives_a_way_out():
    reason, hint = ml_backend.diagnose(RuntimeError("something odd"))
    assert "something odd" in reason
    assert "DATAVORTEX_NO_TENSORFLOW" in hint


# --- Capabilities & health ---------------------------------------------------


def test_capabilities_report_broken_tensorflow(monkeypatch):
    _broken_tensorflow(monkeypatch)
    body = client.get("/api/ml/capabilities").json()
    assert body["tensorflow"]["available"] is False
    assert body["tensorflow"]["probed"] is True
    assert "pywrap_tensorflow" in body["tensorflow"]["reason"]
    assert body["features"] == {"scikit_learn": True, "neural_network": False, "tflite_export": False}


def test_capabilities_report_working_tensorflow():
    pytest.importorskip("tensorflow")
    body = client.get("/api/ml/capabilities").json()
    assert body["tensorflow"]["available"] is True
    assert body["tensorflow"]["version"]
    assert body["features"]["neural_network"] is True


def test_health_never_triggers_the_import(monkeypatch):
    calls = []

    def spy():
        calls.append(1)
        raise WINDOWS_DLL_ERROR

    monkeypatch.setattr(ml_backend, "_import_tensorflow", spy)
    body = client.get("/api/health").json()
    assert body["tensorflow"] == {"available": None, "probed": False, "version": None,
                                  "disabled_by": None, "reason": None, "hint": None}
    assert calls == []


def test_failed_import_is_probed_once(monkeypatch):
    calls = []

    def spy():
        calls.append(1)
        raise WINDOWS_DLL_ERROR

    monkeypatch.setattr(ml_backend, "_import_tensorflow", spy)
    client.get("/api/ml/capabilities")
    client.get("/api/ml/capabilities")
    with pytest.raises(Exception):
        ml_backend.require_tensorflow()
    assert len(calls) == 1


# --- Routes -------------------------------------------------------------------


def test_neural_network_route_returns_diagnostic_not_internal_error(monkeypatch):
    _broken_tensorflow(monkeypatch)
    resp = _train_network(_iris_session())
    assert resp.status_code == 503
    error = resp.json()["error"]
    assert error["code"] == "TENSORFLOW_UNAVAILABLE"
    assert "pywrap_tensorflow" in error["message"]
    assert "DATAVORTEX_NO_TENSORFLOW" in error["message"] or "uv tool install --force" in error["message"]


def test_sklearn_methods_keep_working_without_tensorflow(monkeypatch):
    _broken_tensorflow(monkeypatch)
    session_id = _iris_session()
    resp = client.post("/api/ml/regression", json={
        "session_id": session_id, "features": ["a"], "target": "b", "model_type": "linear", "degree": 2,
    })
    assert resp.status_code == 200
    assert resp.json()["r2"] > 0.9


@pytest.mark.parametrize("variable", ["DATAVORTEX_NO_TENSORFLOW", "DATAVORTEX_NO_ML"])
def test_env_var_disables_tensorflow_without_importing(monkeypatch, variable):
    calls = []
    monkeypatch.setattr(ml_backend, "_import_tensorflow", lambda: calls.append(1))
    monkeypatch.setenv(variable, "1")

    body = client.get("/api/ml/capabilities").json()
    assert body["tensorflow"]["available"] is False
    assert body["tensorflow"]["disabled_by"] == variable
    assert body["features"]["scikit_learn"] is True

    resp = _train_network(_iris_session())
    assert resp.status_code == 503
    assert variable in resp.json()["error"]["message"]
    assert calls == []


def test_env_var_off_values_do_not_disable(monkeypatch):
    monkeypatch.setenv("DATAVORTEX_NO_ML", "0")
    assert ml_backend.disabled_by() is None


def test_tflite_export_reports_missing_tensorflow(monkeypatch):
    """L'export d'un modèle entraîné ailleurs ne doit pas non plus finir en erreur interne."""
    from app.ml_export_service import _export_tflite
    from app.ml_registry import TrainedModel

    _broken_tensorflow(monkeypatch)
    model = TrainedModel(model_id="m", task="neural_network", model_type="mlp", estimator=object(),
                         feature_names=["a"], target_name="b", target_classes=None, encoded_columns=None,
                         config={}, performance={}, feature_importance=None, n_train=1, n_test=1,
                         dataset_shape=(2, 2))
    with pytest.raises(Exception) as excinfo:
        _export_tflite(model)
    assert getattr(excinfo.value, "code", None) == "TENSORFLOW_UNAVAILABLE"
