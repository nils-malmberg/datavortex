"""Gestionnaire de sessions utilisateur en mémoire (pas de base de données).

Chaque upload crée une session identifiée par un UUID, isolée des autres
(données, filtre actif, colonnes calculées). Permet plusieurs fichiers
ouverts en parallèle (Phase 5 : onglets multi-fichiers côté frontend).
Les sessions expirent après une heure d'inactivité (nettoyage paresseux à
chaque création), et un nombre maximal de sessions simultanées est imposé
pour borner la mémoire utilisée par le serveur.
"""
from __future__ import annotations

import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.errors import AppError

SESSION_TTL_SECONDS = 60 * 60  # 1h d'inactivité
MAX_SESSIONS = 10  # nombre maximal de fichiers ouverts simultanément

# Au-delà de cette taille, le fichier source est déversé sur disque au lieu
# d'être conservé en mémoire (Phase 9). Une session détient sinon deux copies
# des données : les octets bruts *et* le DataFrame analysé. Sur un fichier de
# 500MB, ce doublon est exactement ce qui fait dépasser le budget mémoire.
# Le fichier sur disque reste nécessaire : changer de séparateur ré-analyse la
# source, et Polars sait la lire par chemin sans la charger en RAM.
# Réglable via DATAVORTEX_SPILL_MB, comme le seuil d'analyse rapide.
SPILL_THRESHOLD_BYTES = int(float(os.environ.get("DATAVORTEX_SPILL_MB", "50")) * 1024 * 1024)


@dataclass
class Session:
    session_id: str
    filename: str
    file_kind: str  # "csv" | "excel" | "json"
    raw_bytes: bytes
    encoding: str
    # Chemin du fichier source déversé sur disque, quand il était trop gros pour
    # rester en mémoire. Mutuellement exclusif avec `raw_bytes` non vide.
    spill_path: Optional[str] = None
    source_size_bytes: int = 0
    detected_separator: Optional[str] = None
    separator: Optional[str] = None
    df: Optional[pd.DataFrame] = None
    active_filter: Optional[object] = None
    filtered_df: Optional[pd.DataFrame] = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    # Modèles ML entraînés dans cette session (Phase 8.1), indexés par model_id,
    # pour permettre leur export a posteriori sans tout ré-entraîner.
    models: dict = field(default_factory=dict)

    def touch(self) -> None:
        self.last_accessed = time.time()

    def read_source(self) -> bytes:
        """Octets du fichier source, relus depuis le disque s'ils y ont été déversés.

        À n'appeler que lorsque les octets sont réellement nécessaires (analyse
        Excel/JSON, repli pandas) : sur un fichier déversé, cet appel ramène
        tout en mémoire, ce que `source_path()` permet justement d'éviter.
        """
        if self.spill_path and os.path.exists(self.spill_path):
            with open(self.spill_path, "rb") as handle:
                return handle.read()
        return self.raw_bytes

    def source_path(self) -> Optional[str]:
        """Chemin du fichier source si déversé, sinon None.

        Permet aux moteurs qui lisent par chemin (Polars) d'analyser le fichier
        sans jamais matérialiser son contenu en mémoire Python.
        """
        if self.spill_path and os.path.exists(self.spill_path):
            return self.spill_path
        return None

    def release_source(self) -> None:
        """Supprime le fichier déversé. Idempotent."""
        if self.spill_path:
            try:
                os.unlink(self.spill_path)
            except OSError:
                pass
            self.spill_path = None

    def active_df(self) -> pd.DataFrame:
        """Le DataFrame courant : filtré si un filtre est actif, sinon complet."""
        return self.filtered_df if self.filtered_df is not None else self.df


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        filename: str,
        file_kind: str,
        raw_bytes: bytes,
        encoding: str,
        detected_separator: Optional[str],
        spill: bool = False,
    ) -> Session:
        self._sweep_expired()
        if len(self._sessions) >= MAX_SESSIONS:
            raise AppError(
                429,
                "SESSION_LIMIT_REACHED",
                f"Limite de {MAX_SESSIONS} fichiers ouverts atteinte. "
                "Fermez un onglet avant d'en ouvrir un nouveau.",
            )
        session_id = str(uuid.uuid4())
        spill_path: Optional[str] = None
        source_size = len(raw_bytes)

        if spill and raw_bytes:
            # Le fichier part sur disque et les octets sont relâchés : à partir
            # d'ici, la session ne détient plus qu'une seule copie des données.
            handle, spill_path = tempfile.mkstemp(prefix=f"datavortex_{session_id}_", suffix=".src")
            try:
                with os.fdopen(handle, "wb") as out:
                    out.write(raw_bytes)
            except OSError:
                # Disque plein ou lecture seule : on garde les octets en mémoire
                # plutôt que de faire échouer l'upload.
                try:
                    os.unlink(spill_path)
                except OSError:
                    pass
                spill_path = None
            else:
                raw_bytes = b""

        session = Session(
            session_id=session_id,
            filename=filename,
            file_kind=file_kind,
            raw_bytes=raw_bytes,
            encoding=encoding,
            detected_separator=detected_separator,
            spill_path=spill_path,
            source_size_bytes=source_size,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time.time() - session.last_accessed > SESSION_TTL_SECONDS:
            del self._sessions[session_id]
            session.release_source()
            return None
        session.touch()
        return session

    def delete(self, session_id: str) -> None:
        """Supprime une session immédiatement (ex : fermeture d'un onglet). Idempotent."""
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.release_source()

    def _sweep_expired(self) -> None:
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_accessed > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            # Le fichier déversé doit disparaître avec la session, sinon les
            # sessions expirées laissent grossir le répertoire temporaire.
            self._sessions.pop(sid).release_source()


# Instance globale unique partagée par toute l'application.
store = SessionStore()
