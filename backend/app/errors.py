"""Gestion cohérente des erreurs de l'API DataVortex.

Toutes les erreurs métier renvoient un JSON de la forme :
    {"error": {"code": "SOME_CODE", "message": "Message lisible"}}
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Exception métier avec un code d'erreur stable et un message clair."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Erreur interne inattendue : {exc}",
            }
        },
    )


# Erreurs courantes préconstruites -------------------------------------------------

def session_not_found(session_id: str) -> AppError:
    return AppError(
        status_code=404,
        code="SESSION_NOT_FOUND",
        message=f"Session '{session_id}' introuvable ou expirée.",
    )


def not_parsed_yet(session_id: str) -> AppError:
    return AppError(
        status_code=409,
        code="DATA_NOT_PARSED",
        message=(
            f"La session '{session_id}' n'a pas encore été parsée. "
            "Appelez POST /api/parse avant d'accéder aux données."
        ),
    )


def column_not_found(col_name: str) -> AppError:
    return AppError(
        status_code=404,
        code="COLUMN_NOT_FOUND",
        message=f"Colonne '{col_name}' introuvable dans le jeu de données.",
    )
