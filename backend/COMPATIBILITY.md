# Matrice de compatibilité — DataVortex v1.2.5

Depuis la Phase 10.3, `backend/pyproject.toml` déclare des **intervalles**
(`>=plancher,<plafond`) et non plus des versions figées (`==`). Un `==`
empêchait l'installation dès qu'un miroir d'entreprise n'avait pas ce wheel
précis ; un intervalle laisse l'installeur choisir parmi ce qui est disponible.

Ce document dit ce qui a **réellement été testé** — la suite complète du
backend (519 tests) exécutée à chaque extrémité des intervalles. Tout ce qui
est entre les deux est accepté par le résolveur mais n'a pas été exécuté
individuellement.

## Python

| Version | Statut | Note |
|---|---|---|
| 3.10 | ✅ testé | plancher (`X \| None`, `match` dans le code) |
| 3.11 | ✅ testé | recommandé |
| 3.12 | ❌ exclu depuis 1.2.5 | exigerait TensorFlow ≥ 2.16, dont les wheels Windows ne se chargent pas sur un poste d'entreprise (voir TensorFlow par plateforme). La 1.2.3 l'acceptait ; retiré après la régression constatée. |
| 3.13 | ❌ exclu | même raison |
| 3.9 | ❌ exclu | fin de vie (octobre 2025) ; les modèles Pydantic utilisent `int \| None`, qui n'existe pas à l'exécution en 3.9 |

## Dépendances directes

Colonne **Plancher** : la plus ancienne version acceptée, installée avec
`uv pip compile --resolution lowest-direct` sur Python 3.10 — toutes en même
temps, donc le pire cas. Colonne **Testé au plus haut** : ce que le lockfile
résout aujourd'hui, exécuté sur Python 3.10 et 3.11 (Linux), et sur Windows en 3.11 avec TensorFlow 2.15.

