"""Registre des modèles ML entraînés (Phase 8.1).

Chaque appel de régression/classification/clustering/réseau de neurones
entraîne un modèle qui, jusqu'ici, était utilisé une fois puis jeté. Pour
permettre son export a posteriori (joblib/pickle/JSON/ONNX/TFLite, métadonnées,
script de reproduction) sans devoir tout ré-entraîner, on le garde en mémoire
dans la session, indexé par un `model_id` renvoyé au frontend.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.errors import AppError


@dataclass
class TrainedModel:
    model_id: str
    task: str  # "regression" | "classification" | "clustering" | "neural_network"
    model_type: str
    estimator: Any  # estimateur scikit-learn (éventuellement un Pipeline), ou modèle Keras
    feature_names: list[str]
    target_name: Optional[str]
    target_classes: Optional[list[str]]
    encoded_columns: Optional[list[str]]
    config: dict
    performance: dict
    feature_importance: Optional[list[dict]]
    n_train: int
    n_test: int
    dataset_shape: tuple[int, int]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def register_model(session, **kwargs) -> str:
    model_id = str(uuid.uuid4())
    session.models[model_id] = TrainedModel(model_id=model_id, **kwargs)
    return model_id


def get_model(session, model_id: str) -> TrainedModel:
    model = session.models.get(model_id)
    if model is None:
        raise AppError(
            404,
            "MODEL_NOT_FOUND",
            "Modèle introuvable : il a peut-être expiré ou la session a été rechargée. Relancez l'analyse.",
        )
    return model
