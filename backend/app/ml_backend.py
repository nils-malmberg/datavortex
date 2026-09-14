"""Disponibilité de TensorFlow et diagnostic quand il manque (Phase 10.4).

Le réseau de neurones et l'export TFLite reposent sur TensorFlow ; tout le
reste du module ML (régression, classification, clustering, PCA — scikit-learn)
s'en passe. Sur certains postes Windows d'entreprise, `import tensorflow`
échoue alors que le paquet est installé : DLL bloquée par une politique
AppLocker, runtime Visual C++ absent, CPU sans AVX… L'erreur remontait alors
comme une « erreur interne » avec la trace brute de `tensorflow.python`, sans
rien dire de la cause ni de ce qu'il restait possible de faire.

Ce module fait trois choses :
- il n'importe TensorFlow qu'à la demande (son import coûte de 5 s à une
  minute selon la machine) et mémorise le résultat, succès ou échec ;
- il traduit un échec d'import en un diagnostic lisible, exposé par
  `GET /api/ml/capabilities` et par les routes qui en dépendent ;
- il permet de désactiver TensorFlow explicitement (`DATAVORTEX_NO_TENSORFLOW=1`,
  ou l'alias `DATAVORTEX_NO_ML=1`), ce qui évite aussi l'import coûteux.
"""
from __future__ import annotations

import os
import platform
import threading
from types import ModuleType

from app.errors import AppError

DISABLE_ENV_VARS = ("DATAVORTEX_NO_TENSORFLOW", "DATAVORTEX_NO_ML")
_TRUTHY = ("1", "true", "yes", "on")

_lock = threading.Lock()
_module: ModuleType | None = None
_status: dict | None = None


def disabled_by() -> str | None:
    """Nom de la variable d'environnement qui désactive TensorFlow, ou None."""
    for name in DISABLE_ENV_VARS:
        if os.environ.get(name, "").strip().lower() in _TRUTHY:
            return name
    return None


def _import_tensorflow() -> ModuleType:  # isolé pour être remplaçable dans les tests
    import tensorflow

    return tensorflow


def diagnose(exc: BaseException) -> tuple[str, str]:
    """(cause, piste) en français pour un `import tensorflow` qui a échoué."""
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    on_windows = platform.system() == "Windows"

    if isinstance(exc, ModuleNotFoundError) and (exc.name or "").split(".")[0] == "tensorflow":
        return (
            "TensorFlow n'est pas installé dans cet environnement.",
            "Réinstallez DataVortex (`uv tool install --force ./datavortex-cli`) ; si le miroir de "
            "paquets de votre entreprise ne fournit pas TensorFlow, voir backend/CORPORATE_SETUP.md.",
        )
    if "dll load failed" in lowered or "pywrap_tensorflow" in lowered or "native tensorflow runtime" in lowered:
        if on_windows:
            return (
                f"TensorFlow est installé mais Windows refuse de charger sa bibliothèque native ({text}).",
                "Causes habituelles sur un poste d'entreprise : le runtime Microsoft Visual C++ 2015-2022 "
                "(msvcp140.dll) n'est pas installé, une politique AppLocker/antivirus bloque les DLL du "
                "dossier utilisateur, ou le processeur (souvent une VM) n'expose pas les instructions AVX. "
                "Détail et contournements : backend/CORPORATE_SETUP.md.",
            )
        return (
            f"TensorFlow est installé mais sa bibliothèque native ne se charge pas ({text}).",
            "Vérifiez que le processeur supporte AVX et que la glibc est récente ; "
            "détail dans backend/CORPORATE_SETUP.md.",
        )
    if "illegal instruction" in lowered or "avx" in lowered:
        return (
            f"Le processeur n'expose pas les instructions requises par TensorFlow ({text}).",
            "TensorFlow exige AVX ; sur une machine virtuelle, demandez l'exposition d'AVX ou "
            "désactivez TensorFlow (DATAVORTEX_NO_TENSORFLOW=1).",
        )
    return (
        f"TensorFlow ne s'importe pas : {text}",
        "Le reste de l'application fonctionne ; pour ne plus tenter l'import, définissez "
        "DATAVORTEX_NO_TENSORFLOW=1. Détail dans backend/CORPORATE_SETUP.md.",
    )


def tensorflow_status(probe: bool = True) -> dict:
    """État de TensorFlow.

    `probe=False` (utilisé par /api/health) ne déclenche jamais l'import :
    tant qu'aucune fonctionnalité ne l'a demandé, `available` vaut None et
    `probed` False. `probe=True` importe une fois pour toutes et mémorise.
    """
    global _module, _status
    env = disabled_by()
    if env:
        return {
            "available": False,
            "probed": True,
            "version": None,
            "disabled_by": env,
            "reason": f"TensorFlow est désactivé par la variable d'environnement {env}.",
            "hint": "Retirez cette variable pour réactiver le réseau de neurones et l'export TFLite.",
        }
    if _status is None and probe:
        with _lock:
            if _status is None:
                try:
                    module = _import_tensorflow()
                except BaseException as exc:  # ImportError, OSError, voire SystemExit (DLL) — tout est diagnostiqué
                    reason, hint = diagnose(exc)
                    _status = {"available": False, "probed": True, "version": None, "disabled_by": None,
                               "reason": reason, "hint": hint}
                else:
                    _module = module
                    _status = {"available": True, "probed": True, "version": getattr(module, "__version__", None),
                               "disabled_by": None, "reason": None, "hint": None}
    if _status is None:
        return {"available": None, "probed": False, "version": None, "disabled_by": None, "reason": None, "hint": None}
    return dict(_status)


def require_tensorflow() -> ModuleType:
    """Le module `tensorflow`, ou une AppError 503 qui explique pourquoi il manque."""
    status = tensorflow_status(probe=True)
    if status["available"]:
        return _module  # type: ignore[return-value]
    raise AppError(503, "TENSORFLOW_UNAVAILABLE", f"{status['reason']} {status['hint']}")


def reset_cache() -> None:
    """Oublie le résultat mémorisé (tests uniquement)."""
    global _module, _status
    with _lock:
        _module = None
        _status = None
