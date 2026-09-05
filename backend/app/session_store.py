"""Stockage en mémoire des sessions utilisateur (pas de base de données).

Chaque upload crée une session identifiée par un UUID. Les sessions expirent
après une heure d'inactivité (nettoyage paresseux effectué à chaque upload).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

SESSION_TTL_SECONDS = 60 * 60  # 1h d'inactivité


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
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_accessed = time.time()


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
