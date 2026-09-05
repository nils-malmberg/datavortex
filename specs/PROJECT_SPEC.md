# DataVortex - Spécification Générale

## Vue d'ensemble
DataVortex est un visualiseur de données interactif permettant d'uploader, explorer, analyser et manipuler des fichiers de données (CSV, Excel) avec une interface web intuitive.

## Stack technique
- **Backend**: FastAPI + Python avec uv
- **Frontend**: React + Vite + Plotly.js
- **Gestion de paquets**: uv (backend), npm (frontend)
- **Déploiement**: GitHub Actions (CI/CD)
- **Visualisations**: Plotly (interactif)
- **Traitement données**: Pandas / Polars

---

## Fonctionnalités principales

### 1. Upload & Parsing de Fichiers

#### Upload multiple
- Drag & drop de fichiers CSV, Excel (.xlsx, .xls), JSON
- Sélection manuelle via explorateur fichiers
- Support fichiers jusqu'à 100MB (configurable)
- Aperçu du fichier avant parsing

#### Détection automatique séparateur
- Détection intelligente du séparateur (`,` `;` `\t` `|` ` `)
- Détection de l'encoding (UTF-8, Latin-1, etc)
- Interface pour confirmer/corriger le séparateur détecté
- Aperçu des premières lignes avec séparateur sélectionné
- Support des guillemets et échappements

#### Gestion des erreurs
- Signalement des lignes malformées
- Option ignorer/corriger erreurs
- Affichage des colonnes non parsées
- Prévue de traitement des valeurs manquantes (NaN, null, vides)

---

### 2. Exploration & Statistiques Descriptives

#### Aperçu des données
- Tableau scrollable et filtrable
- Affichage des 100 premières lignes (configurable)
- Types de colonnes détectés (int, float, string, date, bool)
- Compteur de lignes/colonnes
- Taille du fichier en mémoire

#### Statistiques globales par colonne
Pour chaque colonne :
- **Numériques**: Count, Mean, Median, Std Dev, Variance, Min, Q1, Q3, Max, Sum, Range
- **Catégories/Strings**: Count, Unique count, Mode, Most frequent values (top 10)
- **Dates**: Min date, Max date, Range, Distribution temporelle
- **Booleans**: True count, False count, % True

#### Détection des anomalies
- Détection valeurs manquantes (NaN) avec %
- Détection valeurs dupliquées
- Détection outliers (IQR method)
- Détection colonnes vides

#### Histogrammes & distributions
- Histogramme pour colonnes numériques (avec contrôle nombre bins)
- Distribution catégories pour colonnes string
- KDE density plot pour numériques (option)
- Box plot pour visualiser quartiles et outliers

---

### 3. Visualisations Interactives

#### Graphiques 1D (univariés)
- **Histogramme** : distribution numérique avec bins configurables
- **Box Plot** : quartiles, médiane, outliers
- **Violin Plot** : distribution avec densité
- **KDE Density** : courbe de densité lissée
- **Bar Chart** : pour catégories
- **Pie Chart** : proportions

#### Graphiques 2D (bivariés)
- **Scatter Plot** : avec options couleur/taille par colonne
- **Line Chart** : évolution temporelle ou séquence
- **Heatmap** : corrélation entre colonnes numériques
- **Hexbin** : densité 2D (pour gros datasets)
- **Bar Chart Groupé** : comparaison par catégorie
- **Bubble Chart** : 3 variables (x, y, size)

#### Graphiques 3D (trivariés)
- **Scatter 3D** : x, y, z avec coloration possible
- **Surface Plot** : fonction z=f(x,y)
- **3D Bar Chart** : données tricatégoriques

#### Options communes
- Titres et labels personnalisables
- Couleurs et thèmes (light/dark)
- Légende interactive
- Zoom et pan
- Hover info détaillé
- Export PNG/SVG/HTML interactif

---

### 4. Filtrage des Données

#### Interface Filter Builder
- Construction visuelle de filtres (pas besoin écrire requête)
- Support filtres simples ET complexes (AND/OR)

#### Types de filtres
- **Numériques**: `=`, `!=`, `>`, `<`, `>=`, `<=`, `between`, `in`
- **Strings**: `equals`, `contains`, `starts with`, `ends with`, `regex`
- **Dates**: `=`, `>`, `<`, `between`, `year`, `month`, `day`
- **Booleans**: `is true`, `is false`
- **Catégories**: `in`, `not in`
- **Valeurs manquantes**: `is null`, `is not null`

#### Fonctionnalités filtres
- Combiner multiples conditions avec AND/OR
- Nesting de conditions (parenthèses)
- Preview du résultat en temps réel
- Histogramme mis à jour après filtre
- Sauvegarde/charger filtres (sessionStorage)
- Bouton "Reset" pour revenir aux données originales
- Affichage: "N lignes sélectionnées sur M totales"

---

### 5. Création de Colonnes Calculées

#### Éditeur de formules
- Interface visuelle pour sélectionner colonnes
- Support des formules mathématiques simples
- Variables: référencer colonnes via `col_name` ou `{col_name}`

#### Opérateurs & Fonctions disponibles

**Arithmétiques**: `+`, `-`, `*`, `/`, `%`, `**` (puissance)

**Comparaison**: `==`, `!=`, `>`, `<`, `>=`, `<=`

**Logiques**: `and`, `or`, `not`

