#!/usr/bin/env bash
# Compile le frontend et le place dans le paquet CLI (datavortex-cli/datavortex/static/).
#
# `uv tool install` ne lance pas Node.js : il embarque le dossier static/ tel
# qu'il est commité. Pousser une modification du frontend sans avoir relancé ce
# script livre donc aux utilisateurs l'interface d'avant — c'est exactement ce
# qui est arrivé entre les Phases 9 et 10.1. À lancer avant chaque release,
# puis commiter datavortex-cli/datavortex/static/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATIC="$ROOT/datavortex-cli/datavortex/static"

echo "🔨 Build du frontend DataVortex"

cd "$ROOT/frontend"
# `npm ci` plutôt que `npm install` : installation reproductible depuis le
# lockfile, sans le modifier — la même que celle de la CI.
npm ci
npm run build

rm -rf "$STATIC"
mkdir -p "$STATIC"
cp -r dist/. "$STATIC/"

if [[ ! -f "$STATIC/index.html" ]]; then
  echo "❌ $STATIC/index.html manquant après le build" >&2
  exit 1
fi

echo "✅ Frontend compilé dans datavortex-cli/datavortex/static/ ($(find "$STATIC" -type f | wc -l) fichiers)"
echo "📦 Prochaine étape : git add datavortex-cli/datavortex/static && git commit"
