# DataVortex sur un poste d'entreprise (Windows 11 verrouillé, proxy, miroir)

Ce guide couvre ce qui diffère entre un poste personnel et un poste géré par
une DSI : réseau filtré, miroir de paquets interne, politiques qui bloquent
l'exécution de bibliothèques natives. Pour les versions de dépendances
acceptées, voir [COMPATIBILITY.md](COMPATIBILITY.md).

## Symptômes et diagnostic rapide

| Ce que vous voyez | Cause probable | Section |
|---|---|---|
| `uv tool install` échoue, « No solution found », timeouts, erreur TLS | pas d'accès direct à PyPI, ou proxy qui réécrit les certificats | [1](#1-installation-derrière-un-proxy-ou-un-miroir) |
| Tout fonctionne sauf **« Réseau de neurones »**, qui affiche « TensorFlow est installé mais Windows refuse de charger sa bibliothèque native » | le paquet est là, mais sa DLL est bloquée ou une dépendance système manque | [2](#2-tensorflow-ne-se-charge-pas) |
| « TensorFlow n'est pas installé dans cet environnement » | le miroir interne n'a pas `tensorflow-cpu`, l'installation l'a sauté | [1](#1-installation-derrière-un-proxy-ou-un-miroir) puis [3](#3-se-passer-de-tensorflow) |
| Le terminal semble figé une minute au premier entraînement | import de TensorFlow ralenti par l'antivirus (normal, une seule fois) | [2](#2-tensorflow-ne-se-charge-pas) |

Depuis la v1.2.4, `GET /api/ml/capabilities` (ou l'onglet ML → Réseau de
neurones) affiche la cause exacte et la piste à suivre. Les autres méthodes
de l'onglet ML (régression, classification, clustering, PCA — scikit-learn)
**ne dépendent pas de TensorFlow** et fonctionnent dans tous les cas.

## 1. Installation derrière un proxy ou un miroir

`uv` lit les variables standard `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`.

**Miroir PyPI interne** (Artifactory, Nexus, devpi…) — remplace PyPI pour
toute la résolution :

```powershell
# PowerShell
$env:UV_INDEX_URL = "https://miroir.entreprise/simple"
uv tool install ./datavortex-cli
```

```bash
# bash
UV_INDEX_URL=https://miroir.entreprise/simple uv tool install ./datavortex-cli
```

Avec `pip` plutôt que `uv` : `pip config set global.index-url https://miroir.entreprise/simple`,
puis `pip install ./datavortex-cli` dans un environnement virtuel.

**Proxy TLS d'inspection** (le certificat racine de l'entreprise est dans le
magasin Windows, mais pas connu de `uv`) :

```powershell
uv tool install --system-certs ./datavortex-cli      # ou $env:UV_SYSTEM_CERTS = "1"
# ou, avec le certificat exporté en PEM :
$env:SSL_CERT_FILE = "C:\certs\ca-entreprise.pem"
```

**Poste sans accès réseau** — préparer les wheels sur un poste connecté
(même OS, même architecture, même version de Python), puis installer hors
ligne :

```bash
# poste connecté
uv pip compile --python-version 3.11 backend/pyproject.toml -o requirements.txt
pip download -r requirements.txt -d wheels/

# poste isolé
uv tool install ./datavortex-cli --offline --no-index --find-links wheels/
```

Si le miroir ne fournit pas `tensorflow-cpu` (paquet lourd, parfois exclu
volontairement), l'installation échoue en bloc : demandez son ajout, ou
installez sans lui — voir [3](#3-se-passer-de-tensorflow).

## 2. TensorFlow ne se charge pas

Message typique dans l'interface ou dans `GET /api/ml/capabilities` :

> TensorFlow est installé mais Windows refuse de charger sa bibliothèque
> native (ImportError: DLL load failed while importing
> _pywrap_tensorflow_internal…)

Le paquet est bien installé ; c'est le chargement de sa DLL qui est refusé.
Trois causes couvrent l'essentiel des postes d'entreprise, à vérifier dans
cet ordre :

1. **Runtime Microsoft Visual C++ 2015-2022 absent.** TensorFlow a besoin de
   `msvcp140.dll`, `vcruntime140.dll` et `vcruntime140_1.dll`. Vérifiez dans
   « Applications installées » la présence de *Microsoft Visual C++ 2015-2022
   Redistributable (x64)* ; sinon, demandez son installation (souvent
   disponible dans le catalogue logiciel interne).
2. **AppLocker / antivirus qui bloque les DLL du profil utilisateur.**
   `uv tool install` place l'environnement dans
   `%LOCALAPPDATA%\uv\tools\datavortex\` ; une politique qui n'autorise
   l'exécution que depuis `Program Files` bloque `_pywrap_tensorflow_internal.pyd`.
   Un indice : l'Observateur d'événements → *Journaux des applications et des
   services → Microsoft → Windows → AppLocker*. Demandez une exception pour
   ce dossier, ou installez dans un chemin autorisé :
   `$env:UV_TOOL_DIR = "C:\Outils\uv"; $env:UV_TOOL_BIN_DIR = "C:\Outils\bin"; uv tool install ./datavortex-cli`
   (chemins approuvés par la DSI ; ajoutez le second au PATH).
3. **Processeur (ou machine virtuelle) sans AVX.** TensorFlow exige les
   instructions AVX. Tout processeur physique depuis 2011 les a ; ce sont
   les machines virtuelles (Citrix, VDI, Hyper-V avec compatibilité de
   processeur activée) qui les masquent parfois — à vérifier avec
   l'administrateur de la VM. Sans AVX, seule la section
   [3](#3-se-passer-de-tensorflow) s'applique.

La lenteur du **premier** entraînement (jusqu'à une minute) est normale :
l'antivirus analyse les ~500 Mo de TensorFlow au premier chargement. Les
suivants sont immédiats. DataVortex n'importe TensorFlow qu'à ce moment-là,
jamais au démarrage.

## 3. Se passer de TensorFlow

Quand aucune des pistes ci-dessus n'est possible, désactivez TensorFlow :
le réseau de neurones et l'export TFLite deviennent indisponibles (l'interface
l'explique), tout le reste — dont les 19 autres méthodes ML — fonctionne
normalement, et le serveur ne tente plus le chargement de la DLL.

```powershell
# Pour un lancement
datavortex --no-tensorflow

# Pour tous les lancements (PowerShell, utilisateur courant)
[Environment]::SetEnvironmentVariable("DATAVORTEX_NO_TENSORFLOW", "1", "User")
```

```bash
# Linux / macOS
export DATAVORTEX_NO_TENSORFLOW=1
```

`DATAVORTEX_NO_ML=1` est accepté comme synonyme (nom du plan initial) ; il ne
désactive **que** TensorFlow, pas les méthodes scikit-learn.

Pour ne même pas télécharger TensorFlow (miroir qui ne l'a pas, quota disque),
installez le backend sans lui puis posez la variable :

```bash
uv pip compile backend/pyproject.toml -o requirements.txt
grep -v -i tensorflow requirements.txt > requirements-sans-tf.txt
uv venv
uv pip install -r requirements-sans-tf.txt
uv pip install --no-deps ./backend ./datavortex-cli   # --no-deps : sinon TensorFlow revient
.venv/bin/datavortex --no-tensorflow                  # Windows : .venv\Scripts\datavortex.exe
```

## 4. Vérifier

```powershell
datavortex --version                       # 1.2.4
curl http://127.0.0.1:8000/api/health      # "tensorflow": {"probed": false, ...} — jamais sondé au démarrage
curl http://127.0.0.1:8000/api/ml/capabilities
#   {"tensorflow": {"available": true, "version": "2.20.0", ...}, "features": {"neural_network": true, ...}}
#   ou, si bloqué : {"available": false, "reason": "...", "hint": "..."}
```

## Environnements vérifiés

| Environnement | Réseau de neurones | Reste de l'application |
|---|---|---|
| Linux x86_64 (CI, Python 3.10–3.12) | ✅ | ✅ |
| Windows 11 personnel | ✅ (retour utilisateur) | ✅ |
| Windows 11 d'entreprise, DLL bloquée | ⚠️ diagnostic affiché, `--no-tensorflow` | ✅ |
| macOS Apple Silicon / Intel | non testé sur cette version | — |
