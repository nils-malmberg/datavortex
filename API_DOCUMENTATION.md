# Documentation de l'API

L'API DataVortex est une API FastAPI classique en JSON. En développement elle écoute sur `http://localhost:8000` ; documentation interactive auto-générée sur `/docs` (Swagger) et `/redoc`. En distribution CLI, elle est servie sur le même port que le frontend (`/api/*`).

Aucune authentification n'est requise (usage local). Les données uploadées vivent en mémoire côté serveur, rattachées à un `session_id` (UUID), avec une expiration après 1h d'inactivité et un maximum de 10 sessions actives simultanément.

## Format des erreurs

Toute erreur métier renvoie un JSON de la forme :

```json
{"error": {"code": "SESSION_NOT_FOUND", "message": "Session '...' introuvable ou expirée."}}
```

Le `code` est stable (à tester par les clients), le `message` est un texte lisible destiné à l'affichage. Codes fréquents :

| Code | HTTP | Signification |
|---|---|---|
| `SESSION_NOT_FOUND` | 404 | Session inexistante ou expirée |
| `DATA_NOT_PARSED` | 409 | `/api/parse` n'a pas encore été appelé sur cette session |
| `COLUMN_NOT_FOUND` | 404 | Colonne référencée absente du jeu de données |
| `COLUMN_ALREADY_EXISTS` | 409 | Nom de colonne déjà utilisé |
| `EMPTY_FILE` | 400 | Fichier uploadé vide |
| `PARSE_ERROR` | 400 | Échec de lecture du fichier (Excel/JSON corrompu, etc.) |
| `INVALID_FILTER_VALUE` / `UNKNOWN_OPERATOR` / `INVALID_REGEX` | 400 | Filtre malformé |
| `TOO_MANY_SAMPLES` | 422 | Jeu de données trop volumineux pour la méthode ML demandée (voir aide intégrée) |
| `REPORT_GENERATION_FAILED` | 500 | Échec de génération du PDF |
| `INTERNAL_ERROR` | 500 | Erreur non anticipée (bug) |

Il n'y a pas de rate limiting (usage local mono-utilisateur).

---

## Sessions, upload & parsing

| Route | Description |
|---|---|
| `GET /api/health` | Ping de santé du serveur. |
| `POST /api/upload` | Upload d'un fichier (`multipart/form-data`, champ `file`). Détecte le type (csv/excel/json), l'encoding et, pour un CSV, propose un séparateur. Retourne un `session_id`. |
| `POST /api/parse` | Parse définitivement la session avec le séparateur choisi (`{session_id, separator}`). Retourne `n_rows`, `n_columns`, `columns`, `column_types`. |
| `DELETE /api/session/{session_id}` | Libère une session (données + modèles ML entraînés associés). |
| `POST /api/merge` | Combine plusieurs sessions (`session_ids`, `mode: "concat"|"merge"`, `key_column` pour un merge façon SQL join). |

## Données

