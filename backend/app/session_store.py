"""Gestionnaire de sessions utilisateur en mémoire (pas de base de données).

Chaque upload crée une session identifiée par un UUID, isolée des autres
(données, filtre actif, colonnes calculées). Permet plusieurs fichiers
ouverts en parallèle (Phase 5 : onglets multi-fichiers côté frontend).
Les sessions expirent après une heure d'inactivité (nettoyage paresseux à
chaque création), et un nombre maximal de sessions simultanées est imposé
pour borner la mémoire utilisée par le serveur.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.errors import AppError

SESSION_TTL_SECONDS = 60 * 60  # 1h d'inactivité
MAX_SESSIONS = 10  # nombre maximal de fichiers ouverts simultanément


@dataclass
class Session:
    session_id: str
    filename: str
    file_kind: str  # "csv" | "excel" | "json"
    raw_bytes: bytes
    encoding: str
    detected_separator: Optional[str] = None
    separator: Optional[str] = None
    df: Optional[pd.DataFrame] = None
    active_filter: Optional[object] = None
    filtered_df: Optional[pd.DataFrame] = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_accessed = time.time()

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
        session = Session(
            session_id=session_id,
            filename=filename,
            file_kind=file_kind,
            raw_bytes=raw_bytes,
            encoding=encoding,
            detected_separator=detected_separator,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time.time() - session.last_accessed > SESSION_TTL_SECONDS:
            del self._sessions[session_id]
            return None
        session.touch()
        return session

    def delete(self, session_id: str) -> None:
        """Supprime une session immédiatement (ex : fermeture d'un onglet). Idempotent."""
        self._sessions.pop(session_id, None)

    def _sweep_expired(self) -> None:
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_accessed > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]


# Instance globale unique partagée par toute l'application.
store = SessionStore()
