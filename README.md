# DataVortex

**v1.0.2 — Production Ready ✅**

DataVortex est une plateforme interactive de visualisation et d'analyse de données : importez un fichier CSV/Excel/JSON, explorez-le statistiquement, visualisez-le, filtrez-le et enrichissez-le, entraînez des modèles de machine learning, et exportez tout ça — données, graphiques, modèles ou rapport PDF complet — le tout depuis un navigateur, sans envoyer vos données où que ce soit hors de votre machine.

## Fonctionnalités

### 🎯 Import & exploration
- Import CSV / Excel (.xls, .xlsx) / JSON avec détection automatique du séparateur et de l'encoding
- Aperçu paginé avec numéros de ligne (indices originaux préservés après filtrage), recherche, tri, redimensionnement de colonnes
- Statistiques descriptives complètes, corrélations avec p-values (Pearson/Spearman/Kendall), analyse de distribution avec ajustement de lois
- Profilage : score de qualité, détection d'anomalies, motifs de données manquantes, suggestions concrètes

### 📈 Visualisation
- 1D : histogramme, box plot, violin, densité (KDE), barres, camembert
- 2D : nuage de points, ligne, heatmap, hexbin, barres groupées, bulles
- 3D : nuage de points, surface
- Avancé : pair plot, joint plot, ridge plot, essaim/strip
- Lignes de tendance (linéaire, polynomiale, LOWESS) avec bandes de confiance, palettes daltonisme-safe, annotations
- Export PNG / SVG / HTML interactif

### 🔧 Manipulation des données
- Filtres avancés (ET/OU imbriqués, regex, intervalles, listes) appliqués à toute la session
- Colonnes calculées via un moteur de formules sûr (jamais `eval`/`exec`)
- Transformations : binning, encodage, décalage (lag), moyenne glissante
- GroupBy multi-colonnes avec agrégations multiples et tri
- Tableaux croisés dynamiques avec marges et pourcentages

### 🤖 Machine Learning (20 méthodes)
- **Régression (9)** : linéaire, polynomiale, Ridge, Lasso, Elastic Net, SVR, processus gaussien, gradient boosting, forêt aléatoire
- **Classification (10)** : logistique, arbre de décision, forêt aléatoire, SVM, gradient boosting, KNN, naïve bayésien, réseau de neurones, vote, stacking
- **Clustering (6)** : k-means, DBSCAN, hiérarchique (dendrogramme), agglomératif, GMM, mean shift
- **Réduction de dimension** : PCA, t-SNE, UMAP
- **Constructeur de réseau de neurones** : architecture configurable, entraînement réel (TensorFlow/Keras), courbes d'apprentissage, diagramme du réseau entraîné
- Validation croisée, importance des variables, matrices de confusion, courbes ROC/AUC sur toutes les méthodes concernées
- Export de modèle : joblib, pickle, JSON, ONNX, TFLite + script d'entraînement reproductible

### 📋 Tests statistiques
- Tests d'hypothèse (t-test, Mann-Whitney, Wilcoxon), ANOVA à un/deux facteurs avec post-hoc (Tukey, Bonferroni)
- Tests de corrélation (Pearson, Spearman, Kendall)
- Tests d'ajustement (Shapiro-Wilk, Kolmogorov-Smirnov, Anderson-Darling, Chi²)

### 📑 Export & rapports
- Données en CSV, tableaux GroupBy/Pivot/Stats en CSV/Excel/LaTeX
- Rapport PDF : statistiques détaillées, corrélations, qualité et suggestions **toujours inclus par défaut** ; graphiques, GroupBy, Pivot et modèles ML en sections optionnelles
- Boîtes de dialogue « Enregistrer sous » natives du navigateur pour tous les exports (repli automatique en téléchargement classique si le navigateur ne les supporte pas)

### 🌓 Interface
- Mode sombre / clair, design responsive (desktop, tablette, mobile)
- Palette de commandes (Ctrl+K), raccourcis clavier complets, onglets multi-fichiers réordonnables
- Aide intégrée avec 60+ sujets et recherche instantanée (F1 / Ctrl+H)

## Installation

### Prérequis

| Composant | Minimum | Recommandé |
|---|---|---|
| Python | 3.10 | 3.11+ |
| RAM | 4 Go | 8 Go+ |
| Navigateur | Chrome/Edge 90+ | Chrome, Firefox, Safari récents |

> **DataVortex n'est pas publié sur PyPI** (le nom `datavortex` y est déjà pris par un paquet sans rapport) — l'installation se fait directement depuis ce dépôt Git, pas via `uv tool install datavortex` seul.

### Avec Git installé

```bash
# Installer uv (si nécessaire) — Linux/macOS :
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell) : irm https://astral.sh/uv/install.ps1 | iex

# Installer DataVortex depuis ce dépôt
uv tool install "git+https://github.com/nils-malmberg/datavortex.git#subdirectory=datavortex-cli"

# Lancer
datavortex
# → ouvre http://127.0.0.1:8000
```

### Sans Git (poste pro sans droits d'installation)

Aucun Git requis — un simple téléchargement suffit :

```bash
curl -LsO https://github.com/nils-malmberg/datavortex/archive/refs/heads/main.zip
unzip main.zip && cd datavortex-main

uv tool install ./datavortex-cli
datavortex
```

