# Changelog

Toutes les phases de développement notables de DataVortex sont documentées ici.

## Phase 4 — Export & CI/CD

- Export CSV de la vue active (filtres + colonnes calculées appliqués),
  séparateur et encoding configurables (UTF-8/Latin-1), filtre actif
  documenté en commentaire en tête de fichier
- Export des graphiques en PNG/SVG/HTML (existant depuis la Phase 2,
  intégré à l'onglet Export)
- Suite de tests pytest (40 tests : moteur de formules, moteur de filtres,
  API de bout en bout) + lint ruff côté backend
- Workflows GitHub Actions : `test.yml` (pytest + ruff + eslint + build,
  sur push/pull_request) et `deploy.yml` (validation de build Docker sur
  push vers `main`)
- Dockerfiles backend/frontend + `docker-compose.yml` pour un lancement
  local en une commande
- README complet : installation, lancement (local et Docker), limitations
  connues, exemples d'utilisation, roadmap
- Fix : une condition de filtre fraîchement ajoutée (encore vide)
  déclenchait une requête invalide côté frontend avant que l'utilisateur
  ait fini de la configurer

## Phase 3 — Filtrage & colonnes calculées

- Filter Builder : conditions combinées en ET/OU, opérateurs adaptés au
  type de colonne (numérique, texte, booléen, date, valeurs manquantes)
- Moteur de formules sûr pour les colonnes calculées (parsing AST Python,
  jamais `eval`/`exec`), avec aperçu avant validation
- Le filtre actif et les colonnes calculées se propagent automatiquement
  à l'aperçu, aux statistiques et aux graphiques

## Phase 2 — Visualisations

- Graphiques 1D (histogramme, box, violin, KDE, bar, pie), 2D (scatter,
  line, heatmap, hexbin, bar groupé, bubble) et 3D (scatter3D, surface)
  via Plotly
- Export PNG/SVG/HTML par graphique
- Fix : bug de synchronisation état/UI empêchant la génération des
  graphiques 2D/3D tant que l'utilisateur ne re-sélectionnait pas
  manuellement chaque colonne

## Phase 1 — MVP

- Upload de fichiers CSV/Excel/JSON, détection automatique de
  l'encoding et du séparateur, confirmation manuelle
- Aperçu des données (100 premières lignes) et statistiques descriptives
  par colonne (numériques, chaînes, booléens, dates)
- Gestion d'erreurs cohérente sur toute l'API (`{"error": {"code", "message"}}`)
