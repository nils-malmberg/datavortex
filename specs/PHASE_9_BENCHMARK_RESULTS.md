# Phase 9 — Résultats mesurés

Mesures réalisées sur la branche `feature/performance-optimization-polars`.

**Machine** : Linux 6.8, 8 cœurs, 31 Go de RAM, Python 3.11, Polars 1.44.2, pandas 2.1.0.
**Reproduction** :

```bash
cd backend
python scripts/generate_test_data.py --rows 500000 --out test_data/large_500k.csv
python scripts/benchmark.py --csv test_data/large_500k.csv
```

Chaque mesure est répétée trois fois, médiane retenue.

---

## 1. Jeu de 500 000 lignes (31,9 Mo, 9 colonnes)

### Analyse CSV

| Moteur | Durée | RSS | Gain |
|---|---|---|---|
| pandas, moteur Python — *avant* | 2,935 s | +628 Mo | — |
| pandas, moteur C | 0,621 s | +135 Mo | 4,7x |
| Polars, depuis les octets | 0,264 s | +186 Mo | 11,1x |
| **Polars, depuis un chemin disque — *après*** | **0,235 s** | **+96 Mo** | **12,5x** |

Lire depuis un chemin plutôt que depuis des octets en mémoire évite de matérialiser
le fichier côté Python : d'où l'écart de RSS entre les deux lignes Polars.

### Détection d'encoding et de séparateur

| Opération | Durée | Gain |
|---|---|---|
| chardet sur le fichier entier — *avant* | 8,237 s | — |
| chardet sur un échantillon de 256 Ko — *après* | 0,066 s | **125x** |
| détection du séparateur, fichier entier — *avant* | 0,082 s | — |
| détection du séparateur, échantillon — *après* | 0,002 s | 41x |

**C'était le coût dominant, et il n'apparaît pas dans la spec.** Huit secondes
passées à deviner l'encoding, contre trois à analyser le fichier. L'information
recherchée tient dans les premières lignes.

### Opérations analytiques

| Opération | pandas | Polars | Rapport |
|---|---|---|---|
| GroupBy (6 groupes) | 0,035 s | 0,015 s | 2,3x |
| Filtre (`age > 30`) | 0,024 s | 0,009 s | 2,7x |
| Tri par salaire | 0,139 s | 0,078 s | 1,8x |

**La spec se trompe sur ce point.** Elle annonce « GroupBy sur 500k+ lignes :
plusieurs secondes de délai ». En réalité pandas agrège 500 000 lignes en 35 ms.
Le délai de plusieurs secondes que ressentait l'utilisateur venait du chargement
(analyse + détection ≈ 11 s), pas de l'agrégation. C'est pourquoi cette phase ne
migre pas les opérations analytiques vers Polars : le gain serait de 20 ms, au
prix d'une conversion de représentation dans les vingt services qui consomment
des DataFrames pandas.

### Export CSV

| Chemin | Durée | Pic mémoire Python |
|---|---|---|
| construction en mémoire — *avant* | 12,07 s | 64,1 Mo |
| **émission par tranches de 10k lignes — *après*** | 12,13 s | **5,8 Mo** |

Le pic est divisé par 11 à durée égale. Les deux durées sont mesurées sous
`tracemalloc`, qui ralentit les deux lignes de la même façon (sans instrumentation :
≈ 1,5 s) ; c'est le pic qui est significatif ici, pas la durée absolue.

---

## 2. Fichier de 527 Mo (8 000 000 lignes)

Parcours complet, de la réception à l'export :

| Étape | Durée | RSS après |
|---|---|---|
| Réception des octets | 0,30 s | 709 Mo |
| Détection encoding + séparateur | 0,071 s | 710 Mo |
| Déversement sur disque + libération des octets | 0,36 s | **183 Mo** |
| Analyse CSV (Polars, depuis le disque) | 5,36 s | 3 456 Mo |
| GroupBy (6 groupes) | 1,47 s | 2 539 Mo |
| Filtre → 5 834 647 lignes | 0,39 s | 2 655 Mo |
| Export en flux (527 Mo émis) | 23,2 s | 2 257 Mo |

