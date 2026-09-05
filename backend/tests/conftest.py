import pytest

from app.session_store import store


@pytest.fixture(autouse=True)
def _clear_session_store():
    """Isole chaque test : le store de sessions est un singleton partagé par
    toute l'app (comme en production), donc il faut le vider entre les tests
    pour éviter qu'ils n'interfèrent entre eux (ex : la limite MAX_SESSIONS).
    """
    store._sessions.clear()
    yield
    store._sessions.clear()
