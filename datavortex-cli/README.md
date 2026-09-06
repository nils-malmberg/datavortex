# datavortex (CLI)

Paquet de distribution de [DataVortex](https://github.com/nils-malmberg/datavortex) via `uv tool` :
une seule commande démarre l'API FastAPI et sert le frontend React pré-compilé sur le même port.

Ce dossier n'est pas le code source de l'application (voir `../backend` et `../frontend`) —
c'est l'emballage qui les distribue ensemble comme un exécutable unique.

## Installation locale (développement)

```bash
# 1. Compiler le frontend et le copier dans datavortex/static/
cd ../frontend && npm install && npm run build
mkdir -p ../datavortex-cli/datavortex/static
cp -r dist/* ../datavortex-cli/datavortex/static/

# 2. Installer le paquet CLI (mode outil, isolé du reste du système)
cd ../datavortex-cli
uv tool install --editable .

# 3. Lancer
datavortex
```

Voir [`../INSTALLATION.md`](../INSTALLATION.md) pour les instructions destinées aux utilisateurs finaux
(Windows, macOS, Linux) et [`../README.md`](../README.md) pour la présentation générale du projet.

## Structure

```
datavortex-cli/
├── pyproject.toml       # config du paquet uv tool (dépend de datavortex-backend en local)
├── datavortex/
│   ├── cli.py            # argparse : --port, --host, --open, --help-browser, --version
│   ├── server.py         # monte le frontend statique sur l'app FastAPI existante
│   ├── config.py         # port par défaut, chemin du dossier static/
│   └── static/           # frontend compilé (généré, non versionné — voir .gitignore)
└── tests/
    └── test_cli.py
```
