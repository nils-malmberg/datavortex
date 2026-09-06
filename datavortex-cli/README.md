# datavortex (CLI)

Paquet de distribution de [DataVortex](https://github.com/nils-malmberg/datavortex) via `uv tool` :
une seule commande démarre l'API FastAPI et sert le frontend React pré-compilé sur le même port.

Ce dossier n'est pas le code source de l'application (voir `../backend` et `../frontend`) —
c'est l'emballage qui les distribue ensemble comme un exécutable unique.

`datavortex/static/` (le frontend compilé) est **commité dans le dépôt**, pas généré à l'installation — `uv tool install` n'a pas besoin de Node.js. Vous ne devez le régénérer que si vous modifiez le frontend :

```bash
cd ../frontend && npm install && npm run build
rm -rf ../datavortex-cli/datavortex/static
mkdir -p ../datavortex-cli/datavortex/static
cp -r dist/* ../datavortex-cli/datavortex/static/
# puis commitez datavortex-cli/datavortex/static/
```

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
