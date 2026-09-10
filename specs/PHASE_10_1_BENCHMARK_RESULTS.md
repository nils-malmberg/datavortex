# Phase 10.1 — Résultats de mesure sur 200 Mo

Mesures de bout en bout via le client de test FastAPI (pile HTTP complète), sur
un fichier de **209,6 Mo / 3,2 millions de lignes / 9 colonnes** généré par
`backend/scripts/generate_test_data.py --rows 3200000`. Reproductible avec
`pytest tests/test_performance_200mb.py -v`.

## 1. Avant / après

| Route | Avant | Après (1er appel) | Après (cache) | Gain |
|---|---|---|---|---|
| `POST /api/upload` | 7 271 ms | 7 003 ms | — | — |
| `POST /api/parse` | 2 527 ms | 1 622 ms | — | 1,6x |
| `GET /preview` | 850 ms | **27 ms** | 10 ms | **31x** |
| `GET /rows` (100 lignes) | 3 519 ms | 1 992 ms | **6 ms** | 1,8x / **580x** |
| `GET /stats` | 13 304 ms | 9 044 ms | **4 ms** | 1,5x / **3 300x** |
| `POST /groupby` | 622 ms | 577 ms | — | déjà sous la cible |
| `POST /filter` | 791 ms | 162 ms | — | 4,9x |
| `GET /stats/advanced` | 23 300 ms | 21 361 ms | **6 ms** | **3 500x** |
| `GET /profile/detailed` | **536 721 ms** | **10 105 ms** | **4 ms** | **53x** |
| `POST /plot/advanced` (nuage) | 6 800 ms / 36,3 Mo | 1 136 ms / **0,57 Mo** | — | 6x / **64x** |
| `POST /plot/subplots` (2x2) | 12 798 ms / 46,7 Mo | 1 390 ms / **1,32 Mo** | — | 9x / **35x** |

## 2. Ce que la spec supposait, et ce que la mesure a montré

La spec partait du principe que chaque route rechargeait le fichier avec
`pl.read_csv()` et qu'il suffisait de passer à `pl.scan_csv()` en lazy. Ce
n'est pas l'architecture de ce projet : le fichier est analysé **une fois** au
`/api/parse`, et toutes les routes travaillent sur le DataFrame pandas déjà en
mémoire dans la session. Il n'y avait donc pas de lecture à rendre paresseuse.

Les cibles annoncées comme critiques étaient d'ailleurs **déjà atteintes** :

- GroupBy : 622 ms mesurés, cible « < 3 s »
- Filtre : 791 ms mesurés, cible « < 1 s »

Les vrais coûts étaient ailleurs, et beaucoup plus graves :

### 2.1 Le profil détaillé prenait neuf minutes

`_inconsistent_formatting` parcourait en Python chaque forme canonique d'une
colonne texte et y relançait un `value_counts()`. Sur une colonne à 3,2
millions de valeurs distinctes, cela faisait 3,2 millions d'opérations pandas
minuscules, chacune payant son surcoût fixe. Le profilage (`cProfile`) le
montrait sans ambiguïté : `value_counts_arraylike` appelé 500 025 fois pour
500 000 lignes, soit une fois par ligne.

Corrigé en trois temps : calcul sur la table des valeurs distinctes plutôt que
sur les lignes, normalisation vectorisée (accesseurs `.str` au lieu d'un appel
Python par valeur — équivalence vérifiée par test sur les cas Unicode limites),
et abandon du contrôle au-delà de 10 000 valeurs distinctes, où « variante
d'écriture du même libellé » ne veut plus rien dire.

### 2.2 `detect_column_type` scannait toute la colonne pour en lire 30 valeurs

```python
sample = non_null.astype(str).head(30)   # convertit 3,2 M de valeurs, en garde 30
```

Environ 100 ms par appel, dans une fonction que presque toutes les routes
appellent, plusieurs fois par requête. L'échantillon est désormais prélevé sur
une fenêtre de tête bornée, avec repli sur la colonne entière si cette fenêtre
est vide (colonne creuse).

### 2.3 Une page de 100 lignes recalculait trois propriétés globales

`GET /rows` recalculait à chaque pagination les bornes d'outliers, les types de
colonnes et l'empreinte mémoire `deep=True` — trois parcours complets pour
afficher cent lignes. Ce sont des propriétés du jeu de données, pas de la page :
elles sont désormais en cache, indexées par version des données.

