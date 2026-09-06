# Installation de DataVortex

DataVortex s'installe via [uv](https://docs.astral.sh/uv/), le gestionnaire de paquets Python, comme un outil en ligne de commande. Une seule commande installe l'application et toutes ses dépendances dans un environnement isolé — pas de configuration manuelle de venv, pas de conflit avec d'autres projets Python sur votre machine.

> **Important** : DataVortex n'est pas publié sur PyPI — `uv tool install datavortex` (sans rien d'autre) installerait un paquet totalement différent : PyPI a déjà un paquet nommé `datavortex` publié par quelqu'un d'autre, sans rapport avec ce projet. Utilisez toujours l'URL Git complète ci-dessous, pas juste le nom.

## Sommaire

- [Linux](#linux)
- [macOS](#macos-intel--apple-silicon)
- [Windows](#windows-powershell)
- [Vérifier l'installation](#vérifier-linstallation)
- [Mettre à jour](#mettre-à-jour)
- [Désinstaller](#désinstaller)
- [Dépannage par plateforme](#dépannage-par-plateforme)

---

## Linux

Testé sur Ubuntu/Debian et Fedora ; les mêmes commandes fonctionnent sur toute distribution avec un shell POSIX.

```bash
# 1. Installer uv (si ce n'est pas déjà fait)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Recharger le shell pour que la commande `uv` soit disponible
source ~/.bashrc   # ou ~/.zshrc selon votre shell

# 3. Installer DataVortex
uv tool install "git+https://github.com/nils-malmberg/datavortex.git#subdirectory=datavortex-cli"

# 4. Lancer
datavortex
```

L'application s'ouvre sur `http://127.0.0.1:8000`.

> **Distributions avec `uv` en paquet snap/flatpak confiné** : si `uv tool install` échoue avec une erreur de permission sur `~/.local/share/uv`, préférez l'installateur officiel ci-dessus plutôt que le paquet de votre distribution.

## macOS (Intel & Apple Silicon)

```bash
# 1. Installer uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Recharger le shell
source ~/.zshrc   # shell par défaut sur macOS récent

# 3. Installer DataVortex
uv tool install "git+https://github.com/nils-malmberg/datavortex.git#subdirectory=datavortex-cli"

# 4. Lancer
datavortex
```

Fonctionne nativement sur Apple Silicon (M1/M2/M3/M4) — aucune émulation Rosetta requise, toutes les dépendances (y compris TensorFlow) ont des builds ARM64.

> Si macOS bloque le premier lancement avec un avertissement Gatekeeper sur un binaire tiers installé par une dépendance, autorisez-le dans **Réglages Système → Confidentialité et sécurité**.

## Windows (PowerShell)

```powershell
# 1. Installer uv
irm https://astral.sh/uv/install.ps1 | iex

# 2. Ouvrir un nouveau terminal PowerShell (pour que le PATH soit à jour)

# 3. Installer DataVortex
uv tool install "git+https://github.com/nils-malmberg/datavortex.git#subdirectory=datavortex-cli"

# 4. Lancer
datavortex
```

> **Politique d'exécution PowerShell** : si l'installateur `install.ps1` est bloqué, exécutez d'abord `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` puis relancez la commande d'installation.

> **Pare-feu Windows** : à la première exécution, Windows peut demander si `datavortex` (Python) est autorisé à écouter sur le réseau. Autorisez uniquement le **réseau privé** — DataVortex n'a besoin d'écouter que sur `127.0.0.1`, pas d'accepter des connexions entrantes depuis Internet.

---

## Vérifier l'installation

```bash
datavortex --version
# datavortex 1.0.0

datavortex --help
```

## Mettre à jour

```bash
uv tool upgrade datavortex
```

`uv` se souvient d'où l'outil a été installé (l'URL Git) et récupère la dernière version depuis cette même source — pas besoin de repréciser l'URL complète.

## Désinstaller

```bash
uv tool uninstall datavortex
```

Cela retire la commande et son environnement isolé. Vos fichiers de données ne sont jamais stockés par DataVortex (tout reste en mémoire pendant l'exécution) : il n'y a rien d'autre à nettoyer.

---

## Dépannage par plateforme

### Toutes plateformes

| Problème | Solution |
|---|---|
| `datavortex: command not found` après installation | Le dossier des outils uv n'est pas dans le PATH. Lancez `uv tool update-shell` puis rouvrez le terminal. |
| `No executables are provided by package 'datavortex'` | Vous avez lancé `uv tool install datavortex` sans l'URL Git — cette commande a installé un paquet PyPI sans rapport qui porte le même nom par coïncidence. Désinstallez-le (`uv tool uninstall datavortex`) et réinstallez avec l'URL Git complète ci-dessus. |
| Port 8000 déjà utilisé | `datavortex --port 9000` |
| Le terminal semble figé au lancement | Normal la première fois : le message « Chargement des modules… » indique que pandas/scikit-learn/TensorFlow s'initialisent (quelques secondes). |

### Linux

| Problème | Solution |
|---|---|
| Erreur de compilation sur une dépendance native | Installez les paquets de développement système : `sudo apt install build-essential python3-dev` (Debian/Ubuntu) ou l'équivalent `dnf groupinstall "Development Tools"` (Fedora). |

### macOS

| Problème | Solution |
|---|---|
| `xcrun: error` lors de l'installation | Installez les outils en ligne de commande Xcode : `xcode-select --install` |

### Windows

| Problème | Solution |
|---|---|
| `uv` introuvable après installation | Redémarrez le terminal (le PATH n'est mis à jour que dans les nouvelles sessions) ou redémarrez la session Windows. |
| Antivirus bloque le lancement | Certains antivirus signalent à tort les binaires Python fraîchement installés ; ajoutez une exception pour le dossier `uv tool` (`%USERPROFILE%\.local\bin`) si besoin. |

Pour tout autre problème, voir la section **Dépannage** de l'aide intégrée (F1 dans l'application) ou [ouvrir une issue GitHub](https://github.com/nils-malmberg/datavortex/issues).
