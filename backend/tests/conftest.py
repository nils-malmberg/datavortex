import pytest

from app.async_tasks import registry
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


@pytest.fixture(autouse=True)
def _clear_task_registry():
    """Même raison pour le registre de tâches de fond (Phase 9) : c'est un
    singleton, et une tâche laissée par un test fausserait les compteurs
    remontés par /api/health dans le suivant.
    """
    registry.clear()
    yield
    registry.clear()
