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

> Si `uv run` ne fonctionne pas dans votre environnement (ex: confinement snap),
> utilisez directement l'environnement virtuel créé par `uv sync` :
> `.venv/bin/uvicorn app.main:app --reload`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

L'application est disponible sur http://localhost:5173 (proxy API configuré vers `http://localhost:8000`).

## Flux utilisateur

1. **Accueil** : upload d'un fichier CSV via drag & drop
2. **Détection du séparateur** : confirmation ou correction du séparateur détecté automatiquement
3. **Dashboard** : aperçu des données (100 premières lignes), onglet **Stats**
   (statistiques descriptives par colonne) et onglet **Visualisations**
4. **Visualisations** : choix du type de graphique (1D/2D/3D), mapping des
   colonnes, aperçu interactif en temps réel, export PNG/SVG/HTML
5. **Filtres** : conditions combinées en ET/OU, appliquées en temps réel à
   l'aperçu, aux stats et aux graphiques
6. **Colonnes calculées** : formules avec référence aux colonnes (`{col}`),
   opérateurs et fonctions, aperçu avant validation

## Visualisations disponibles (Phase 2)

- **1D** : histogramme, box plot, violin plot, densité (KDE), bar chart,
  pie chart — avec regroupement optionnel par catégorie (`group_by`)
- **2D** : scatter plot (couleur/taille par colonne), line chart, heatmap
  de corrélation, hexbin (densité 2D), bar chart groupé, bubble chart
- **3D** : scatter 3D, surface plot
- **Export** : PNG et SVG (via kaleido) et HTML interactif (Plotly)

## Filtrage & colonnes calculées (Phase 3)

- **Filtres** : opérateurs numériques (`=`, `≠`, `>`, `<`, `≥`, `≤`, `entre`,
  `dans/hors liste`), texte (`contient`, `commence/finit par`, `regex`),
  booléens, dates (`année/mois/jour`), valeurs manquantes — combinés en
  ET/OU. Un filtre actif s'applique automatiquement à l'aperçu, aux stats
  et aux graphiques (le dataset original reste intact).
- **Colonnes calculées** : moteur de formules sûr (parsing AST Python, sans
  `eval`/`exec`) supportant `+ - * / % **`, comparaisons, `and/or/not`,
  fonctions mathématiques (`abs`, `round`, `sqrt`, `log`, trigonométrie...),
  fonctions texte (`upper`, `lower`, `concat`, `replace`, `substring`...) et
  `if(condition, si_vrai, si_faux)`. Aperçu sur les premières lignes avant
  d'ajouter définitivement la colonne.

## Tests manuels effectués (Phase 1)

- Upload d'un CSV séparé par virgules : séparateur `,` détecté correctement
- Upload d'un CSV séparé par points-virgules : séparateur `;` détecté correctement
- Upload d'un TSV (tabulations) : séparateur `\t` détecté correctement
- Parsing avec un mauvais séparateur : erreur `SEPARATOR_LIKELY_WRONG` renvoyée (HTTP 422)
- Accès à une session inexistante : erreur `SESSION_NOT_FOUND` renvoyée (HTTP 404)
- Aperçu des données et statistiques (numériques, chaînes, booléens, dates,
  valeurs manquantes) vérifiés manuellement contre les données sources
- Flux complet testé de bout en bout à travers le proxy Vite (upload → parse
  → preview → stats)

## Tests manuels effectués (Phase 2)

Testés avec le jeu de données `iris.csv` (150 lignes, 4 colonnes numériques,
1 colonne catégorielle `species`) :

- Histogramme de `sepal_length` (bins configurables)
- Box plot de `sepal_length` groupé par `species` (3 traces, une par espèce)
- Densité KDE de `sepal_length`
- Pie chart de `species`
- Scatter plot `sepal_length` vs `petal_length` coloré par `species`
- Heatmap de corrélation sur les 4 colonnes numériques
- Bubble chart et hexbin sur `sepal_length`/`petal_length`
- Scatter 3D et surface plot sur `sepal_length`/`sepal_width`/`petal_length`
- Bar chart groupé testé avec un second jeu de données (`region`/`product`)
  pour valider le regroupement à deux colonnes catégorielles distinctes
- Export PNG, SVG et HTML d'un graphique, fichiers vérifiés (image PNG
  valide 900×600, SVG valide, HTML contenant Plotly)
- Cas d'erreur vérifiés : colonne inexistante, colonne non numérique pour
  un scatter, bubble chart sans `size_by`, bar groupé avec `x` = `color_by`
- Flux complet retesté de bout en bout à travers le proxy Vite

## Tests manuels effectués (Phase 3)

Testés dans un vrai navigateur (Playwright + Chromium) avec `iris.csv` :

- Filtre simple (`species = setosa`) : 50/150 lignes, badge "filtré" affiché
  et synchronisé dans l'aperçu, les stats et les graphiques
- Filtre imbriqué ET (`sepal_length > 5 ET species = setosa`) et opérateur
  `in` (`species in [setosa, virginica]`) vérifiés via curl
- Réinitialisation du filtre (retour à 150/150)
- Colonne calculée `sepal_area = {sepal_length} * {sepal_width}` : aperçu
  live puis ajout définitif, visible immédiatement dans l'aperçu et les
  stats sans perdre le filtre actif
- Formule conditionnelle `if({sepal_length} > 5.5, "big", "small")` :
  aperçu live correct
- Fonctions `upper()`, `round(sqrt(...), 2)` vérifiées via curl
- Erreurs vérifiées : colonne inconnue dans une formule, nom de colonne
  dupliqué (bloqué sauf `overwrite`), division par zéro (gérée ligne par
  ligne sans interrompre le calcul)
- Tentatives d'échapper au bac à sable de formules (`__import__`, accès
  `__class__`, list comprehension, `lambda`) toutes rejetées

## Roadmap

- **Phase 1 (MVP)** : upload, parsing, détection séparateur, stats descriptives, aperçu tableau ✅
- **Phase 2** : visualisations interactives (1D, 2D, 3D) avec Plotly, export PNG/SVG/HTML ✅
- **Phase 3** : filtrage avancé (Filter Builder) et colonnes calculées (formules) ✅
- **Phase 4** : export avancé, CI/CD (GitHub Actions), documentation, Docker

Voir le dossier [`specs/`](../specs) pour le détail complet des spécifications.
