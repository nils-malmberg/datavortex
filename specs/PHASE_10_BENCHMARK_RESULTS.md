# Phase 10 — Résultats de mesure

Mesures réalisées sur la même machine que les résultats Phase 9
([PHASE_9_BENCHMARK_RESULTS.md](PHASE_9_BENCHMARK_RESULTS.md)), avec un jeu de
données généré par `backend/scripts/generate_test_data.py --rows 200000`
(9 colonnes, 12,64 Mo en CSV). Chaque mesure passe par le client de test
FastAPI (`TestClient`), donc par la pile HTTP complète — upload puis parse —
et non par un appel direct aux fonctions internes.

## 1. Formats compressés : ce que la compression change réellement

| Format | Taille transférée | Upload | Parse | Requêtes nécessaires |
|---|---|---|---|---|
| CSV brut | 12,64 Mo | 656 ms | 180 ms (`polars`) | 2 (`upload` + `parse`) |
| CSV.GZ | 3,59 Mo (**-72 %**) | 190 ms | 168 ms (`polars`) | 2 |
| Parquet (Zstandard) | 2,27 Mo (**-82 %**) | 150 ms (tout compris) | — (`already_parsed`) | 1 |

*(mesures avec `DATAVORTEX_FAST_PARSE_MB` abaissé pour que Polars s'enclenche dès 12 Mo — au seuil par défaut de 50 Mo, un fichier de cette taille passe par le moteur Python, plus lent pour les deux formats de façon égale, ce qui ne change rien à la comparaison CSV / CSV.GZ.)*

**Ce que ça confirme** : décompresser un `.csv.gz` en amont (§1.2 de la spec)
ne coûte quasiment rien face au temps de parsing lui-même — la décompression
gzip d'un fichier de quelques Mo se mesure en millisecondes. Le vrai gain de
la Phase 10 n'est donc pas la vitesse de traitement (déjà réglée en Phase 9),
mais le **volume transféré sur le réseau** : un fichier 3 à 5 fois plus petit
à envoyer, pour un coût de décompression serveur négligeable.

Le Parquet va plus loin : une seule requête au lieu de deux (le format porte
déjà son schéma, pas besoin de confirmer un séparateur), et une compression
par colonne généralement meilleure qu'un gzip générique sur du texte.

## 2. Formats colonnaires : équivalence quel que soit le codec

`pl.read_parquet()` et `pl.read_ipc()` décodent nativement Snappy, Gzip et
Zstandard sans branche spécifique — vérifié empiriquement plutôt que supposé
(voir `backend/tests/test_compressed_formats.py::test_upload_parquet_variants_already_parsed`).
Le "format" `.parquet.gz` de la spec (Parquet avec compression interne gzip)
ne doit pas être confondu avec un Parquet *enveloppé* dans un gzip externe —
ce dernier cas n'existe pas dans les outils usuels (pandas/Polars/PyArrow
n'écrivent jamais un Parquet de cette façon), et n'a donc pas été implémenté :
le suffixe `.parquet.gz` désigne uniquement la codec interne, comme le fait
Polars lui-même.

## 3. Multi-séries : un graphique, pas N allers-retours

Avant la Phase 10, superposer deux grandeurs d'échelles différentes (ex :
chiffre d'affaires en euros et unités vendues) demandait soit de renoncer à
l'axe secondaire, soit de composer manuellement plusieurs graphiques. La
route `POST /api/plot/multi-series` construit la figure complète — jusqu'à 10
séries, chacune avec son propre type de trace et son axe — en un seul appel,
réutilisant le même moteur de sérialisation Plotly (`fig.to_json()`) que les
routes `/api/plot/1d|2d|3d` existantes. Le coût de construction reste dominé
par le nombre de points tracés, pas par le nombre de séries : ajouter des
traces à une figure Plotly déjà construite est de complexité linéaire en
nombre de points, pas en nombre de séries au carré.

## 4. Audit de vectorisation (§4.1 de la spec)

Recherche exhaustive de boucles Python ligne à ligne sur l'ensemble de
`backend/app/` (`.iterrows()`, `.apply(axis=1)`, `for i in range(len(df))`) :

- `app/report.py:426` et `app/stats_service.py:515` itèrent avec `.iterrows()`,
  mais sur des tables **déjà agrégées et bornées** (aperçu à `max_rows` lignes,
  motifs de valeurs manquantes limités à `MAX_MISSING_PATTERNS`) — pas sur le
  jeu de données complet. Aucun changement nécessaire.
- `app/formulas.py:235` utilise `df.apply(_row_eval, axis=1)` pour évaluer les
  colonnes calculées par formule utilisateur. C'est un choix architectural
  documenté (interpréteur AST restreint, pas d'`eval`/`exec`), pas un oubli :
  vectoriser un interpréteur de formules arbitraires exigerait de compiler
  chaque formule vers des opérations Polars/NumPy équivalentes — un projet en
  soi, hors du périmètre d'une passe d'optimisation. Le coût réel est
  d'ailleurs déjà mesuré et documenté en Phase 9 comme secondaire face au
  parsing CSV.
- Aucune autre occurrence trouvée. Les opérations GroupBy, filtrage,
  agrégation, stats passent déjà par les méthodes vectorisées de pandas
  (`.groupby()`, masques booléens, `.corr()`, `.describe()`).

**Sur la représentation pandas pour les analyses** : la Phase 9 avait déjà
tranché cette question et l'a documenté dans `CHANGELOG.md` — un groupby sur
500 000 lignes prend 35 ms en pandas, donc convertir vingt services vers
Polars pour gagner quelques millisecondes ne se justifie pas. La Phase 10 ne
revient pas sur cette décision : Polars reste cantonné au rôle de moteur de
*parsing* (CSV rapide, lecteur Parquet/Feather), pas de représentation de
travail.

## 5. Profilage à la demande

`DATAVORTEX_PROFILE=1` active `@profile_operation` (cProfile, 10 appels les
plus coûteux) et `@memory_tracker` (pic tracemalloc) sur l'agrégation GroupBy
et les statistiques avancées — désactivés par défaut car ils ralentissent
sensiblement l'exécution (cProfile ajoute typiquement 2 à 5x de surcoût). Un
développeur qui cherche pourquoi une agrégation particulière est lente
l'active ponctuellement, en local ; ni les benchmarks ci-dessus ni la CI ne
l'activent.

## Reproduire ces mesures

```bash
cd backend
python scripts/generate_test_data.py --rows 200000 --out /tmp/bench_200k.csv
gzip -k /tmp/bench_200k.csv
python -c "
import polars as pl
pl.read_csv('/tmp/bench_200k.csv').write_parquet('/tmp/bench_200k.parquet', compression='zstd')
"
# Puis mesurer upload+parse via TestClient (voir backend/tests/test_compressed_formats.py
# pour la structure des requêtes).
```