| Route | Description |
|---|---|
| `GET /api/data/{session_id}/preview?rows=N` | Aperçu des N premières lignes (défaut : constante `PREVIEW_ROWS`). |
| `GET /api/data/{session_id}/rows` | Lignes paginées avec tri, recherche texte et regroupement (utilisé par l'aperçu principal). |
| `POST /api/data/{session_id}/filter` | Applique un filtre (`ApplyFilterRequest`, arbre `FilterNode` ET/OU) à la session. |
| `POST /api/filters/apply` | Filtre avancé avec aperçu (`AdvancedFilterRequest`) : `invert`, `preview_mode: "all"|"kept"|"removed"`. |
| `GET /api/columns/{session_id}` | Liste des colonnes avec leur type détecté. |
| `POST /api/columns/operation` | Renommer / dupliquer / supprimer / réordonner des colonnes (`ColumnOperationRequest`). |
| `POST /api/columns/transform` | Transformation d'une colonne : `binning`, `encoding`, `lag`, `rolling` (`ColumnTransformRequest`, `params` spécifiques à la transformation). |
| `POST /api/data/{session_id}/columns` | Crée une colonne calculée depuis une formule (`CreateColumnRequest` : `name`, `formula`, `preview_only` pour tester sans valider). |

## Statistiques & profiling

| Route | Description |
|---|---|
| `GET /api/stats/{session_id}` | Statistiques descriptives par colonne. |
| `GET /api/column/{session_id}/{col_name}/stats` | Statistiques détaillées d'une seule colonne. |
| `GET /api/stats/{session_id}/advanced?method=pearson` | Corrélations avec p-values (`pearson`/`spearman`/`kendall`) et analyse de distribution. |
| `GET /api/profile/{session_id}/detailed` | Score de qualité, anomalies, données manquantes, suggestions. |
| `POST /api/stats/export` | Exporte un tableau de stats (`StatsExportRequest` : `table: "summary"|"correlations"|"distributions"|"missing"`, `format: "csv"|"excel"|"latex"`). |
| `POST /api/stats/hypothesis_test` | Tests d'hypothèse / ANOVA / corrélation / ajustement (`HypothesisTestRequest`, voir aide intégrée pour le détail des `test` disponibles par `family`). |

## Visualisation

| Route | Description |
|---|---|
| `POST /api/plot/1d` | Graphique 1D (`Plot1DRequest` : `column`, `plot_type`, `bins`, `group_by`). |
| `POST /api/plot/2d` | Graphique 2D (`Plot2DRequest` : `x`, `y`, `plot_type`, `color_by`, `size_by`). |
| `POST /api/plot/3d` | Graphique 3D (`Plot3DRequest` : `x`, `y`, `z`, `plot_type`). |
| `POST /api/plot/advanced` | Graphiques avancés (`AdvancedPlotRequest`) : types étendus (pair/joint/ridge/strip…), `trend` (tendance + confiance), `overlays` (moyenne/médiane/écart-type), `style` (palette, daltonisme, annotations, thème). |
| `POST /api/export/plot` | Exporte un graphique déjà généré (`ExportPlotRequest` : `kind`, `params` du graphique d'origine, `format: "png"|"svg"|"html"`). |

## GroupBy & Pivot

| Route | Description |
|---|---|
| `POST /api/groupby` | Regroupe et agrège (`GroupByRequest` : `group_by`, `aggregations` — liste de `{column, func, alias?}`, `sort_by`, `limit`). |
| `POST /api/groupby/export` | Exporte un résultat GroupBy (`GroupByExportRequest`, mêmes champs + `format`). |
| `POST /api/pivot` | Tableau croisé dynamique (`PivotRequest` : `index`, `columns`, `values`, `aggfunc`, `margins`, `percentage`). |
| `POST /api/pivot/export` | Exporte un pivot (`PivotExportRequest`). |

## Machine Learning

| Route | Description |
|---|---|
| `POST /api/ml/regression` | Entraîne un modèle de régression (`RegressionRequest` : `features`, `target`, `model_type`, `params` spécifiques à la méthode). Retourne métriques, résidus, importance des variables si applicable, et un `model_id` réutilisable. |
| `POST /api/ml/classification` | Entraîne un modèle de classification (`ClassificationRequest`). Retourne accuracy/précision/rappel/F1, matrice de confusion, ROC/AUC si applicable. |
| `POST /api/ml/clustering` | Clustering (`ClusteringRequest`). Retourne silhouette/Davies-Bouldin/Calinski-Harabasz, tailles de cluster, courbe du coude pour k-means. |
| `POST /api/ml/pca` | Réduction de dimension (`PCARequest` : `method: "pca"|"tsne"|"umap"`, `n_components: 2|3`). |
| `POST /api/ml/neural_network` | Entraîne un réseau de neurones (`NeuralNetworkRequest` : `layers`, `optimizer`, `learning_rate`, `batch_size`, `epochs`). Entraînement réel TensorFlow/Keras, retourne courbes de perte et poids pour le diagramme du réseau. |
| `POST /api/ml/export/model` | Exporte un modèle entraîné (`ModelExportRequest` : `model_id`, `format: "joblib"|"pickle"|"json"|"onnx"|"tflite"`). |
| `POST /api/ml/export/metadata` | Métadonnées d'entraînement d'un modèle (`ModelMetadataRequest`). |
| `POST /api/ml/export/training_script` | Génère un notebook Python reproduisant l'entraînement (`TrainingScriptRequest`). |

> Les modèles entraînés (`model_id`) sont conservés en mémoire pour la durée de la session — ré-exporter un modèle ou ses métadonnées ne nécessite pas de le ré-entraîner.

## Rapports PDF

| Route | Description |
|---|---|
| `POST /api/report/pdf` | Génère un rapport (`GenerateReportRequest` : `sections` optionnelles, `plots` — liste de `ReportPlotSpec` avec `kind` parmi `1d`/`2d`/`3d`/`ml`/`advanced`/`groupby`/`pivot`, `page_format`, `orientation`). Les statistiques détaillées, corrélations, qualité et suggestions sont **toujours incluses**, indépendamment de `sections`. |

## Export de données

| Route | Description |
|---|---|
| `POST /api/export/csv` | Exporte les données actuellement filtrées/enrichies en CSV (`ExportCsvRequest` : `separator`, `encoding`, `include_filter_comment`). |

---

## Notes pour intégrateurs

- Tous les corps de requête sont validés par Pydantic ; un champ manquant ou mal typé renvoie une erreur `422` FastAPI standard (pas l'enveloppe `{"error": ...}` ci-dessus, réservée aux erreurs métier).
- Les endpoints de graphique (`/api/plot/*`) renvoient une figure Plotly (`dict` sérialisable directement par `Plotly.newPlot`) plutôt qu'une image — l'export en image se fait via `/api/export/plot` séparément.
- Voir `backend/app/models.py` pour la définition Pydantic exacte et exhaustive de chaque requête (source de vérité — cette page en donne une vue lisible mais non générée automatiquement).
