# Contribuer à DataVortex

Merci de l'intérêt porté à DataVortex. Ce guide couvre la mise en place de l'environnement de développement, les attentes en matière de tests et de style, et le processus de pull request.

## Structure du dépôt

```
datavortex/
├── backend/          # API FastAPI (Python)
├── frontend/         # Interface React/Vite
├── datavortex-cli/   # Paquet de distribution (uv tool), assemble backend + frontend compilé
├── examples/         # Jeux de données de démonstration
├── specs/            # Spécifications d'origine, par phase
└── .github/workflows/ # CI (tests, lint, build)
```

## Mise en place

### Backend

```bash
cd backend
uv sync --extra dev
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000, /docs pour Swagger
```

> `uv run` peut échouer silencieusement dans certains environnements confinés (snap) : si c'est votre cas, appelez directement les binaires de `.venv/bin/` comme ci-dessus.

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxy /api vers :8000
```

Node.js 18+ requis (20 LTS recommandé) — le Node fourni par défaut sur certaines distributions Linux (souvent la v12 via `apt`) est incompatible avec Vite/ESLint.

### CLI (datavortex-cli)

Uniquement nécessaire si vous travaillez sur l'empaquetage/distribution lui-même — voir [datavortex-cli/README.md](datavortex-cli/README.md).

## Tests

Aucune pull request n'est acceptée sans que la suite de tests concernée passe.

```bash
# Backend
cd backend
.venv/bin/pytest -v
.venv/bin/ruff check .

# Frontend
cd frontend
npm run lint
npm run build

# CLI
cd datavortex-cli
uv sync --extra dev
.venv/bin/pytest -v
```

### Ce qu'on attend d'un nouveau test

Pour toute nouvelle statistique, métrique ML ou agrégation, un test qui vérifie seulement « la route répond 200 avec une forme plausible » n'est pas suffisant. Calculez la même chose indépendamment (appel direct à `scipy`/`sklearn`/`numpy`/`pandas`, ou implémentation de référence isolée) et comparez avec `pytest.approx`. Cette exigence a permis de détecter, au fil des phases, des bugs réels qu'un simple test de fumée aurait laissés passer (un pourcentage de tableau croisé qui ne sommait pas à 100%, un score de qualité incohérent avec la note affichée, une forêt aléatoire sans limite de profondeur qui rendait le produit inutilisable sur 100k lignes).

Pour toute revendication de performance (« ça marche sur de gros fichiers »), mesurez réellement le temps d'exécution sur un jeu de données représentatif plutôt que de supposer qu'un code raisonnable passera à l'échelle — plusieurs algorithmes de ce projet (SVM, processus gaussien, clustering hiérarchique, mean shift, score de silhouette) ont une complexité quadratique ou pire, qui ne se voit qu'au chronométrage, pas à la lecture du code.

## Style de code

- **Backend** : `ruff check .` doit passer sans erreur (voir `[tool.ruff]` dans `backend/pyproject.toml` pour la configuration exacte : ligne à 120 caractères, règles E/F/W/I).
- **Frontend** : `npm run lint` (ESLint + règles React/React Hooks) doit passer sans erreur. Tailwind CSS pour le style — pas de CSS-in-JS ni de fichiers `.css` par composant.
- Pas de commentaire qui répète ce que le code dit déjà — un commentaire n'a de valeur que s'il explique un choix non évident (contrainte cachée, contournement d'un bug spécifique, comportement qui surprendrait un lecteur).
- Les erreurs métier passent par `AppError` (`backend/app/errors.py`), jamais par une exception non gérée qui remonterait telle quelle au client.

## Processus de Pull Request

1. Une branche par changement, nommée `feat/...`, `fix/...` ou `docs/...` selon la nature du changement.
2. Commits atomiques avec un message clair en français (convention du projet), décrivant le *pourquoi* autant que le *quoi*.
3. La CI (`test.yml`, GitHub Actions) doit passer : pytest + ruff côté backend, ESLint + build côté frontend.
4. Dans la description de la PR : ce qui change, comment c'est testé (y compris la vérification indépendante pour tout calcul numérique nouveau), et tout écart volontaire par rapport à une spec ou une demande initiale, avec la raison.
5. Une seule fonctionnalité/correction par PR — un refactor sans rapport avec le correctif ne doit pas s'y glisser.

## Signaler un bug

Ouvrez une [issue GitHub](https://github.com/nils-malmberg/datavortex/issues) avec :
- le message d'erreur exact (et le `code` de l'enveloppe d'erreur JSON si c'est une erreur API),
- les étapes pour reproduire,
- la taille/structure du jeu de données si le bug semble lié au volume de données,
- ce qui était attendu vs. ce qui s'est produit.

## Licence

En contribuant, vous acceptez que vos contributions soient distribuées sous licence MIT (voir [LICENSE](LICENSE)).
