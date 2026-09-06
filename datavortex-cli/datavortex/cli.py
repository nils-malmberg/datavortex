"""Point d'entrée de la commande `datavortex`."""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser

from . import __version__
from .config import DEFAULT_HOST, get_default_port

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          DataVortex v{version:<10} Data Analysis Platform     ║
╚══════════════════════════════════════════════════════════════╝

  Serveur démarré sur {url}

  Fonctionnalités :
    • Exploration et visualisation interactive de données
    • Filtrage avancé, colonnes calculées, GroupBy, tableaux croisés
    • 20+ méthodes de machine learning (dont réseaux de neurones)
    • Génération de rapports PDF professionnels

  Aide intégrée : appuyez sur F1 dans l'application, ou lancez
    datavortex --help-browser

  Documentation complète : https://github.com/nils-malmberg/datavortex

  Astuce : Ctrl+C pour arrêter le serveur
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datavortex",
        description="DataVortex - plateforme interactive de visualisation et d'analyse de données",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=get_default_port(),
        help="Port d'écoute du serveur (défaut : 8000, ou $DATAVORTEX_PORT)",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Adresse d'écoute du serveur (défaut : {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--open", "-o",
        action="store_true",
        help="Ouvre automatiquement le navigateur au démarrage",
    )
    parser.add_argument(
        "--help-browser",
        action="store_true",
        help="Démarre le serveur et ouvre directement l'aide intégrée dans le navigateur",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}"
    print(BANNER.format(version=__version__, url=url))
    print("Chargement des modules (première initialisation, quelques secondes)...")

    # Import différé : charger app.main (pandas/scikit-learn/tensorflow...)
    # prend plusieurs secondes, on ne veut pas que ça se produise avant que
    # la bannière ci-dessus soit visible pour l'utilisateur.
    from .server import start_server

    if args.help_browser:
        target = f"{url}/?help=1"
        print(f"Ouverture de l'aide dans le navigateur ({target})...")
        threading.Timer(1.5, webbrowser.open, args=(target,)).start()
    elif args.open:
        print(f"Ouverture de {url} dans le navigateur...")
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    else:
        print(f"Ouvrez votre navigateur à l'adresse : {url}")

    try:
        start_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\n\n👋 Serveur DataVortex arrêté.")
        sys.exit(0)
    except OSError as exc:
        print(f"\n❌ Impossible de démarrer le serveur : {exc}")
        print(f"   Le port {args.port} est peut-être déjà utilisé : essayez `datavortex --port {args.port + 1}`.")
        sys.exit(1)


if __name__ == "__main__":
    main()
