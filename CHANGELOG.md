# Changelog

Toutes les phases de développement notables de DataVortex sont documentées ici, de la plus récente à la plus ancienne. Format inspiré de [Keep a Changelog](https://keepachangelog.com/), adapté au déroulé par phases de ce projet.

## [1.0.2] — Apple Silicon & installation sans Git

### Corrigé
- `tensorflow-cpu` (utilisé jusqu'ici sans condition) ne publie aucune wheel macOS ARM64 : l'installation échouait purement et simplement sur Apple Silicon (M1/M2/M3/M4). Dépendance désormais conditionnelle par plateforme (`sys_platform`/`platform_machine`) : `tensorflow-macos` sur Apple Silicon, `tensorflow-cpu` partout ailleurs — les deux fournissent le même module `tensorflow`, aucun changement de code nécessaire. Vérifié via le lockfile : les deux wheels (dont `tensorflow_macos-2.15.0-*-macosx_12_0_arm64.whl`) sont bien résolues et prêtes.
- Toutes les instructions d'installation supposaient Git disponible, ce qui n'est pas toujours le cas sur un poste professionnel verrouillé. Ajout d'une méthode d'installation sans Git (téléchargement du ZIP du dépôt + `uv tool install ./datavortex-cli`) pour Linux, macOS et Windows, vérifiée de bout en bout.

## [1.0.1] — Correctif d'installation

### Corrigé
- `uv tool install datavortex` installait silencieusement un paquet PyPI totalement différent : `datavortex` y est déjà pris par un paquet sans rapport avec ce projet. Trouvé en testant l'installation en conditions réelles depuis un clone frais du tag v1.0.0. L'installation se fait maintenant via l'URL Git du dépôt (`uv tool install "git+https://github.com/nils-malmberg/datavortex.git#subdirectory=datavortex-cli"`), documentée dans README.md et INSTALLATION.md.
- Même en installant depuis la bonne source, le frontend ne s'installait pas : `datavortex-cli/datavortex/static/` était ignoré par git en tant que « produit de build », mais rien dans le paquetage ne le reconstruisait automatiquement — un `uv tool install` depuis un clone Git donnait donc une API fonctionnelle sans aucune interface. Le frontend compilé est maintenant commité directement dans le dépôt.

## [1.0.0] — Phase 8.2 : distribution, aide intégrée, documentation — première version de production

### Ajouté
- Distribution via `uv tool` : une seule commande (`datavortex`) démarre l'API et sert le frontend pré-compilé sur le même port, avec `--port`, `--host`, `--open`, `--help-browser`, `--version`.
- Aide intégrée (F1 / Ctrl+H / bouton « ? ») : 12 sections, 63 sujets, recherche instantanée, liens croisés entre sujets liés.
- Documentation complète : [INSTALLATION.md](INSTALLATION.md), [USAGE_GUIDE.md](USAGE_GUIDE.md), [API_DOCUMENTATION.md](API_DOCUMENTATION.md), [CONTRIBUTING.md](CONTRIBUTING.md), [LICENSE](LICENSE) (MIT), README réécrit.
- Jeu de données de démonstration [`examples/ventes_demo.csv`](examples/ventes_demo.csv), utilisé par le guide d'utilisation.

### Corrigé
- `npm run lint` remontait 1292 faux positifs sur le bundle minifié quand `dist/` existait localement (jamais vu en CI, qui lint avant de builder) — `dist/` est maintenant ignoré par ESLint.

## [Phase 8.1] — Polish, extension du Machine Learning, exports intelligents

### Ajouté
- Numéros de ligne dans l'aperçu des données, avec préservation de l'index original après filtrage.
- Boîtes de dialogue « Enregistrer sous » natives du navigateur pour tous les exports (données, graphiques, tableaux, modèles, rapports), avec repli automatique en téléchargement classique.
- 11 nouvelles méthodes de régression/classification/clustering (Ridge, Lasso, Elastic Net, SVR, processus gaussien, gradient boosting, forêt aléatoire, SVM, KNN, naïve bayésien, vote, stacking, hiérarchique, GMM, mean shift), chacune avec validation croisée et métriques détaillées.
- Constructeur de réseau de neurones (TensorFlow/Keras) : couches configurables, entraînement réel, courbes d'apprentissage, diagramme du réseau entraîné.
- Export de modèle ML : joblib, pickle, JSON, ONNX, TFLite, métadonnées et script d'entraînement reproductible.
- Rapport PDF : statistiques détaillées, corrélations, qualité et suggestions désormais toujours incluses par défaut ; graphiques/GroupBy/Pivot/modèles ML en sections optionnelles.

### Corrigé
- Passage en revue des performances sur 100k+ lignes : profondeur par défaut bornée pour la forêt aléatoire (un fit passait de plus de 60s à quelques secondes), score de silhouette calculé sur échantillon au-delà de 5000 lignes (complexité quadratique), garde-fous explicites (`TOO_MANY_SAMPLES`) pour SVM/SVR, processus gaussien, clustering hiérarchique et mean shift plutôt qu'un blocage silencieux.
- Fuite de données en classification : la colonne cible pouvait être sélectionnée comme variable explicative.
- Dendrogramme illisible au-delà de 40 feuilles ; chevauchement des étiquettes sur le diagramme de réseau de neurones.

## [Phase 8] — Analytique avancée : stats, visualisation, filtres, profiling, tests

### Ajouté
- Statistiques avancées : corrélations avec p-values (Pearson/Spearman/Kendall), analyse de distribution avec ajustement de lois.
- Visualisations avancées : pair plot, joint plot, ridge plot, essaim/strip, lignes de tendance (linéaire/polynomiale/LOWESS) avec bandes de confiance, palettes daltonisme-safe, annotations.
- Filtres avancés : regex, intervalles, listes, inversion, aperçu des lignes retenues/exclues.
- Aperçu de données « pro » : tri, recherche, redimensionnement et fixation de colonnes.
- GroupBy multi-colonnes avec agrégations multiples et tri ; tableaux croisés dynamiques avec marges et pourcentages.
- Profilage détaillé : score de qualité, détection d'anomalies, suggestions.
- Tests d'hypothèse, ANOVA (un/deux facteurs, post-hoc Tukey/Bonferroni), tests de corrélation, tests d'ajustement.
- Opérations sur les colonnes (renommer/dupliquer/supprimer/réordonner) et transformations (binning, encodage, lag, rolling).
- Raccourcis clavier complets et palette de commandes (Ctrl+K).

## [Phase 7] — Machine Learning

### Ajouté
- Régression (linéaire, polynomiale), classification (logistique, arbre, forêt aléatoire), clustering (k-means, DBSCAN) et réduction de dimension (PCA, t-SNE, UMAP).

## [Phase 5–6] — Mode sombre, multi-fichiers, rapports PDF

### Ajouté
- Mode sombre / clair, onglets multi-fichiers avec fusion (concaténation ou jointure sur colonne clé).
- Génération de rapport PDF (résumé, statistiques, graphiques).

### Corrigé
- Mise en page PDF : respect des marges, dimensionnement des heatmaps.

## [Phase 4] — Export & CI/CD

### Ajouté
- Export CSV de la vue active (filtres + colonnes calculées appliqués), séparateur et encoding configurables (UTF-8/Latin-1), filtre actif documenté en commentaire en tête de fichier.
- Export des graphiques en PNG/SVG/HTML, intégré à l'onglet Export.
- Suite de tests pytest (formules, filtres, API de bout en bout) et lint ruff côté backend.
- Workflows GitHub Actions : `test.yml` (pytest + ruff + eslint + build) et `deploy.yml` (validation de build Docker).
- Dockerfiles backend/frontend + `docker-compose.yml`.

### Corrigé
- Une condition de filtre fraîchement ajoutée (encore vide) déclenchait une requête invalide côté frontend avant que l'utilisateur ait fini de la configurer.

## [Phase 3] — Filtrage & colonnes calculées

### Ajouté
- Filter Builder : conditions combinées en ET/OU, opérateurs adaptés au type de colonne (numérique, texte, booléen, date, valeurs manquantes).
- Moteur de formules sûr pour les colonnes calculées (parsing AST Python, jamais `eval`/`exec`), avec aperçu avant validation.
- Le filtre actif et les colonnes calculées se propagent automatiquement à l'aperçu, aux statistiques et aux graphiques.

## [Phase 2] — Visualisations

### Ajouté
- Graphiques 1D (histogramme, box, violin, KDE, bar, pie), 2D (scatter, line, heatmap, hexbin, bar groupé, bubble) et 3D (scatter3D, surface) via Plotly.
- Export PNG/SVG/HTML par graphique.

### Corrigé
- Bug de synchronisation état/UI empêchant la génération des graphiques 2D/3D tant que l'utilisateur ne re-sélectionnait pas manuellement chaque colonne.

## [Phase 1] — MVP

### Ajouté
- Upload de fichiers CSV/Excel/JSON, détection automatique de l'encoding et du séparateur, confirmation manuelle.
- Aperçu des données (100 premières lignes) et statistiques descriptives par colonne (numériques, chaînes, booléens, dates).
- Gestion d'erreurs cohérente sur toute l'API (`{"error": {"code", "message"}}`).