| Paquet | Intervalle déclaré | Plancher testé | Testé au plus haut | Pourquoi ce plancher / ce plafond |
|---|---|---|---|---|
| fastapi | `>=0.100.0,<1.0.0` | 0.100.0 | 0.141.1 | 0.100 = première version Pydantic v2 |
| uvicorn[standard] | `>=0.24.0,<1.0.0` | 0.24.0 | 0.52.4 | |
| pandas | `>=2.1.0,<3.0.0` | 2.1.0 | 2.3.3 | 2.0 : `pivot_table(dropna=False)` perd les modalités vides ; 3.0 change les chaînes et le copy-on-write par défaut |
| polars | `>=1.0.0,<2.0.0` | 1.0.0 | 1.44.2 | le code cible l'API 1.x (`truncate_ragged_lines`, `separator=`) |
| pyarrow | `>=12.0.0,<30.0.0` | 12.0.0 | 25.0.1 | pont Arrow pour `polars → pandas` |
| psutil | `>=5.9.0,<8.0.0` | 5.9.0 | 7.2.2 | |
| numpy | `>=1.24.0,<3.0.0` | 1.24.0 | 2.2.6 (3.10) · 2.4.6 (3.11) · 1.26.4 (Windows, imposé par TF 2.15) | NumPy 2 passe la suite ; le plafond est la prochaine majeure |
| scipy | `>=1.10.0,<1.19.0` | 1.10.0 | 1.15.3 (3.10) · 1.17.1 (3.11) | **1.19 retirera `critical_values` du résultat d'`anderson`**, utilisé par les tests de normalité (avertissement depuis 1.17) |
| plotly | `>=5.10.0,<6.0.0` | 5.10.0 | 5.24.1 | 5.10 = `texttemplate` sur les heatmaps ; Plotly 6 exige kaleido 1 |
| kaleido | Linux/macOS `>=0.2.1,<0.3.0` · **Windows `>=0.1.0.post1,<0.2.0`** | 0.2.1 | 0.2.1 (Windows : 0.1.0.post1) | kaleido 1.x exige un Chrome installé sur le poste ; **sur Windows la 0.2.1 bloque `to_image` indéfiniment** (constaté en CI : export PNG et rapport PDF ne rendaient jamais la main), la 0.1.0.post1 — publiée par kaleido pour ce cas, en wheels Windows uniquement — fonctionne |
| python-multipart | `>=0.0.6,<0.1.0` | 0.0.6 | 0.0.32 | |
| chardet | `>=4.0.0,<6.0.0` | 4.0.0 | 5.2.0 | |
| openpyxl | `>=3.1.0,<4.0.0` | 3.1.0 | 3.1.5 | 3.0.x utilise `np.float`, retiré de NumPy 1.24 |
| reportlab | `>=3.6.5,<5.0.0` | 3.6.5 | 4.5.1 | 3.6.5 = premiers wheels cp310 (avant : compilation, et `setup.py` télécharge des polices) |
| scikit-learn | `>=1.2.0,<2.0.0` | 1.2.0 | 1.7.2 (3.10) · 1.9.1 (3.11) | 1.6+ interroge `__sklearn_tags__` — corrigé côté code (adaptateur Keras) |
| matplotlib | `>=3.7.0,<4.0.0` | 3.7.0 | 3.10.9 (3.10) · 3.11.1 (3.11) | |
| jinja2 | `>=3.1.2,<4.0.0` | 3.1.2 | 3.1.6 | minimum exigé par `pandas.Styler` |
| skl2onnx | `>=1.16.0,<2.0.0` | 1.16.0 | 1.20.0 | |
| onnx | Linux/Apple Silicon `>=1.14.0,<2.0.0` · **Windows, macOS Intel `>=1.14.0,<1.18.0`** | 1.14.0 | 1.22.0 (Windows : 1.17.0) | 1.18+ lit `ml_dtypes.float4_e2m1fn` (ml_dtypes ≥ 0.5) sans le déclarer ; TensorFlow 2.15/2.16 imposent ml_dtypes 0.3 → `import onnx` plantait (constaté en CI Windows) |
| tensorflow-cpu / tensorflow-intel (Windows) | Linux `>=2.15.0,<2.21.0` · **Windows `>=2.15.0,<2.16.0`** | 2.15.0 (Keras 2) | 2.20.0 (Keras 3) sur Linux ; 2.15.x sur Windows | voir la section TensorFlow |

Dépendances de développement : `pytest>=7.4,<9`, `httpx>=0.25,<1`, `ruff>=0.6,<1`.

## TensorFlow par plateforme

Le module importé est toujours `tensorflow`, mais le paquet qui le fournit —
et la version qui se charge — dépendent de la plateforme. Les marqueurs de
`pyproject.toml` s'en chargent :

| Plateforme | Paquet | Intervalle | Raison |
|---|---|---|---|
| **Windows AMD64** | `tensorflow-intel` (ce que `tensorflow-cpu` installe réellement sur Windows : le wheel `tensorflow-cpu` n'y est qu'une coquille de 2 Ko) | `>=2.15,<2.16` | **Seule la 2.15 se charge de façon fiable.** À partir de la 2.16, les wheels Windows sont compilés avec une chaîne MSVC plus récente et exigent un runtime Visual C++ 2022 à jour ; sur un poste d'entreprise sans droits admin, `import tensorflow` échoue (`DLL load failed while importing _pywrap_tensorflow_internal`). Constaté en v1.2.3 (qui installait la 2.20) sur un poste où la v1.2.2 (2.15 figée) fonctionnait ; la 2.15 réinstallée sur ce même poste fonctionne. |
| Linux x86_64 | `tensorflow-cpu` | `>=2.15,<2.21` | wheels légers (sans CUDA) ; 2.15 et 2.20 testés en CI |
| macOS Apple Silicon | `tensorflow` | `>=2.15,<2.21` | `tensorflow-cpu` n'a pas de wheel arm64 ; `tensorflow-macos` (fork Apple, utilisé jusqu'en v1.2.1) s'arrête à 2.16 |
| macOS Intel | `tensorflow-cpu` | `>=2.15,<2.17` | plus aucun wheel macOS x86_64 après 2.16.2 |