### 2.4 L'upload bloquait la boucle d'événements

`upload_file` est une coroutine `async def` qui enchaînait décompression,
analyse Excel/Parquet et écriture de 210 Mo sur disque **dans la boucle
d'événements** — donc toutes les autres requêtes attendaient, y compris celles
des autres onglets. C'est la cause directe du « l'interface se fige ». Ce
travail est passé dans le pool de threads.

À noter : les routes déclarées `def` (non `async`) sont déjà exécutées par
FastAPI dans un pool de threads. Le « vrai async » réclamé par la spec était
donc en place partout ailleurs ; seul `upload` y échappait, parce qu'il est le
seul à devoir être `async` (il attend le corps de la requête).

### 2.5 Une figure Plotly transporte ses données brutes

Un nuage de points sur 3,2 millions de lignes produisait **36 Mo de JSON**. Le
serveur les générait en 6,8 s, puis le navigateur devait désérialiser 36 Mo et
demander à Plotly de tracer 3,2 millions de points — pour un résultat visuel
qui n'est qu'une tache uniforme. C'est l'autre moitié du « l'interface se
fige », côté client cette fois.

Les traces point à point sont désormais plafonnées à 50 000 points
(`DATAVORTEX_MAX_PLOT_POINTS`), par tirage aléatoire à graine fixe. Les calculs
(tendance, repères statistiques) restent faits sur l'intégralité des données :
seul le tracé est échantillonné, et la figure l'affiche. Les barres d'un
sous-graphique agrègent par modalité au lieu d'émettre une barre par ligne.

## 3. Ce qui a été mesuré puis écarté

**Chaînes Arrow (`to_pandas(use_pyarrow_extension_array=True)`)** — très
tentant sur le papier, et les micro-mesures étaient excellentes : mémoire de
0,94 Go à 0,31 Go, `isna()` 39x plus rapide, `nunique()` 3x. Mais pandas 2.1.0
ne sait pas tout faire avec ces types : `Series.duplicated()` lève
`NotImplementedError` sur un `ArrowDtype`, et cette méthode est utilisée par
les statistiques par colonne. Abandonné — avec la mesure pour justifier la
décision plutôt qu'une intuition.

**Migration complète vers Polars** — la Phase 9 avait déjà tranché (un groupby
sur 500 000 lignes prend 35 ms en pandas) et la Phase 10 l'avait redocumenté.
Rien dans les mesures de la Phase 10.1 ne remet cette décision en cause : aucun
des coûts trouvés ne venait du moteur de calcul, tous venaient d'algorithmes
en O(n) déguisés ou de données envoyées inutilement.

## 4. Échantillonnage : ce qu'il faut savoir

Trois analyses portent désormais sur un échantillon plutôt que sur tout le
fichier. Dans les trois cas, le résultat le signale explicitement — un chiffre
calculé sur un échantillon ne doit jamais être présenté comme exhaustif :

| Analyse | Seuil | Pourquoi |
|---|---|---|
| Profil détaillé | 500 000 lignes | Ses indicateurs sont des proportions, qu'un échantillon aléatoire estime fidèlement. Affiché en clair dans l'onglet Profil. |
| Ajustement de lois | 50 000 points | Au-delà, le test de Kolmogorov-Smirnov rejette *toute* loi, y compris la bonne : l'échantillonnage est plus juste, pas seulement plus rapide. Même raison que le test de Shapiro-Wilk, déjà échantillonné avant cette phase. |
| Tracés point à point | 50 000 points | Au-delà, les points se superposent en une tache : aucun gain d'information, 36 Mo de JSON de perdus. Mentionné sur la figure. |

## 5. Ce qui reste lent, et pourquoi

- **Upload (7 s)** — dominé par le transfert de 210 Mo et son écriture sur
  disque. Peu compressible sans passer à un upload par tranches.
- **Stats (9 s au premier appel)** — coût réparti sur les colonnes texte
  stockées en objets Python. C'est exactement ce que les chaînes Arrow
  auraient résolu (§3) ; en attendant, le cache le ramène à 4 ms.
- **Stats avancées (21 s au premier appel)** — corrélations et tests de
  normalité sur neuf colonnes. Le cache le ramène à 6 ms.

Ces trois-là justifieraient un calcul en arrière-plan avec suivi de
progression (la mécanique existe déjà depuis la Phase 9 pour le groupby et les
filtres) plutôt qu'une optimisation supplémentaire.
