# DataVortex

DataVortex est un visualiseur de données interactif permettant d'uploader, explorer, analyser, filtrer, enrichir et exporter des fichiers de données (CSV, Excel, JSON) via une interface web.

Le projet est actuellement au stade **MVP complet** : les quatre phases de développement (upload/stats, visualisations, filtrage/colonnes calculées, export/CI) sont terminées et testées.

## Stack technique

- **Backend** : FastAPI (Python) + [uv](https://docs.astral.sh/uv/) pour la gestion des dépendances
- **Frontend** : React + Vite + Plotly.js (via `react-plotly.js`) + Tailwind CSS
- **Traitement de données** : Pandas / NumPy / SciPy
- **Export graphiques** : Kaleido (PNG/SVG statiques) + Plotly (HTML interactif)
- **Tests** : pytest (backend), ESLint (frontend)
- **CI/CD** : GitHub Actions

## Structure du projet

```
datavortex/
├── .github/workflows/     # CI (tests) et build Docker
├── backend/
│   ├── app/
│   │   ├── main.py        # Routes FastAPI
│   │   ├── parsing.py     # Détection séparateur/encoding, parsing CSV/Excel/JSON
│   │   ├── stats.py       # Statistiques descriptives par colonne
│   │   ├── plotting.py    # Génération des figures Plotly (1D/2D/3D)
│   │   ├── filtering.py   # Évaluation des filtres (AND/OR imbriqués)
│   │   ├── formulas.py    # Moteur de formules sûr (colonnes calculées)
│   │   ├── session_store.py
│   │   ├── serialize.py
│   │   └── errors.py
│   ├── tests/              # Suite pytest (unitaires + API)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/     # UploadZone, Dashboard, PlotBuilder, FilterBuilder, ...
│   │   ├── api/             # Client Axios + helpers de téléchargement
│   │   ├── main.jsx         # Point d'entrée Vite
│   │   └── index.jsx        # Montage React
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── specs/                   # Spécifications du projet (source des phases)
```

## Installation complète

### Prérequis

| Outil | Version requise | Notes |
|---|---|---|
| Python | ≥ 3.10 | pour le backend |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | dernière version | gestion des dépendances Python |
| Node.js | ≥ 18 (idéalement 20 LTS) | pour le frontend — voir [Limitations](#limitations-connues) |
| npm | fourni avec Node.js | |
| Docker (optionnel) | dernière version | pour `docker-compose up` |

### 1. Cloner le dépôt

```bash
git clone git@github.com:nils-malmberg/datavortex.git
cd datavortex
```

### 2. Backend

```bash
cd backend
uv sync --extra dev   # installe les dépendances de prod + dev (pytest, ruff, black)
```

### 3. Frontend

```bash
cd frontend
npm install
```

## Lancer le projet en local

### Backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

L'API est disponible sur http://localhost:8000 (documentation interactive OpenAPI sur `/docs`).

> **Si `uv run` échoue** (par ex. confinement snap sur certaines distributions
> Linux), utilisez directement l'environnement virtuel créé par `uv sync` :
> `.venv/bin/uvicorn app.main:app --reload`.

### Frontend

```bash
cd frontend
npm run dev
```

L'application est disponible sur http://localhost:5173 (le proxy Vite redirige `/api/*` vers `http://localhost:8000`).

### Avec Docker

```bash
docker-compose up --build
```

- Frontend (nginx, sert le build de production + proxy `/api`) : http://localhost:8080
- Backend seul : http://localhost:8000

### Lancer les tests

```bash
cd backend
uv run pytest -v          # 40 tests : formules, filtres, API de bout en bout
uv run ruff check .       # lint

cd frontend
npm run lint
npm run build
```

## Flux utilisateur

1. **Accueil** : upload d'un fichier CSV/Excel/JSON via drag & drop
2. **Détection du séparateur** (CSV uniquement) : confirmation ou correction du séparateur détecté automatiquement, aperçu live
3. **Dashboard** : aperçu des données (100 premières lignes) et cinq onglets :
   - **Stats** : statistiques descriptives par colonne
   - **Visualisations** : construction de graphiques 1D/2D/3D
   - **Filtres** : conditions combinées en ET/OU
   - **Colonnes calculées** : formules avec aperçu avant validation
   - **Export** : téléchargement CSV et graphiques

Un filtre actif et les colonnes calculées s'appliquent automatiquement à l'aperçu, aux statistiques, aux graphiques et à l'export — sans jamais modifier les données sources tant que la session est active.

## Exemples d'utilisation

### Filtrer les données

Dans l'onglet **Filtres**, ajouter une ou plusieurs conditions, par exemple :

- `species` `égal à` `setosa`
- `age` `entre` `18` et `65`
- `email` `contient` `@gmail.com`

Combiner plusieurs conditions avec **ET** ou **OU**. Le nombre de lignes sélectionnées s'affiche en temps réel.

### Créer une colonne calculée

Dans l'onglet **Colonnes calculées**, référencer les colonnes existantes entre accolades :

| Formule | Résultat |
|---|---|
| `{price} * {quantity}` | total de la ligne |
| `{age} > 18` | booléen (majeur) |
| `{salary} * 1.1` | salaire +10% |
| `if({gender} == "M", "Homme", "Femme")` | conversion catégorielle |
| `round(sqrt({value}), 2)` | transformation mathématique |
| `upper({name})` | mise en majuscule |

L'aperçu du résultat s'affiche avant de valider l'ajout définitif de la colonne.

### Exporter

- **CSV** (onglet Export) : choix du séparateur et de l'encoding (UTF-8/Latin-1), inclut automatiquement les filtres actifs et les colonnes calculées, avec le filtre appliqué documenté en commentaire en tête de fichier.
- **Graphiques** (onglet Visualisations) : PNG, SVG ou HTML interactif, via les boutons de téléchargement sous chaque graphique.

## Visualisations disponibles

- **1D** : histogramme, box plot, violin plot, densité (KDE), bar chart, pie chart — avec regroupement optionnel par catégorie
- **2D** : scatter plot (couleur/taille par colonne), line chart, heatmap de corrélation, hexbin (densité 2D), bar chart groupé, bubble chart
- **3D** : scatter 3D, surface plot

## Filtrage & colonnes calculées

- **Filtres** : opérateurs numériques (`=`, `≠`, `>`, `<`, `≥`, `≤`, `entre`, `dans/hors liste`), texte (`contient`, `commence/finit par`, `regex`), booléens, dates (`année/mois/jour`), valeurs manquantes — combinables en ET/OU
- **Colonnes calculées** : moteur de formules sûr (parsing AST Python, jamais `eval`/`exec`) supportant `+ - * / % **`, comparaisons, `and/or/not`, fonctions mathématiques (`abs`, `round`, `sqrt`, `log`, trigonométrie...), fonctions texte (`upper`, `lower`, `concat`, `replace`, `substring`...) et `if(condition, si_vrai, si_faux)`

## Gestion des erreurs

Toutes les erreurs API renvoient un JSON cohérent :

```json
{"error": {"code": "SESSION_NOT_FOUND", "message": "Session '...' introuvable ou expirée."}}
```

Codes courants : `SESSION_NOT_FOUND`, `DATA_NOT_PARSED`, `COLUMN_NOT_FOUND`, `SEPARATOR_LIKELY_WRONG`, `INVALID_FORMULA`, `COLUMN_ALREADY_EXISTS`, `UNKNOWN_OPERATOR`, `INVALID_FILTER_VALUE`.

## Limitations connues

- **Node.js** : le développement a révélé que Node 12 (souvent la version par défaut via `apt` sur certaines distributions Ubuntu/Debian) est incompatible avec les outils modernes (Vite, ESLint récent). **Node 18+ est requis**, idéalement 20 LTS. Si votre `node --version` affiche moins que ça, installez une version récente via [nvm](https://github.com/nvm-sh/nvm) ou un binaire officiel, sans toucher au Node système.
- **`uv run`** : dans certains environnements avec un `uv` installé via snap (confinement strict), `uv run <commande>` peut échouer silencieusement. Contournement : appeler directement le binaire dans `.venv/bin/` (voir section "Lancer le projet en local").
- **Sessions en mémoire** : les données uploadées sont stockées en RAM côté serveur, par session (UUID), avec une expiration après 1h d'inactivité. Redémarrer le backend efface toutes les sessions actives. Il n'y a pas de base de données persistante — ce n'est pas prévu pour un usage multi-utilisateurs en production telle quelle.
- **Fichiers volumineux** : la limite d'upload est fixée à 100MB. Les formules sur colonnes calculées s'évaluent ligne par ligne (`DataFrame.apply`), ce qui reste correct pour des jeux de données de taille raisonnable mais n'est pas optimisé pour des millions de lignes.
- **Bundle frontend** : `plotly.js` (bundle complet, nécessaire pour les graphiques 3D) représente à lui seul près de 5MB avant compression gzip. Un découpage en chunks (`import()` dynamique) améliorerait le temps de chargement initial mais n'a pas été fait pour ce MVP.
- **Déploiement** : `deploy.yml` valide uniquement que les images Docker se construisent (`docker build`), il ne pousse vers aucun registre ni ne déploie sur une plateforme (Heroku/Vercel/etc.) — aucun credential de déploiement n'est configuré pour ce dépôt à ce stade.
- **Authentification** : aucune. Le projet est prévu pour un usage local/dev, pas pour être exposé publiquement sans ajouts de sécurité (auth, rate limiting, etc.).

## Roadmap

- **Phase 1 (MVP)** : upload, parsing, détection séparateur, stats descriptives, aperçu tableau ✅
- **Phase 2** : visualisations interactives (1D, 2D, 3D) avec Plotly, export PNG/SVG/HTML ✅
- **Phase 3** : filtrage avancé (Filter Builder) et colonnes calculées (formules) ✅
- **Phase 4** : export CSV avancé, CI/CD (GitHub Actions), Docker, documentation complète ✅
- **Futur possible** : sessions persistantes (base de données), authentification, filtres imbriqués avec parenthèses dans l'UI (le backend les supporte déjà), agrégations sur colonnes calculées, déploiement réel (choix de plateforme à faire), découpage du bundle frontend

Voir le dossier [`specs/`](specs) pour le détail complet des spécifications d'origine par phase.

## Historique des tests manuels

<details>
<summary>Phase 1 — Upload, parsing, stats</summary>

- Upload d'un CSV séparé par virgules : séparateur `,` détecté correctement
- Upload d'un CSV séparé par points-virgules : séparateur `;` détecté correctement
- Upload d'un TSV (tabulations) : séparateur `\t` détecté correctement
- Parsing avec un mauvais séparateur : erreur `SEPARATOR_LIKELY_WRONG` (HTTP 422)
- Accès à une session inexistante : erreur `SESSION_NOT_FOUND` (HTTP 404)
- Aperçu des données et statistiques (numériques, chaînes, booléens, dates, valeurs manquantes) vérifiés manuellement contre les données sources
- Flux complet testé de bout en bout à travers le proxy Vite

</details>

<details>
<summary>Phase 2 — Visualisations</summary>

Testés avec `iris.csv` (150 lignes, 4 colonnes numériques, 1 catégorielle) :

- Histogramme de `sepal_length` (bins configurables)
- Box plot de `sepal_length` groupé par `species` (3 traces)
- Densité KDE de `sepal_length`, pie chart de `species`
- Scatter plot coloré par `species`, heatmap de corrélation
- Bubble chart, hexbin, scatter 3D, surface plot
- Bar chart groupé (testé avec un second jeu de données à deux colonnes catégorielles)
- Export PNG/SVG/HTML vérifiés (PNG inspecté visuellement)
- Bug trouvé et corrigé : les `<select>` requis (Axe X/Y/Z) démarraient avec un
  état React vide non synchronisé avec l'affichage du navigateur, bloquant
  silencieusement la génération des graphiques 2D/3D (et 1D). Confirmé et
  corrigé via un test dans un vrai navigateur (Playwright + Chromium).

</details>

<details>
<summary>Phase 3 — Filtrage & colonnes calculées</summary>

Testé dans un vrai navigateur (Playwright + Chromium) avec `iris.csv` :

- Filtre simple et imbriqué (ET/OU), opérateur `in`, réinitialisation
- Colonne calculée avec formule arithmétique et conditionnelle (`if(...)`)
- Le filtre actif et les colonnes calculées restent synchronisés entre les
  onglets Stats/Visualisations/Export
- Erreurs vérifiées : colonne inconnue, nom dupliqué, division par zéro par
  ligne (sans interrompre le calcul global)
- Tentatives d'échapper au bac à sable de formules (`__import__`, accès
  `__class__`, list comprehension, `lambda`) toutes rejetées

</details>

<details>
<summary>Phase 4 — Export & CI/CD</summary>

- Export CSV avec filtre + colonne calculée : séparateur `;`, encoding
  Latin-1, commentaire de filtre en tête de fichier, contenu vérifié
  (uniquement les lignes filtrées, nouvelle colonne présente)
- Export du graphique filtré en PNG/SVG/HTML, tous vérifiés
- Bug trouvé et corrigé : une condition de filtre tout juste ajoutée (encore
  vide) déclenchait une requête invalide (HTTP 400) avant que l'utilisateur
  ait fini de la configurer ; les conditions incomplètes sont désormais
  ignorées jusqu'à être valides
- 40 tests pytest (formules, filtres, API de bout en bout) exécutés avec
  succès ; `ruff check` et `npm run lint`/`npm run build` vérifiés localement
  avant de committer les workflows CI

</details>
