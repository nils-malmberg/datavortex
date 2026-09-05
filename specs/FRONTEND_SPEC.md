# Frontend DataVortex - Spécification

## Composants principaux

### 1. Upload Zone
- Drag & drop multiple fichiers
- Support CSV, Excel, JSON
- Détection séparateur automatique
- Option pour spécifier séparateur manuellement

### 2. Data Preview
- Tableau scrollable
- Aperçu 100 lignes
- Indicateurs types colonnes
- Boutons actions (filtrer, créer colonne, etc)

### 3. Statistics Panel
- Résumé par colonne (count, mean, median, std, min, max)
- Détection type données (numeric, string, date, etc)
- Histogrammes intégrés par colonne

### 4. Filter Builder
- Interface drag-and-drop pour filtres
- Conditions: =, !=, >, <, contains, in, etc
- Preview résultat

### 5. Column Creator
- Éditeur formules mathématiques simples
- Sélection colonnes via interface
- Aperçu résultat avant confirmation

### 6. Visualization Builder
- Sélecteur type plot (scatter, line, histogram, box plot, etc)
- Mapping colonnes aux axes
- Options (couleurs, tailles, labels, etc)
- Preview temps réel
- Export PNG/SVG

### 7. Export Options
- Export CSV (données filtrées + colonnes créées)
- Export graphiques (PNG, SVG, HTML interactif)