**Fonctions mathématiques**:
- `abs()`, `round(value, decimals)`, `sqrt()`, `pow(base, exp)`
- `log()`, `log10()`, `exp()`, `sin()`, `cos()`, `tan()`
- `ceil()`, `floor()`, `min()`, `max()`

**Fonctions de chaînes** (pour colonnes string):
- `upper()`, `lower()`, `strip()`, `len()`
- `concat()`, `replace()`, `substring()`

**Fonctions conditionnelles**:
- `if(condition, value_if_true, value_if_false)`

**Agrégations** (optionnel Phase 2):
- `count()`, `sum()`, `mean()`, `min()`, `max()` sur groupes

#### Exemples
- `{price} * {quantity}` → Total
- `{age} > 18` → Boolean (adulte)
- `{salary} * 1.1` → Salaire augmenté 10%
- `if({gender}=='M', 'Homme', 'Femme')` → Conversion catégorie
- `log({value})` → Transformation log

#### Validation
- Vérification syntaxe formule
- Gestion erreurs (division par 0, type mismatch)
- Preview résultat sur premières lignes
- Renommage colonne personnalisé
- Ajout à la suite des colonnes existantes

---

### 6. Export des Données

#### Export CSV
- Export données complètes (avec filtres appliqués)
- Inclure les colonnes calculées
- Choix du séparateur (`,` `;` `\t`)
- Choix de l'encoding (UTF-8, Latin-1)
- Bouton télécharger directement

#### Export graphiques
- **PNG** : haute résolution, bitmap
- **SVG** : format vectoriel (scalable)
- **HTML interactif** : graphique Plotly complet (zoomable, hover, etc)

#### Métadonnées export
- Inclure résumé stats dans fichier ZIP optionnel
- Noms fichiers avec timestamp (`data_2024-01-15_14h30.csv`)
- Inclure paramètres filtres appliqués en commentaire dans CSV

---

### 7. Gestion Sessions & Persistance

#### Session utilisateur
- Stockage données en mémoire serveur (temporary)
- Session ID unique par upload
- Expiration après 1h d'inactivité
- Possibilité d'avoir plusieurs fichiers ouverts en parallèle

#### Sauvegarde locale (frontend)
- État UI dans localStorage (colonnes visibles, filtres, etc)
- Cache aperçu données pour performance
- Restauration après refresh page

---

### 8. Performance & UX

#### Optimisations backend
- Pagination des données (100 lignes max affichées d'un coup)
- Chunking traitement fichiers volumineux
- Lazy loading des stats (calculées à la demande)
- Cache résultats stats et graphiques

#### Optimisations frontend
- Virtualisation tableau (millions de lignes possibles)
- Debouncing des filtres/recherches (300ms)
- Indicateurs loading/spinning
- Compression images export

#### Accessibilité
- Dark/Light mode
- Responsive design (desktop + tablette)
- Clavier shortcuts (Alt+F filtrer, Alt+C créer colonne, etc)
- Messages d'erreur clairs

---

## Flux utilisateur principal

1. **Accueil** : Page d'upload, drag & drop
2. **Parser** : Détection séparateur, aperçu, validation
3. **Dashboard** : Aperçu données + stats
4. **Analyse** : Construction graphiques, application filtres
5. **Manipulation** : Création colonnes calculées
6. **Export** : Télécharger données modifiées et graphiques

---

## Limitations & Assumptions

- Taille max fichier : 100MB (par défaut)
- Données stockées en mémoire (pas de base de données persistante)
- Une seule session par navigateur (ou localStorage)
- Pas de authentification (local/dev only)
- Pas de collaboration temps réel
- Pas d'import depuis URLs ou bases de données (Phase future)

---

## Technologies & Dépendances

### Backend (Python)
- `fastapi` : framework web
- `uvicorn` : serveur ASGI
- `pandas` / `polars` : traitement données
- `numpy` : calculs numériques
- `scipy` : statistiques avancées
- `plotly` : génération graphiques
- `python-multipart` : upload fichiers
- `chardet` : détection encoding

### Frontend (JavaScript)
- `React` : framework UI
- `Vite` : build tool
- `Plotly.js` : visualisations
- `Axios` : requêtes HTTP
- `React Router` : routing
- `TailwindCSS` : styling (optionnel)

### CI/CD
- GitHub Actions : tests et déploiement
- pytest : tests backend
- ESLint + Prettier : code quality frontend

---

## Phases de développement

### Phase 1 (MVP) : Upload & Stats basiques
- Upload + parsing
- Détection séparateur
- Stats descriptives simples
- Preview tableau

### Phase 2 : Visualisations
- Graphiques 1D, 2D, 3D
- Export graphiques (PNG, SVG, HTML)

### Phase 3 : Filtrage & Colonnes calculées
- Filter Builder
- Column Creator avec formules

### Phase 4 : Polish & CI/CD
- Export CSV avancé
- GitHub Actions (tests, linting, release)
- Documentation complète
- Déploiement (Docker optionnel)

---

## Succès Criteria

✓ Upload fichier CSV/Excel multiformat  
✓ Détection séparateur précise (>95%)  
✓ Stats complètes et correctes  
✓ Visualisations interactives et performantes  
✓ Filtrage flexible et intuitif  
✓ Colonnes calculées avec formules mathématiques  
✓ Export CSV et graphiques  
✓ Pas de crash sur 50MB+ fichiers  
✓ UI responsive et accessible  
✓ Code testé et documenté