La 2.15 n'a pas de wheel Python 3.12 : c'est ce qui borne `requires-python`
à `<3.12` pour tout le monde (on ne peut pas exprimer une fenêtre Python par
plateforme). La suite passe avec Keras 2 (TF 2.15) et Keras 3 (TF 2.20) : le
réseau de neurones, l'export TFLite et l'importance par permutation
fonctionnent dans les deux cas.

## Ce que garantit la CI

- `backend` (matrice 3.10 / 3.11) : le lockfile — donc les versions les plus
  récentes des intervalles — sur chaque interpréteur supporté.
- `backend-windows` (windows-latest, 3.11) : la résolution Windows retient
  bien TensorFlow 2.15, il se charge, et la suite passe. Windows n'était pas
  couvert avant la 1.2.5 — c'est là que la 2.20 a cassé sans que rien ne le
  voie.
- `backend-lowest` : chaque dépendance directe **à son plancher** sur 3.10.
  Si ce job casse après une modification du code, c'est que le code vient
  d'utiliser une API plus récente que le plancher : relevez le plancher (et
  cette matrice), ou évitez l'API.
- `test_dependencies.py` : aucun `==`, chaque dépendance a un plancher et un
  plafond, backend et CLI partagent la même fenêtre Python.

## Installation sur un réseau d'entreprise

Les intervalles permettent à l'installeur de prendre **ce que le miroir a**,
sans exiger un numéro précis. Trois cas courants :

**Miroir PyPI interne (Artifactory, Nexus, devpi…)**

```bash
# uv (recommandé) — le miroir remplace PyPI pour toute la résolution
UV_INDEX_URL=https://miroir.entreprise/simple uv tool install ./datavortex-cli

# pip, dans un environnement virtuel
pip install --index-url https://miroir.entreprise/simple ./datavortex-cli
```

**Proxy TLS d'inspection (certificat d'entreprise)**

```bash
uv tool install --system-certs ./datavortex-cli    # magasin de certificats du système (UV_SYSTEM_CERTS=1)
# ou, avec un bundle explicite :
SSL_CERT_FILE=/chemin/ca-entreprise.pem uv tool install ./datavortex-cli
```

**Poste sans accès réseau** — préparer les wheels depuis un poste connecté,
puis installer hors ligne :

```bash
# poste connecté (même OS, même architecture, même version de Python que la cible)
uv pip compile --python-version 3.11 backend/pyproject.toml -o requirements.txt
pip download -r requirements.txt -d wheels/   # uv n'a pas d'équivalent de `pip download`

# poste isolé
uv tool install ./datavortex-cli --offline --find-links wheels/ --no-index
```

À éviter : `pip install --no-binary :all:`. Il recompilerait NumPy, SciPy,
pandas, pyarrow et TensorFlow depuis les sources — TensorFlow ne se construit
pas ainsi, et le reste exige une chaîne de compilation complète et des heures.
Les planchers ci-dessus ont justement été choisis pour que **chaque**
dépendance existe en wheel sur Linux x86_64, macOS (Intel et Apple Silicon)
et Windows AMD64.

## Relever ou abaisser une borne

1. Modifiez l'intervalle dans `backend/pyproject.toml` (et `datavortex-cli/pyproject.toml` s'il s'agit d'uvicorn).
2. Plancher : `cd backend && uv pip compile --resolution lowest-direct --python-version 3.10 --extra dev pyproject.toml -o /tmp/lowest.txt`, installez-le dans un venv jetable et lancez `pytest`.
3. Plafond : `uv lock --upgrade && uv sync --extra dev && uv run pytest`.
4. Mettez cette matrice à jour, puis commitez `pyproject.toml` **et** `uv.lock`.
