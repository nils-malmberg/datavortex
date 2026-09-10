"""Export CSV en flux (Phase 9).

L'export historique construisait l'intégralité du CSV dans un `io.StringIO`,
puis l'encodait en octets : pour 500 000 lignes, cela signifie détenir
simultanément le DataFrame, sa représentation texte complète et sa version
encodée — un pic mémoire de plusieurs fois la taille du fichier, au moment
précis où la mémoire est déjà sous tension.

Ici, le CSV est produit et transmis par tranches de lignes : à aucun instant
plus d'une tranche n'existe en mémoire, et le navigateur commence à recevoir
des données avant que la dernière ligne ne soit formatée.
"""
from __future__ import annotations

from typing import Any, Iterator, Optional

import pandas as pd

# Compromis entre le coût fixe par tranche (appel pandas, en-têtes HTTP) et le
# pic mémoire qu'une tranche représente. 10 000 lignes tiennent dans quelques
# mégaoctets de texte quelle que soit la largeur raisonnable du tableau.
DEFAULT_CHUNK_ROWS = 10_000


def iter_csv_chunks(
    df: pd.DataFrame,
    separator: str = ",",
    encoding: str = "utf-8",
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    header_comment: Optional[str] = None,
) -> Iterator[bytes]:
    """Produit le CSV tranche par tranche, encodé en octets.

    L'en-tête de colonnes n'est écrit qu'avec la première tranche ; les
    suivantes ne portent que des lignes de données.
    """
    if chunk_rows < 1:
        chunk_rows = DEFAULT_CHUNK_ROWS

    if header_comment:
        yield f"# {header_comment}\n".encode(encoding, errors="replace")

    total = int(df.shape[0])

    # Un tableau vide doit tout de même produire sa ligne d'en-tête, sinon le
    # fichier exporté ne contient rien du tout et l'utilisateur croit à un échec.
    if total == 0:
        yield df.head(0).to_csv(sep=separator, index=False).encode(encoding, errors="replace")
        return

    for start in range(0, total, chunk_rows):
        chunk = df.iloc[start:start + chunk_rows]
        text = chunk.to_csv(sep=separator, index=False, header=(start == 0))
        yield text.encode(encoding, errors="replace")


def validate_encoding(encoding: str) -> None:
    """Vérifie l'encoding avant d'ouvrir le flux.

    Une fois la réponse en flux commencée, le statut HTTP est déjà parti : une
    erreur d'encoding se traduirait par un fichier tronqué sans explication.
    Mieux vaut échouer proprement avant le premier octet.
    """
    "".encode(encoding)


def stream_headers(filename: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        # Le total n'est pas connu à l'avance : on l'annonce explicitement pour
        # que le navigateur n'attende pas un `Content-Length`.
        "X-Accel-Buffering": "no",
    }


def estimate_csv_bytes(df: pd.DataFrame, sample_rows: int = 200) -> Optional[int]:
    """Estime la taille du CSV à partir d'un échantillon.

    Sert uniquement à informer l'interface (« ~120 Mo ») ; renvoie None quand
    l'estimation n'a pas de sens.
    """
    total = int(df.shape[0])
    if total == 0:
        return None
    sample = df.head(min(sample_rows, total))
    sample_bytes = len(sample.to_csv(index=False).encode("utf-8", errors="replace"))
    return int(sample_bytes / max(1, sample.shape[0]) * total)


def csv_stream_metrics(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "estimated_bytes": estimate_csv_bytes(df),
        "chunk_rows": DEFAULT_CHUNK_ROWS,
    }
