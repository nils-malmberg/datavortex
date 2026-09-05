# Phase 1 : MVP - DataVortex

## Objectif
Avoir un prototype fonctionnel permettant d'uploader, parser et afficher stats basiques.

## Tâches Backend
1. Setup FastAPI avec CORS
2. Route upload simple (fichier dans mémoire)
3. Détection séparateur (chardet + essai)
4. Parse CSV en pandas DataFrame
5. Stats basiques (count, type, min/max pour numériques)

## Tâches Frontend
1. Setup React/Vue + Vite
2. Zone drag & drop
3. Formulaire pour séparateur
4. Tableau preview des données
5. Affichage stats basiques en panneau

## Testing
- Tester avec CSV standard (virgule, point-virgule, tab)