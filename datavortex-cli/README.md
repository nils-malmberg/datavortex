# datavortex (CLI)

Paquet de distribution de [DataVortex](https://github.com/nils-malmberg/datavortex) via `uv tool` :
une seule commande démarre l'API FastAPI et sert le frontend React pré-compilé sur le même port.

Ce dossier n'est pas le code source de l'application (voir `../backend` et `../frontend`) —
c'est l'emballage qui les distribue ensemble comme un exécutable unique.

`datavortex/static/` (le frontend compilé) est **commité dans le dépôt**, pas généré à l'installation — `uv tool install` n'a pas besoin de Node.js. Il doit donc être régénéré **à chaque modification du frontend**, sinon les utilisateurs installent l'interface d'avant (c'est arrivé entre les Phases 9 et 10.1) :

```bash
# à la racine du dépôt
./build.sh        # macOS / Linux
.\build.ps1       # Windows
git add datavortex-cli/datavortex/static && git commit -m "build: rebuild frontend"
```

`tests/test_bundle.py` (exécuté en CI) échoue si le bundle commité ne contient pas les fonctionnalités récentes du frontend.

## Installation locale (développement du paquet CLI lui-même)

```bash
cd datavortex-cli
uv tool install --editable .
datavortex
```

> Utilisateurs finaux : ne clonez pas ce dépôt pour installer DataVortex — voir
> [`../INSTALLATION.md`](../INSTALLATION.md), qui documente `uv tool install "git+https://...#subdirectory=datavortex-cli"`
> directement, sans clone manuel. **N'installez jamais avec juste `uv tool install datavortex`** :
> ce nom est déjà pris par un paquet PyPI sans rapport avec ce projet, l'installation échouerait
> silencieusement avec la mauvaise dépendance.

## Structure

```
datavortex-cli/
├── pyproject.toml       # config du paquet uv tool (dépend de datavortex-backend en local)
├── datavortex/
│   ├── cli.py            # argparse : --port, --host, --open, --help-browser, --version
│   ├── server.py         # monte le frontend statique sur l'app FastAPI existante
│   ├── config.py         # port par défaut, chemin du dossier static/
│   └── static/           # frontend compilé, commité — voir la note ci-dessus
└── tests/
    └── test_cli.py
```
