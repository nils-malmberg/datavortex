# DataVortex

DataVortex est un visualiseur de données interactif permettant d'uploader, explorer, analyser et manipuler des fichiers de données (CSV, Excel, JSON) via une interface web.

## Stack technique

- **Backend**: FastAPI (Python) + uv pour la gestion des dépendances
- **Frontend**: React + Vite + Plotly.js
- **Traitement de données**: Pandas / NumPy / SciPy

## Structure du projet

```
datavortex/
├── backend/          # API FastAPI
│   ├── app/
│   │   └── main.py
│   └── pyproject.toml
├── frontend/         # Application React (Vite)
│   ├── src/
│   │   ├── components/
│   │   ├── main.jsx
│   │   └── index.jsx
│   └── package.json
└── specs/            # Spécifications du projet
```

## Lancer le projet en local

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

L'API est disponible sur http://localhost:8000 (documentation interactive sur `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

L'application est disponible sur http://localhost:5173 (proxy API configuré vers `http://localhost:8000`).

## Flux utilisateur (Phase 1 - MVP)

1. **Accueil** : upload d'un fichier CSV via drag & drop
2. **Détection du séparateur** : confirmation ou correction du séparateur détecté automatiquement
3. **Dashboard** : aperçu des données (100 premières lignes) et statistiques descriptives par colonne

## Roadmap

- **Phase 1 (MVP)** : upload, parsing, détection séparateur, stats descriptives, aperçu tableau ✅
- **Phase 2** : visualisations interactives (1D, 2D, 3D) avec Plotly
- **Phase 3** : filtrage avancé (Filter Builder) et colonnes calculées (formules)
- **Phase 4** : export avancé, CI/CD (GitHub Actions), documentation, Docker

Voir le dossier [`specs/`](../specs) pour le détail complet des spécifications.
