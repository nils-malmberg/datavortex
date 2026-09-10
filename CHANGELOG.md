# Changelog

Toutes les phases de développement notables de DataVortex sont documentées ici, de la plus récente à la plus ancienne. Format inspiré de [Keep a Changelog](https://keepachangelog.com/), adapté au déroulé par phases de ce projet.

## [Phase 10.1] — Atelier de visualisation unifié et performance sur 200 Mo

Mesures détaillées, méthode et pistes écartées : [specs/PHASE_10_1_BENCHMARK_RESULTS.md](specs/PHASE_10_1_BENCHMARK_RESULTS.md).

### Changé
- **Un seul onglet « Visualisations »**. L'onglet « Multi-graphiques » introduit en Phase 10 dupliquait l'atelier tout en perdant ses types de graphiques et ses options avancées ; il est supprimé. L'atelier porte désormais un sélecteur de disposition à trois modes — graphique simple, multi-séries à axe Y secondaire, grille de sous-graphiques — qui partagent le même aperçu, le même export, le même historique et les mêmes presets.
- Le mode multi-séries accepte maintenant les courbes de tendance et le panneau de style, jusqu'ici réservés au mode simple. Les trois modes s'exportent via `POST /api/export/plot` et s'ajoutent à un rapport PDF : plus aucune capacité n'est propre à un mode.

### Ajouté
- Grille de sous-graphiques (`POST /api/plot/subplots`) : de 1x2 à 4x4, préréglages ou dimensions libres, chaque case avec ses propres colonnes et son propre type (nuage, ligne, barres, aire, histogramme, box, violin). Redimensionner la grille conserve les cases déjà configurées.
- Cache de résultats (`backend/app/cache.py`) pour les statistiques, les statistiques avancées, le profil et les propriétés de tableau. L'invalidation est portée par un numéro de version que `Session.__setattr__` incrémente : toute affectation de `df`, `filtered_df` ou `active_filter` invalide automatiquement, sans dépendre des 17 points de mutation répartis dans le code. Les deux écritures *en place* (colonne calculée, transformation) le signalent explicitement, et un test couvre chaque façon de modifier les données.
- Plafond de points tracés (`DATAVORTEX_MAX_PLOT_POINTS`, 50 000 par défaut). Une figure Plotly transporte ses données brutes : un nuage de points sur 3,2 millions de lignes pesait 36 Mo de JSON et bloquait l'onglet du navigateur à la désérialisation, pour une tache visuellement identique. Les tendances et repères statistiques restent calculés sur l'intégralité des données ; seul le tracé est échantillonné, et la figure l'indique.
- Suite de mesures sur 200 Mo (`backend/tests/test_performance_200mb.py`), ignorée automatiquement si le jeu de données de 3,2 millions de lignes n'a pas été généré.

### Corrigé
- **Le profil détaillé prenait neuf minutes** sur 3,2 millions de lignes : `_inconsistent_formatting` parcourait chaque valeur distincte en Python en y relançant un `value_counts()` (500 025 appels pour 500 000 lignes, mesuré au profileur). Ramené à 10 s, puis 4 ms en cache.
- `detect_column_type` appliquait `.astype(str)` à la colonne entière pour en examiner 30 valeurs — ~100 ms par appel, dans une fonction que presque toutes les routes appellent plusieurs fois par requête.
- `GET /rows` recalculait bornes d'outliers, types de colonnes et empreinte mémoire `deep=True` sur tout le jeu de données à chaque page de 100 lignes.
- `POST /api/upload` exécutait décompression, analyse et écriture de 210 Mo sur disque dans la boucle d'événements, immobilisant toutes les autres requêtes — la cause directe de l'interface figée pendant un envoi. Déplacé dans le pool de threads. (Les routes `def` non asynchrones y étaient déjà exécutées par FastAPI : `upload` était la seule exception.)
- Les statistiques et le profil faisaient deux passes de hachage (`nunique()` puis `value_counts()`) là où une seule suffit.
- L'ajustement des lois de distribution triait 1,5 million de points par loi candidate. Échantillonné à 50 000 points, ce qui est aussi statistiquement plus juste : au-delà, le test de Kolmogorov-Smirnov rejette toute loi, y compris la bonne.
- Les barres d'un sous-graphique agrègent par modalité au lieu d'émettre une barre par ligne.

### Notes
- Le profil détaillé est calculé sur un échantillon de 500 000 lignes au-delà de ce seuil, et l'onglet Profil l'affiche. Ses indicateurs sont des proportions, qu'un échantillon aléatoire estime fidèlement ; les présenter comme exhaustifs serait en revanche trompeur.
- Les chaînes Arrow (`to_pandas(use_pyarrow_extension_array=True)`) ont été mesurées puis écartées : mémoire divisée par trois et `isna()` 39x plus rapide, mais `Series.duplicated()` lève `NotImplementedError` sur un `ArrowDtype` avec pandas 2.1.0, et les statistiques par colonne s'en servent.
- Deux cibles de la spec étaient déjà atteintes avant cette phase : groupby à 622 ms (cible < 3 s) et filtre à 791 ms (cible < 1 s). Le diagnostic de départ — « chaque route recharge le fichier avec `pl.read_csv`, il faut passer en lazy » — ne correspondait pas à l'architecture : le fichier est analysé une seule fois au parsing, et aucun des coûts trouvés ne venait du moteur de calcul.

## [Phase 10] — Formats compressés, graphiques multi-séries, audit de performance

Mesures détaillées et méthode de reproduction : [specs/PHASE_10_BENCHMARK_RESULTS.md](specs/PHASE_10_BENCHMARK_RESULTS.md).

### Ajouté
- Upload de formats compressés (`backend/app/data_service.py`) : `.csv.gz`, `.csv.bz2`, `.csv.zip` (décompressés en octets CSV en clair dès l'upload, puis traités comme un `.csv` normal — même cascade Polars/pandas, même spill), `.parquet` (toute compression interne : snappy/gzip/zstd, transparente pour Polars), `.feather` (Arrow IPC). `POST /api/upload` renvoie désormais `format` (ex: `"csv_gz"`) et `file_info` (taille, compression, taille décompressée estimée).
- Garde-fou contre les bombes de décompression : la taille décompressée d'un CSV compressé est bornée en flux (`DATAVORTEX_MAX_DECOMPRESSED_MB`, 500 Mo par défaut — aligné sur la limite d'upload), et rejetée avant d'avoir matérialisé plus que la limite en mémoire. Pour un zip, la taille déclarée dans l'archive est vérifiée avant toute décompression.
- Graphiques multi-séries à axe Y secondaire (`POST /api/plot/multi-series`) : jusqu'à 10 séries indépendantes (colonne, type de trace, axe gauche/droite, couleur, nom), pour superposer par exemple un chiffre d'affaires et un nombre d'unités vendues sans que l'un écrase visuellement l'autre. Intégré au générateur de rapport PDF (`kind: "multi-series"`).
- Tableau de bord multi-graphiques (onglet « Multi-graphiques », `frontend/src/components/MultiGraphDashboard.jsx`) : plusieurs graphiques multi-séries indépendants, disposition grille/1 colonne/2 colonnes, export groupé en un seul PDF (une page par graphique).
- Profilage optionnel (`backend/app/profiling.py`, `DATAVORTEX_PROFILE=1`) : détail cProfile et pic mémoire tracemalloc de l'agrégation GroupBy et des statistiques avancées. No-op par défaut — le profilage a un coût réel, il n'a rien à faire actif en permanence.
- Tests de non-régression de performance (`backend/tests/test_performance_regression.py`) sur un jeu de données de 300 000 lignes : GroupBy, statistiques et statistiques avancées restent chacun sous des seuils larges (5-10 s), et Polars reste mesurablement plus rapide que le moteur Python de pandas sur un CSV de 100 000 lignes.

### Changé
- Formats acceptés par la zone de dépôt (`UploadZone.jsx`) et limite d'upload affichée mise à jour (500 Mo, cohérente avec la Phase 9).

### Notes
- Audit de vectorisation : aucune boucle Python ligne à ligne trouvée sur un jeu de données complet. Les deux occurrences de `.iterrows()` du projet portent sur des tables déjà agrégées et bornées (aperçu, motifs de valeurs manquantes) ; `app/formulas.py` utilise `.apply(axis=1)` pour son interpréteur de formules AST, un choix architectural (sécurité, formules arbitraires) documenté et non reconsidéré ici — vectoriser un interpréteur générique serait un projet à part entière.
- La représentation de travail reste pandas pour les analyses (groupby, filtres, stats), comme tranché et documenté en Phase 9 : un groupby sur 500 000 lignes y prenait déjà 35 ms, un gain marginal ne justifiant pas de convertir les vingt services qui la consomment vers Polars. Polars reste cantonné au rôle de moteur de *parsing* (CSV rapide, lecteur Parquet/Feather).
- Le vrai gain des formats compressés n'est pas la vitesse de traitement (déjà réglée en Phase 9) mais le volume transféré sur le réseau : jusqu'à 82 % de moins pour un Parquet Zstandard face au CSV équivalent, pour un coût de décompression serveur négligeable.

## [Phase 9] — Performance sur les gros fichiers

Mesures détaillées et méthode de reproduction : [specs/PHASE_9_BENCHMARK_RESULTS.md](specs/PHASE_9_BENCHMARK_RESULTS.md).

### Ajouté
- Moteur d'analyse CSV en cascade (`backend/app/data_engine.py`) : Polars, puis moteur C de pandas, puis moteur Python, chaque niveau servant de repli au précédent. Sur 500 000 lignes, l'analyse passe de 2,94 s à 0,24 s (12,5x). Le basculement s'opère au-delà de 50 Mo ; `DATAVORTEX_FAST_PARSE_MB` permet d'abaisser ce seuil.
- Opérations en arrière-plan (`backend/app/async_tasks.py`) : `POST /api/groupby/async` et `POST /api/filters/apply/async` rendent un `task_id` immédiatement, `GET /api/tasks/{id}` livre le résultat, `DELETE /api/tasks/{id}` abandonne le calcul. L'interface affiche la progression du groupby et reste utilisable pendant le calcul. Un filtre à quatre conditions coûte 399 ms sur 500 000 lignes, donc plusieurs secondes sur un fichier de 500 Mo : exécuté dans le gestionnaire de route, il immobilisait la boucle d'événements et donc *toutes* les sessions ouvertes, pas seulement celle qui filtrait.
- Verrou par session : les opérations qui écrivent `filtered_df` sont désormais sérialisées. Deux filtres concurrents pouvaient laisser la session dans un état hybride — le risque existait déjà entre deux requêtes HTTP simultanées, l'exécution en arrière-plan le rendait plus probable.
- Export CSV en flux : `POST /api/export/csv/stream` émet le fichier par tranches de 10 000 lignes, et `GET /api/export/csv/estimate/{session_id}` annonce le volume approximatif avant le téléchargement.
- `GET /api/health` remonte désormais l'empreinte mémoire du processus, la durée de fonctionnement et le nombre de tâches en cours. Les routes coûteuses annoncent durée, débit et moteur d'analyse retenu.
- Jeux de données de test reproductibles (`backend/scripts/generate_test_data.py`) et banc de mesure (`backend/scripts/benchmark.py`).

### Changé
- Taille maximale d'upload relevée de 100 Mo à 500 Mo.
- La détection d'encoding et de séparateur ne travaille plus que sur les 256 premiers kilo-octets. `chardet` sur un fichier de 32 Mo prenait 8,2 s — plus que l'analyse elle-même — pour une information que portent les premières lignes. Ramené à 0,07 s.
- Les fichiers sources de plus de 50 Mo sont déversés sur disque au lieu d'être conservés en mémoire : une session détenait jusqu'ici les octets bruts *et* le DataFrame analysé. Sur un fichier de 527 Mo, l'empreinte retombe de 709 Mo à 183 Mo après déversement. Le fichier temporaire est supprimé à la fermeture comme à l'expiration de la session.
- L'export CSV historique (`POST /api/export/csv`) reste disponible et inchangé ; l'interface utilise désormais la version en flux, dont le pic mémoire est onze fois plus faible.

### Notes
- Deux critères de la spec ne sont pas atteints sur un fichier de 527 Mo : chargement en 5,36 s (cible < 5 s) et empreinte de 2,2 Go (cible < 2 Go). L'analyse Polars elle-même ne prend que 0,84 s ; le reste est la conversion vers la représentation pandas, où chaque chaîne devient un objet Python. Les pistes chiffrées sont documentées dans les résultats de mesure.
- L'aperçu interactif du constructeur de filtres reste sur la route synchrone : il se redéclenche à chaque modification du filtre, et un aller-retour de sondage y coûterait plus qu'il ne rapporte. C'est le blocage du serveur, et non celui du navigateur, que la version asynchrone corrige.
- Les opérations analytiques (groupby, filtre, tri) restent en pandas : sur 500 000 lignes, un groupby prend déjà 35 ms. Le contraire de ce qu'annonçait la spec, et un gain de 20 ms ne justifie pas de convertir la représentation dans les vingt services qui la consomment.

## [1.0.4] — Démarrage rapide

### Corrigé
- Le démarrage de `datavortex` (bannière affichée, mais navigateur/API pas encore utilisables) pouvait prendre 30s à 1min : `app/ml_neural_service.py` importait `tensorflow` au niveau du module, donc à chaque lancement du serveur — même pour un utilisateur qui n'utilise jamais le constructeur de réseau de neurones. TensorFlow est maintenant importé à la demande, au premier entraînement de réseau de neurones seulement (mis en cache ensuite) : le démarrage du serveur ne dépend plus que de pandas/scikit-learn, nettement plus rapides à charger.

## [1.0.3] — Sélection automatique d'une version de Python compatible

### Corrigé
- `requires-python = ">=3.10"` n'avait pas de borne haute : sur une machine sans Python 3.10/3.11 déjà installé, `uv` en téléchargeait automatiquement un plus récent (ex. 3.14 sur Windows) — que TensorFlow ne publie pas encore en wheel, avec une erreur de résolution de dépendances peu explicite (`No wheels with a matching Python ABI tag`). `requires-python` est maintenant borné à `>=3.10,<3.12` dans `backend/pyproject.toml` et `datavortex-cli/pyproject.toml`, pour que `uv` sélectionne/télécharge automatiquement une version compatible sans intervention manuelle (`--python 3.11` reste possible en secours, documenté dans INSTALLATION.md).

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
