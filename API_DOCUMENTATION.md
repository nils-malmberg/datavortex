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
| `TASK_NOT_FOUND` | 404 | Tâche de fond inconnue ou dont le résultat a expiré |
| `INVALID_ENCODING` | 400 | Encoding d'export inconnu |
| `INVALID_SEPARATOR_REGEX` | 400 | Motif de séparateur invalide, ou acceptant la chaîne vide |
| `TENSORFLOW_UNAVAILABLE` | 503 | Réseau de neurones ou export TFLite demandé alors que TensorFlow ne se charge pas (DLL bloquée, paquet absent) ou est désactivé (`DATAVORTEX_NO_TENSORFLOW`). Le message contient la cause et la piste ; voir `GET /api/ml/capabilities` (Phase 10.4). |
| `INTERNAL_ERROR` | 500 | Erreur non anticipée (bug) — la trace complète est dans le journal du serveur |

Il n'y a pas de rate limiting (usage local mono-utilisateur).

---

## Sessions, upload & parsing

| Route | Description |
|---|---|
| `GET /api/health` | État du serveur : empreinte mémoire (`memory.rss_mb`), durée de fonctionnement, tâches de fond en cours, statistiques du cache (`cache.hit_rate`), disponibilité de Polars, état de TensorFlow **sans le sonder** (`tensorflow.probed: false` tant qu'aucune fonctionnalité ne l'a chargé — l'import peut prendre une minute, il n'a pas sa place dans un contrôle de santé). |
| `POST /api/upload` | Upload d'un fichier (`multipart/form-data`, champ `file`). Détecte le format depuis l'extension — CSV, CSV.GZ/BZ2/ZIP, Parquet (toute compression interne), Feather, Excel, JSON (Phase 10) — l'encoding et, pour un CSV, propose un séparateur. Retourne un `session_id`, `format` (ex: `"csv_gz"`) et `file_info` (taille, compression, taille décompressée estimée). |
| `GET /api/version` | Numéro de version du serveur, seul (`{"version": "1.2.1"}`). |
| `POST /api/parse` | Parse définitivement la session avec le séparateur choisi (`{session_id, separator, separator_type}`). `separator_type` vaut `"preset"` (défaut : séparateur littéral) ou `"regex"` (Phase 10.2 : motif tel que `\s+`, `[,;]`, `\s*,\s*` — validé avant analyse, `INVALID_SEPARATOR_REGEX` sinon ; toujours traité par le moteur Python de pandas, le seul à découper sur une expression régulière). Retourne `n_rows`, `n_columns`, `columns`, `column_types`, et `metrics` (durée, débit, moteur d'analyse retenu : `polars`, `pandas-c` ou `pandas-python`). Sans objet pour Parquet/Feather/Excel/JSON, déjà analysés à l'upload (`already_parsed: true`). |
| `DELETE /api/session/{session_id}` | Libère une session (données + modèles ML entraînés associés). |
| `POST /api/merge` | Combine plusieurs sessions (`session_ids`, `mode: "concat"|"merge"`, `key_column` pour un merge façon SQL join). |

## Données

| Route | Description |
|---|---|
| `GET /api/data/{session_id}/preview?rows=N` | Aperçu des N premières lignes (défaut : constante `PREVIEW_ROWS`). |
| `GET /api/data/{session_id}/rows` | Lignes paginées avec tri, recherche texte et regroupement (utilisé par l'aperçu principal). |
| `POST /api/data/{session_id}/filter` | Applique un filtre (`ApplyFilterRequest`, arbre `FilterNode` ET/OU) à la session. |
| `POST /api/filters/apply` | Filtre avancé avec aperçu (`AdvancedFilterRequest`) : `invert`, `preview_mode: "all"|"kept"|"removed"`. Retourne aussi `metrics`. Voir la variante asynchrone pour les gros fichiers. |
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
| `GET /api/profile/{session_id}/detailed` | Score de qualité, anomalies, données manquantes, suggestions. Au-delà de 500 000 lignes, calculé sur un échantillon aléatoire : la réponse porte alors `sampling: {sampled, rows_analyzed, total_rows}` (Phase 10.1). |
| `POST /api/stats/export` | Exporte un tableau de stats (`StatsExportRequest` : `table: "summary"|"correlations"|"distributions"|"missing"`, `format: "csv"|"excel"|"latex"`). |
| `POST /api/stats/hypothesis_test` | Tests d'hypothèse / ANOVA / corrélation / ajustement (`HypothesisTestRequest`, voir aide intégrée pour le détail des `test` disponibles par `family`). |

## Visualisation

| Route | Description |
|---|---|
| `POST /api/plot/1d` | Graphique 1D (`Plot1DRequest` : `column`, `plot_type`, `bins`, `group_by`). |
| `POST /api/plot/2d` | Graphique 2D (`Plot2DRequest` : `x`, `y`, `plot_type`, `color_by`, `size_by`). |
| `POST /api/plot/3d` | Graphique 3D (`Plot3DRequest` : `x`, `y`, `z`, `plot_type`). |
| `POST /api/plot/advanced` | Graphiques avancés (`AdvancedPlotRequest`) : types étendus (pair/joint/ridge/strip…), `trend` (tendance + confiance), `overlays` (moyenne/médiane/écart-type), `style` (palette, daltonisme, annotations, thème). |
| `POST /api/export/plot` | Exporte un graphique déjà généré (`ExportPlotRequest` : `kind` parmi `1d`/`2d`/`3d`/`ml`/`advanced`/`multi-series`/`subplots`, `params` du graphique d'origine, `format: "png"|"svg"|"html"`, `width`/`height`). Une grille de sous-graphiques n'est jamais rendue plus petite que sa taille intrinsèque (Phase 10.4) : `width`/`height` sont des minima pour elle. |
| `POST /api/plot/multi-series` | Graphique multi-séries à axe Y secondaire optionnel (Phase 10) : `MultiSeriesPlotRequest` — `x_axis`, `series: [{y_column, y_axis: "left"|"right", plot_type: "scatter"|"line"|"bar"|"area", name, color}]` (1 à 10 séries), plus `trend` et `style` comme `/plot/advanced` (Phase 10.1). |
| `POST /api/plot/subplots` | Grille de sous-graphiques indépendants (Phase 10.1) : `SubplotGridRequest` — `rows`/`cols` (1 à 4), `subplots: [{plot_type, x, y, title, color}]`, `style`. Les types `histogram`/`box`/`violin` ne demandent qu'une colonne (`y`) ; `bar` agrège par modalité. La figure déclare sa taille (Phase 10.4) : `layout.height` = 500 px par ligne (520 minimum) et `layout.meta.grid = {rows, cols, min_width}` (420 px par colonne) — un client doit lui donner cette hauteur et laisser défiler horizontalement sous `min_width`, sinon les cases se compriment. |

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
| `GET /api/ml/capabilities` | Ce que ce serveur sait faire en ML (Phase 10.4) : `tensorflow: {available, probed, version, disabled_by, reason, hint}` et `features: {scikit_learn, neural_network, tflite_export}`. Sonde TensorFlow (import mémorisé : la première réponse peut prendre jusqu'à une minute — l'interface ne l'appelle pas, elle paie cet import au premier entraînement). `reason`/`hint` sont rédigés pour l'utilisateur final. |
| `POST /api/ml/neural_network` | Entraîne un réseau de neurones (`NeuralNetworkRequest` : `layers`, `optimizer`, `learning_rate`, `batch_size`, `epochs`). Entraînement réel TensorFlow/Keras, retourne courbes de perte et poids pour le diagramme du réseau. `TENSORFLOW_UNAVAILABLE` (503) si TensorFlow ne se charge pas ou est désactivé. |
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

---

## Opérations en arrière-plan (Phase 9)

Les calculs longs peuvent être lancés en tâche de fond : la route rend un
identifiant immédiatement, le client interroge ensuite son état. L'interface
reste utilisable pendant le calcul.

| Route | Description |
|---|---|
| `POST /api/groupby/async` | Même charge utile que `POST /api/groupby`. Rend `{task_id, status, kind}` sans attendre le calcul. La session est validée sur-le-champ : une session inconnue renvoie 404 immédiatement. |
| `GET /api/tasks/{task_id}` | État de la tâche : `pending`, `running`, `done`, `error` ou `cancelled`. Le résultat est dans `data` quand `status` vaut `done` ; l'erreur est dans `error` (`{code, message}`, même forme que les routes synchrones) quand il vaut `error`. |
| `POST /api/filters/apply/async` | Même charge utile que `POST /api/filters/apply`. Applique le filtre en arrière-plan, sous le verrou de la session. |
| `DELETE /api/tasks/{task_id}` | Abandonne la tâche. Un calcul déjà lancé n'est pas interrompu — pandas et Polars n'offrent pas de point d'annulation — mais son résultat est écarté. |

Sondage recommandé : premier appel après ~250 ms, puis intervalle croissant
plafonné à 3 s. Les résultats terminés restent disponibles 10 minutes.

```bash
TASK=$(curl -s -X POST localhost:8000/api/groupby/async \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"...","group_by":["department"],
       "aggregations":[{"column":"salary","func":"mean"}]}' | jq -r .task_id)

curl -s localhost:8000/api/tasks/$TASK | jq '.status, .data.group_count'
```

## Export en flux (Phase 9)

| Route | Description |
|---|---|
| `POST /api/export/csv/stream` | Export CSV émis par tranches (`StreamExportRequest` : `separator`, `encoding`, `include_filter_comment`, `chunk_rows`). Réponse en `transfer-encoding: chunked`, sans pic mémoire côté serveur. |
| `GET /api/export/csv/estimate/{session_id}` | Volume approximatif de l'export : `rows`, `columns`, `estimated_bytes`, `chunk_rows`. |

`POST /api/export/csv` (construction en mémoire) reste disponible et produit
exactement le même fichier — l'égalité des deux sorties est vérifiée par les
tests. La version en flux est à préférer au-delà de quelques dizaines de milliers
de lignes.

L'encoding est validé **avant** l'ouverture du flux : une fois le premier octet
parti, le statut HTTP l'est aussi, et une erreur se traduirait par un fichier
tronqué sans explication.

## Formats compressés (Phase 10)

`POST /api/upload` accepte, en plus de CSV/Excel/JSON :

| Extension | `format` renvoyé | Traitement |
|---|---|---|
| `.csv.gz` | `csv_gz` | Décompressé en octets CSV en clair dès l'upload, puis traité comme un `.csv` normal (même cascade Polars/pandas, même spill). |
| `.csv.bz2` | `csv_bz2` | Idem, décompression `bz2`. |
| `.csv.zip` | `csv_zip` | Premier fichier `.csv`/`.tsv`/`.txt` trouvé dans l'archive. |
| `.parquet`, `.parquet.gz`, `.parquet.snappy`, `.parquet.zstd` | `parquet*` | Chargé intégralement à l'upload via Polars (`already_parsed: true`) — la codec de compression est interne au fichier Parquet, transparente pour le lecteur. |
| `.feather` | `feather` | Arrow IPC, chargé à l'upload comme le Parquet. |

Une décompression illimitée est un vecteur de déni de service classique (bombe
de décompression) : la taille décompressée d'un CSV compressé est bornée par
`DATAVORTEX_MAX_DECOMPRESSED_MB`, vérifiée en flux (sans jamais matérialiser
plus que la limite en mémoire) plutôt qu'après coup.

## Cache de résultats (Phase 10.1)

Les routes coûteuses et idempotentes — `GET /api/stats/{id}`,
`GET /api/stats/{id}/advanced`, `GET /api/profile/{id}/detailed` et les
propriétés de tableau de `GET /api/data/{id}/rows` — servent leur résultat
depuis un cache mémoire. Sur un fichier de 200 Mo, un profil détaillé passe de
10 s à 4 ms au deuxième appel.

La clé contient un numéro de version des données, incrémenté à chaque
modification de la session (filtre, colonne calculée, transformation,
suppression de colonne, nouveau parsing) : un résultat calculé avant un filtre
n'est jamais servi après. `GET /api/health` remonte `cache: {entries, hits,
misses, hit_rate}`, et la fermeture d'une session purge ses entrées.

## Variables d'environnement (Phases 9 à 10.4)

| Variable | Défaut | Effet |
|---|---|---|
| `DATAVORTEX_FAST_PARSE_MB` | `50` | Taille à partir de laquelle l'analyse CSV bascule sur Polars. |
| `DATAVORTEX_SPILL_MB` | `50` | Taille à partir de laquelle le fichier source est déversé sur disque plutôt que conservé en mémoire. |
| `DATAVORTEX_MAX_DECOMPRESSED_MB` | `500` | Taille maximale acceptée pour un CSV compressé une fois décompressé (Phase 10). Alignée par défaut sur la limite d'upload : la compression réduit le transfert réseau, pas le budget mémoire du pipeline. |
| `DATAVORTEX_MAX_PLOT_POINTS` | `50000` | Nombre maximal de points transportés par une trace point à point (Phase 10.1). Une figure Plotly embarque ses données : sans plafond, un nuage de points sur 3,2 millions de lignes pèse 36 Mo de JSON et bloque l'onglet du navigateur. Les calculs (tendance, repères) restent faits sur toutes les données. |
| `DATAVORTEX_NO_TENSORFLOW` (alias `DATAVORTEX_NO_ML`) | *(désactivé)* | À `1`, TensorFlow n'est jamais importé : réseau de neurones et export TFLite répondent `TENSORFLOW_UNAVAILABLE`, les méthodes scikit-learn sont intactes (Phase 10.4). Équivalent du drapeau `datavortex --no-tensorflow`. |
| `DATAVORTEX_PROFILE` | *(désactivé)* | À `1`, journalise (module `datavortex.profiling`) le détail cProfile et le pic mémoire tracemalloc de l'agrégation et des statistiques avancées. Désactivé par défaut : le profilage a un coût réel. |
