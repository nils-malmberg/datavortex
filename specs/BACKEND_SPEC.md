# Backend DataVortex - Spécification FastAPI

## Structure des routes

### Upload & Parsing
- `POST /api/upload` - Upload fichier
- `POST /api/parse` - Parse avec détection séparateur
- `POST /api/validate-separator` - Confirmer séparateur

### Données
- `GET /api/data/{id}` - Récupérer données
- `GET /api/data/{id}/preview` - Aperçu
- `POST /api/data/{id}/filter` - Appliquer filtre
- `POST /api/data/{id}/columns` - Créer colonne calculée

### Statistiques
- `GET /api/stats/{id}` - Stats globales
- `GET /api/column/{id}/{col_name}/stats` - Stats colonne
- `GET /api/column/{id}/{col_name}/histogram` - Histogramme

### Visualisations
- `POST /api/plot/1d` - Graphique 1D (histogramme, box plot, etc)
- `POST /api/plot/2d` - Graphique 2D (scatter, line, etc)
- `POST /api/plot/3d` - Graphique 3D

### Export
- `POST /api/export/csv` - Export CSV
- `POST /api/export/plot` - Export image graphique

## Technologies
- pandas/polars pour traitement données
- numpy/scipy pour stats
- plotly pour visualisations