Windows (PowerShell, sans `curl`/`unzip`) :

```powershell
Invoke-WebRequest -Uri "https://github.com/nils-malmberg/datavortex/archive/refs/heads/main.zip" -OutFile main.zip
Expand-Archive -Path main.zip -DestinationPath .
cd datavortex-main

uv tool install ./datavortex-cli
datavortex
```

Voir [INSTALLATION.md](INSTALLATION.md) pour le détail par plateforme (dont **Apple Silicon**), le dépannage et la désinstallation.

## Démarrage rapide

```bash
datavortex --open        # démarre et ouvre le navigateur automatiquement
datavortex --port 9000   # sur un autre port
datavortex --help-browser  # ouvre directement l'aide intégrée
datavortex --version
```

1. **Importer** — glissez un fichier CSV/Excel/JSON sur la zone d'upload, confirmez le séparateur détecté.
2. **Explorer** — onglets Stats, Visualisations, Profil pour comprendre le jeu de données.
3. **Manipuler** — Filtres, Colonnes, GroupBy, Pivot pour préparer les données.
4. **Analyser** — Tests stats ou Machine Learning selon le besoin.
5. **Exporter** — données, graphiques, modèles, ou un rapport PDF complet.

Un jeu de données de démonstration est fourni : [`examples/ventes_demo.csv`](examples/ventes_demo.csv) (400 lignes de ventes fictives). Le [guide d'utilisation](USAGE_GUIDE.md) l'utilise pour ses tutoriels pas à pas.

## Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Ctrl + K` | Palette de commandes |
| `Ctrl + F` | Rechercher dans le tableau de données |
| `Ctrl + S` | Exporter les données en CSV |
| `Ctrl + E` | Ouvrir le générateur de rapport PDF |
| `Ctrl + D` | Basculer thème clair/sombre |
| `1` … `9` | Aller directement à l'onglet correspondant |
| `F1` / `Ctrl + H` | Ouvrir l'aide complète |
| `?` | Afficher les raccourcis clavier |
| `Échap` | Fermer la fenêtre ouverte |

Référence complète et exemples : aide intégrée (F1) → section « Raccourcis clavier ».

## Développement

Ce dépôt contient trois parties : `backend/` (API FastAPI), `frontend/` (React/Vite) et `datavortex-cli/` (paquet de distribution qui assemble les deux en une seule commande).

```bash
git clone git@github.com:nils-malmberg/datavortex.git
cd datavortex

# Backend
cd backend && uv sync --extra dev
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000

# Frontend (autre terminal)
cd frontend && npm install
npm run dev   # http://localhost:5173, proxy /api vers :8000
```

```bash
# Tests
cd backend && .venv/bin/pytest -v && .venv/bin/ruff check .
cd frontend && npm run lint && npm run build
cd datavortex-cli && uv sync --extra dev && .venv/bin/pytest -v
```

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour le détail (style de code, tests attendus, process de PR) et [datavortex-cli/README.md](datavortex-cli/README.md) pour construire et tester le paquet CLI localement.

### Avec Docker

Alternative à `uv tool install` pour un déploiement conteneurisé (deux services séparés, pas le mode CLI mono-process) :

```bash
docker-compose up --build
```

Frontend (nginx + build de production, proxy `/api`) sur http://localhost:8080, backend seul sur http://localhost:8000.

## Documentation

- [INSTALLATION.md](INSTALLATION.md) — installation détaillée par plateforme
- [USAGE_GUIDE.md](USAGE_GUIDE.md) — tutoriels pas à pas (débutant → avancé)
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — toutes les routes du backend
- [CHANGELOG.md](CHANGELOG.md) — historique des versions
- [CONTRIBUTING.md](CONTRIBUTING.md) — guide de contribution
- Aide intégrée (F1 dans l'application) — 60+ sujets avec recherche
- [`specs/`](specs) — spécifications d'origine, phase par phase

## Limitations connues

- **Sessions en mémoire** : les données uploadées vivent en RAM côté serveur par session (expiration après 1h d'inactivité, 10 sessions actives maximum) ; redémarrer le serveur efface tout. Pas de base de données persistante — pas prévu pour un usage multi-utilisateurs concurrent en production telle quelle.
- **Pas d'authentification** : DataVortex écoute sur `127.0.0.1` par défaut et n'est pas conçu pour être exposé publiquement sans ajouts de sécurité (auth, rate limiting, TLS).
- **Méthodes ML coûteuses en calcul** : SVM/SVR, processus gaussien, clustering hiérarchique et mean shift ont des garde-fous de taille (voir l'aide intégrée → Machine Learning → Limites sur les gros jeux de données) plutôt qu'un support illimité — au-delà, choisissez une méthode alternative ou filtrez vos données.
- **Bundle frontend** : `plotly.js` pèse à lui seul près de 5MB avant compression ; il est chargé à la demande (code-splitting) mais reste le plus gros téléchargement initial une fois qu'un graphique est affiché.

## Licence

MIT — voir [LICENSE](LICENSE).

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). Bugs et demandes de fonctionnalités : [GitHub Issues](https://github.com/nils-malmberg/datavortex/issues).