Le déversement fonctionne exactement comme prévu : la RSS retombe de 709 à
183 Mo, la session ne détenant plus qu'une seule copie des données.

---

## 3. Critères de succès de la spec (§10)

| Critère | Résultat | Statut |
|---|---|---|
| Fichiers 500 Mo+ chargés en < 5 s | 5,36 s | ⚠️ **manqué de peu** |
| GroupBy sur 500k lignes en < 1 s | 0,035 s | ✅ (1,47 s sur 8M lignes) |
| Filtres appliqués en < 500 ms | 24 ms sur 500k, 390 ms sur 8M | ✅ |
| Interface jamais figée | agrégations en tâche de fond, export en flux | ✅ |
| Mémoire < 2 Go pour un fichier de 500 Mo | 2,2 Go en régime stable, 3,4 Go de pic transitoire | ❌ **dépassé** |
| Export sans pic mémoire | pic divisé par 11 | ✅ |
| Pagination fluide | déjà livrée en Phase 8 | ✅ |
| Benchmarks documentés | ce document | ✅ |

### Pourquoi les deux critères manquants le sont

Le coupable n'est pas Polars, et le détail est net :

| Étape, sur le fichier de 527 Mo | Durée | Résultat |
|---|---|---|
| `pl.read_csv` | 0,84 s | frame Polars de 500 Mo |
| `.to_pandas()` (objets Python) | 3,18 s | DataFrame de **2 246 Mo** |
| `.to_pandas(use_pyarrow_extension_array=True)` | 0,25 s | DataFrame de **744 Mo** |

Polars lit les 527 Mo en 0,84 s. C'est la conversion vers la représentation
pandas qui coûte 3,18 s et 2,2 Go — parce que pandas stocke chaque chaîne comme
un objet Python distinct. Le détail par colonne le montre sans ambiguïté :

| Colonne | Type | Mémoire |
|---|---|---|
| `name` | object | 525 Mo |
| `date` | object | 511 Mo |
| `city` | object | 484 Mo |
| `department` | object | 473 Mo |
| `id`, `age`, `salary`, `score` | int64 / float64 | 61 Mo chacune |
| `active` | bool | 8 Mo |

Quatre colonnes de texte pèsent 1 993 Mo à elles seules. En représentation Arrow,
l'ensemble tombe à 744 Mo.

### Piste pour la suite

Adopter les types Arrow (`ArrowDtype`) comme représentation de travail ferait
passer le chargement de 527 Mo à ≈ 1,1 s et l'empreinte à ≈ 750 Mo — les deux
critères seraient alors largement tenus. Mais c'est un changement de
représentation qui traverse les vingt services consommant des DataFrames
(statistiques, graphiques, ML, formules, filtres), avec des différences de
comportement sur les valeurs nulles et les types. Cela mérite sa propre phase et
sa propre campagne de tests, pas un ajout discret en fin de Phase 9.

---

## 4. Réglage du seuil d'analyse rapide

La spec fixe le basculement vers Polars à 50 Mo (§2.2). Ce seuil laisse de côté
la taille de fichier la plus courante. Même fichier de 500 000 lignes (31,9 Mo),
mesuré à travers l'API :

| Seuil | Moteur retenu | Durée d'analyse |
|---|---|---|
| 50 Mo (défaut de la spec) | pandas, moteur Python | **3,15 s** |
| 1 Mo (`DATAVORTEX_FAST_PARSE_MB=1`) | Polars | **0,275 s** |

Un facteur 11 sur un cas parfaitement banal. Le seuil de 50 Mo a été retenu par
prudence, pour ne pas exposer les petits fichiers à des différences d'inférence
de type entre moteurs — mais `tests/test_performance.py::test_engines_agree`
vérifie précisément que les trois moteurs produisent le même tableau, valeurs
comprises, y compris sur les séparateurs entre guillemets et les colonnes à
valeurs manquantes.

**Recommandation** : abaisser le défaut à 5 Mo. Les deux seuils sont réglables
sans modifier le code :

```bash
DATAVORTEX_FAST_PARSE_MB=5   # bascule vers Polars
DATAVORTEX_SPILL_MB=50       # déversement de la source sur disque
```

Le défaut reste à 50 Mo dans cette branche, conformément à la spec.
