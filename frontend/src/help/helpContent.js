/**
 * Contenu de l'aide intégrée (panneau Aide, F1 / Ctrl+H).
 *
 * Source unique de vérité : ce module alimente à la fois la navigation par
 * section, le rendu de chaque page d'aide et la recherche (HelpSearch).
 * Chaque topic a un corps structuré en blocs (paragraphe, étapes, liste,
 * note, exemple de code) plutôt qu'une chaîne markdown — pas de dépendance
 * supplémentaire à charger juste pour du texte formaté.
 */

// Un topic peut fournir `dynamic: 'shortcuts'` : son corps est alors généré
// à l'affichage à partir de SHORTCUT_HELP (hooks/useKeyboardShortcuts), pour
// ne jamais désynchroniser la doc des raccourcis réellement branchés.

export const HELP_SECTIONS = [
  {
    id: 'getting-started',
    title: 'Prise en main',
    topics: [
      {
        id: 'gs-installation',
        title: 'Installer DataVortex',
        keywords: ['installation', 'uv', 'windows', 'macos', 'linux', 'setup'],
        body: [
          { kind: 'p', text: "DataVortex se distribue comme un outil en ligne de commande unique via uv, le gestionnaire de paquets Python. Une seule commande installe l'application et toutes ses dépendances (FastAPI, pandas, scikit-learn, TensorFlow…) dans un environnement isolé, sans configuration manuelle." },
          { kind: 'steps', title: 'Linux / macOS', items: [
            'Installer uv : curl -LsSf https://astral.sh/uv/install.sh | sh',
            'Installer DataVortex : uv tool install datavortex',
            'Lancer : datavortex',
          ] },
          { kind: 'steps', title: 'Windows (PowerShell)', items: [
            'Installer uv : irm https://astral.sh/uv/install.ps1 | iex',
            'Installer DataVortex : uv tool install datavortex',
            'Lancer : datavortex',
          ] },
          { kind: 'note', text: "L'application s'ouvre par défaut sur http://127.0.0.1:8000. Un pare-feu peut demander une autorisation la première fois : DataVortex n'écoute que sur votre machine (127.0.0.1), rien ne sort vers l'extérieur." },
        ],
        related: ['gs-first-steps', 'ts-common-issues'],
      },
      {
        id: 'gs-first-steps',
        title: 'Premiers pas',
        keywords: ['premiers pas', 'tutoriel', 'upload', 'commencer'],
        body: [
          { kind: 'p', text: "Une fois DataVortex ouvert dans le navigateur, l'écran d'accueil propose de déposer un fichier (glisser-déposer ou clic pour parcourir). CSV, Excel (.xls/.xlsx) et JSON sont acceptés." },
          { kind: 'steps', items: [
            'Déposez votre fichier sur la zone d\'import.',
            "Pour un CSV, vérifiez le séparateur détecté automatiquement (virgule, point-virgule, tabulation, pipe) — vous pouvez le corriger avant de valider.",
            'Cliquez sur « Valider et parser ».',
            "Le tableau de bord s'ouvre : aperçu des données en haut, onglets d'analyse en dessous (Stats, Visualisations, Filtres…).",
          ] },
          { kind: 'note', text: "Rien n'est envoyé sur Internet : le fichier reste en mémoire côté serveur local, dans une session identifiée par un ID, jusqu'à ce que vous fermiez l'onglet ou rechargiez un autre fichier." },
        ],
        related: ['up-formats', 'ex-preview-rows'],
      },
      {
        id: 'gs-shortcuts',
        title: 'Raccourcis clavier',
        keywords: ['raccourcis', 'clavier', 'shortcuts'],
        dynamic: 'shortcuts',
        body: [
          { kind: 'p', text: "DataVortex peut s'utiliser presque entièrement au clavier. Voici la liste complète des raccourcis actifs une fois un fichier chargé." },
        ],
        related: ['gs-first-steps'],
      },
      {
        id: 'gs-troubleshooting',
        title: 'Un problème au démarrage ?',
        keywords: ['problème', 'erreur', 'ne démarre pas', 'port'],
        body: [
          { kind: 'p', text: "Les soucis les plus fréquents au premier lancement sont un port déjà occupé ou une commande introuvable après l'installation." },
          { kind: 'list', items: [
            'Port occupé : datavortex --port 9000 pour en choisir un autre.',
            "Commande « datavortex » introuvable : vérifiez que le dossier des outils uv est bien dans votre PATH (uv tool update-shell puis rouvrez le terminal).",
            "La page ne charge pas : vérifiez qu'aucun message d'erreur ne s'affiche dans le terminal où datavortex tourne.",
          ] },
          { kind: 'note', text: 'Pour la liste complète des problèmes connus et leurs solutions, voir la section Dépannage.' },
        ],
        related: ['ts-common-issues', 'ts-getting-help'],
      },
    ],
  },

  {
    id: 'upload',
    title: 'Import & parsing',
    topics: [
      {
        id: 'up-formats',
        title: 'Formats de fichiers supportés',
        keywords: ['formats', 'csv', 'excel', 'xlsx', 'json', 'import'],
        body: [
          { kind: 'p', text: 'Trois formats sont pris en charge à l\'import :' },
          { kind: 'list', items: [
            'CSV — avec détection automatique du séparateur et de l\'encoding.',
            'Excel — .xls et .xlsx (première feuille du classeur).',
            'JSON — un tableau d\'objets, une ligne par enregistrement.',
          ] },
          { kind: 'note', text: "Le Parquet n'est pas un format d'import : il n'apparaît que côté export de modèles/rapports (formats de sortie, pas d'entrée)." },
        ],
        related: ['up-separator', 'up-issues'],
      },
      {
        id: 'up-separator',
        title: 'Détection du séparateur et de l\'encodage',
        keywords: ['séparateur', 'encoding', 'utf-8', 'latin-1', 'détection'],
        body: [
          { kind: 'p', text: "À l'upload, DataVortex teste plusieurs séparateurs candidats (virgule, point-virgule, tabulation, pipe) sur un échantillon du fichier et propose celui qui donne le nombre de colonnes le plus cohérent sur les premières lignes. L'encoding est détecté automatiquement (chardet)." },
          { kind: 'steps', items: [
            "Avant de cliquer sur « Valider et parser », un aperçu brut des premières lignes s'affiche.",
            'Si les colonnes ne se découpent pas correctement, changez le séparateur proposé dans la liste déroulante.',
            'Validez : le fichier est reparsé avec le séparateur choisi.',
          ] },
        ],
        related: ['up-formats', 'up-issues'],
      },
      {
        id: 'up-issues',
        title: 'Problèmes courants à l\'import',
        keywords: ['erreur import', 'fichier vide', 'accents', 'caractères bizarres'],
        body: [
          { kind: 'list', items: [
            "Fichier vide → message d'erreur explicite, rien à parser.",
            'Caractères accentués mal affichés → l\'encoding détecté ne correspond pas au fichier réel ; réexportez le CSV en UTF-8 depuis votre logiciel source si possible.',
            "Excel avec plusieurs feuilles → seule la première feuille du classeur est lue.",
            "Toutes les colonnes fusionnées en une seule → mauvais séparateur détecté, corrigez-le manuellement avant de valider.",
          ] },
        ],
        related: ['up-separator', 'ts-common-issues'],
      },
      {
        id: 'up-example',
        title: 'Exemple : importer un fichier de ventes',
        keywords: ['exemple', 'tutoriel', 'ventes'],
        body: [
          { kind: 'p', text: "Un petit jeu de données de démonstration (examples/ventes_demo.csv à la racine du dépôt) illustre les exemples de ce guide : colonnes Region, Produit, Date, Unites, Prix_Unitaire, Revenu, Cout, Profit." },
          { kind: 'steps', items: [
            'Importez examples/ventes_demo.csv.',
            'Séparateur virgule, encoding UTF-8 — la détection automatique doit déjà proposer les bonnes valeurs.',
            'Validez : vous obtenez un tableau prêt pour les exemples GroupBy, Pivot et Machine Learning de ce guide.',
          ] },
        ],
        related: ['dm-groupby-basics', 'dm-pivot'],
      },
    ],
  },

  {
    id: 'exploration',
    title: 'Exploration des données',
    topics: [
      {
        id: 'ex-stats-summary',
        title: 'Statistiques descriptives',
        keywords: ['stats', 'moyenne', 'médiane', 'écart-type', 'résumé'],
        body: [
          { kind: 'p', text: "L'onglet Stats calcule pour chaque colonne numérique : moyenne, médiane, écart-type, min/max, quartiles, asymétrie (skewness) et aplatissement (kurtosis). Pour les colonnes catégorielles : nombre de valeurs uniques, valeur la plus fréquente, répartition." },
          { kind: 'note', text: "Ces mêmes statistiques détaillées sont incluses par défaut dans tout rapport PDF généré — inutile de les recopier manuellement." },
        ],
        related: ['ex-stats-correlations', 'exp-pdf-defaults'],
      },
      {
        id: 'ex-stats-correlations',
        title: 'Corrélations et p-values',
        keywords: ['corrélation', 'pearson', 'spearman', 'kendall', 'p-value'],
        body: [
          { kind: 'p', text: "La matrice de corrélation entre colonnes numériques est disponible selon trois méthodes : Pearson (linéaire), Spearman et Kendall (rangs, plus robustes aux valeurs extrêmes et aux relations non linéaires monotones). Chaque coefficient est accompagné de sa p-value." },
          { kind: 'note', text: "Une p-value élevée (par convention > 0.05) signifie que la corrélation observée n'est pas statistiquement distinguable de zéro : à interpréter avec prudence, surtout sur peu de lignes." },
        ],
        related: ['st-correlation-tests', 'viz-2d'],
      },
      {
        id: 'ex-stats-distributions',
        title: 'Analyse de distribution',
        keywords: ['distribution', 'histogramme', 'loi', 'ajustement'],
        body: [
          { kind: 'p', text: "Pour une colonne numérique, DataVortex peut ajuster plusieurs lois théoriques (normale, exponentielle, uniforme, log-normale) et comparer leur qualité d'ajustement via le critère AIC (qui pénalise les modèles à plus de paramètres, pour éviter de toujours préférer la loi la plus flexible)." },
        ],
        related: ['st-goodness-of-fit', 'viz-1d'],
      },
      {
        id: 'ex-missing-data',
        title: 'Données manquantes',
        keywords: ['manquant', 'nan', 'null', 'valeurs vides'],
        body: [
          { kind: 'p', text: "Le profil détaillé (onglet Profil) affiche, par colonne, le nombre et le pourcentage de valeurs manquantes, ainsi que les motifs de coïncidence entre colonnes (les valeurs manquent-elles ensemble, ou indépendamment ?)." },
        ],
        related: ['ex-profile-quality'],
      },
      {
        id: 'ex-preview-rows',
        title: 'Aperçu : numéros de ligne et navigation',
        keywords: ['aperçu', 'numéro de ligne', 'pagination', 'preview'],
        body: [
          { kind: 'p', text: "La colonne « # » (activable/désactivable) affiche l'index original de chaque ligne dans le fichier source — y compris après un filtre : si vous filtrez age > 25 et que Bob/Carol occupaient les lignes 2 et 3 du fichier, ils restent numérotés 2 et 3, pas renumérotés 1 et 2. Utile pour retrouver une ligne dans le fichier d'origine." },
          { kind: 'note', text: "L'aperçu est paginé et peut être redimensionné (glisser la poignée sous le tableau) ou replié entièrement pour gagner de la place." },
        ],
        related: ['ex-preview-search-sort', 'dm-filters-simple'],
      },
      {
        id: 'ex-preview-search-sort',
        title: 'Recherche, tri et colonnes',
        keywords: ['recherche', 'tri', 'ctrl+f', 'colonnes largeur'],
        body: [
          { kind: 'list', items: [
            'Ctrl+F place le curseur dans la recherche du tableau (recherche texte sur toutes les colonnes visibles).',
            'Cliquer sur un en-tête de colonne trie par cette colonne ; un second clic inverse le sens.',
            'Les colonnes se redimensionnent en glissant le bord droit de leur en-tête.',
          ] },
        ],
        related: ['ex-preview-rows'],
      },
      {
        id: 'ex-profile-quality',
        title: 'Score de qualité des données',
        keywords: ['qualité', 'score', 'quality score'],
        body: [
          { kind: 'p', text: "Le score de qualité (0-100, onglet Profil) combine le taux de complétude, la présence de doublons, la cohérence des types de colonnes et la proportion de valeurs aberrantes détectées. Un score bas déclenche des suggestions concrètes (colonnes à nettoyer, lignes à examiner) plutôt qu'un simple chiffre." },
        ],
        related: ['ex-missing-data', 'ex-profile-anomalies'],
      },
      {
        id: 'ex-profile-anomalies',
        title: 'Détection d\'anomalies et suggestions',
        keywords: ['anomalies', 'outliers', 'suggestions'],
        body: [
          { kind: 'p', text: "Le profil détecte les valeurs aberrantes par colonne numérique (méthode IQR) et propose des actions correctives : créer une colonne filtrée, binner une colonne à forte cardinalité, encoder une catégorielle avant du machine learning, etc. Ces suggestions apparaissent aussi dans le rapport PDF." },
        ],
        related: ['ex-profile-quality', 'dm-columns-transform'],
      },
    ],
  },

  {
    id: 'visualization',
    title: 'Visualisation',
    topics: [
      {
        id: 'viz-1d',
        title: 'Graphiques 1D',
        keywords: ['histogramme', 'boîte', 'violon', 'densité', 'kde', 'camembert'],
        body: [
          { kind: 'p', text: "Types disponibles pour une seule variable : histogramme, boîte à moustaches (box plot), violon, densité (KDE), barres et camembert. Tous acceptent un regroupement optionnel par une colonne catégorielle (color_by / group_by)." },
        ],
        related: ['viz-advanced-types', 'viz-customization'],
      },
      {
        id: 'viz-2d',
        title: 'Graphiques 2D',
        keywords: ['nuage de points', 'scatter', 'ligne', 'heatmap', 'bulles', 'hexbin'],
        body: [
          { kind: 'p', text: "Types disponibles pour deux variables : nuage de points, ligne, heatmap (matrice de corrélation ou densité), hexbin (nuage de points agrégé en hexagones pour les gros volumes), barres groupées, bulles (taille = 3ᵉ variable)." },
        ],
        related: ['viz-trendlines', 'viz-3d'],
      },
      {
        id: 'viz-3d',
        title: 'Graphiques 3D',
        keywords: ['3d', 'scatter3d', 'surface'],
        body: [
          { kind: 'p', text: "Nuage de points 3D (x, y, z + couleur optionnelle) et surface. Interactifs : rotation à la souris, zoom à la molette." },
        ],
        related: ['viz-2d'],
      },
      {
        id: 'viz-advanced-types',
        title: 'Pair plots, joint plots et graphiques avancés',
        keywords: ['pair plot', 'joint plot', 'ridge', 'essaim', 'strip'],
        body: [
          { kind: 'p', text: "Au-delà des types classiques : pair plot (matrice de nuages de points croisant toutes les colonnes sélectionnées), joint plot (nuage de points + distributions marginales), ridge plot (distributions superposées par groupe), strip/essaim (points individuels avec dispersion pour éviter le chevauchement)." },
        ],
        related: ['viz-1d', 'viz-2d'],
      },
      {
        id: 'viz-customization',
        title: 'Personnalisation des graphiques',
        keywords: ['couleurs', 'palette', 'daltonisme', 'thème', 'annotations', 'légende'],
        body: [
          { kind: 'list', items: [
            'Palettes : Default, Viridis, Plasma, Inferno, Cividis, Twilight, Okabe-Ito, Tol Bright.',
            'Modes daltonisme : deutéranopie, protanopie, tritanopie, ou niveaux de gris — recalcule la palette pour rester lisible.',
            'Position de la légende, échelle des axes (linéaire/log), grille, titres et sous-titres personnalisables.',
            "Annotations libres : texte positionné à des coordonnées (x, y), avec ou sans flèche.",
          ] },
        ],
        related: ['viz-export'],
      },
      {
        id: 'viz-trendlines',
        title: 'Lignes de tendance et bandes de confiance',
        keywords: ['tendance', 'régression', 'lowess', 'confiance'],
        body: [
          { kind: 'p', text: "Sur un graphique 2D, une ligne de tendance peut être ajoutée : linéaire, polynomiale (degré ajustable) ou LOWESS (lissage local, utile pour des relations non linéaires). Une bande de confiance à 95% ou 99% peut être superposée, et l'équation affichée directement sur le graphique." },
        ],
        related: ['viz-2d', 'ml-regression'],
      },
      {
        id: 'viz-export',
        title: 'Exporter un graphique',
        keywords: ['export plot', 'png', 'svg', 'html'],
        body: [
          { kind: 'p', text: "Chaque graphique s'exporte en PNG ou SVG (image statique, résolution et taille configurables) ou en HTML (fichier interactif autonome, zoom/survol conservés, ouvrable dans n'importe quel navigateur sans DataVortex)." },
          { kind: 'note', text: "L'export ouvre une boîte de dialogue « Enregistrer sous » native du navigateur (pas de téléchargement automatique dans un dossier par défaut) — voir Export & Rapports." },
        ],
        related: ['exp-plots'],
      },
    ],
  },

  {
    id: 'manipulation',
    title: 'Manipulation des données',
    topics: [
      {
        id: 'dm-filters-simple',
        title: 'Filtres simples',
        keywords: ['filtre', 'condition', 'égal', 'supérieur'],
        body: [
          { kind: 'p', text: "Un filtre est une condition sur une colonne (égal, différent, supérieur/inférieur, contient, commence par, entre deux valeurs, dans une liste…). Le filtre s'applique à toute la session : les onglets Stats, Visualisations, GroupBy, Export, etc. reflètent automatiquement les données filtrées." },
        ],
        related: ['dm-filters-advanced', 'ex-preview-rows'],
      },
      {
        id: 'dm-filters-advanced',
        title: 'Conditions avancées',
        keywords: ['et', 'ou', 'regex', 'entre', 'groupe de conditions', 'inverser'],
        body: [
          { kind: 'p', text: "Les conditions se combinent en groupes ET/OU imbriqués (ex : (Région = \"Nord\" OU Région = \"Est\") ET Profit > 0). Les opérateurs incluent aussi les expressions régulières et les intervalles. Un filtre peut être inversé (voir les lignes exclues plutôt qu'incluses) — pratique pour auditer ce qu'un filtre retire." },
        ],
        related: ['dm-filters-simple'],
      },
      {
        id: 'dm-columns-formulas',
        title: 'Créer des colonnes avec des formules',
        keywords: ['formule', 'colonne calculée', 'if', 'fonctions'],
        body: [
          { kind: 'p', text: "Les formules référencent les colonnes existantes entre accolades et acceptent les opérateurs +, -, *, /, %, ^ ainsi qu'un jeu de fonctions." },
          { kind: 'list', items: [
            'Fonctions : abs, round, sqrt, pow, log, log10, exp, sin, cos, tan, ceil, floor, min, max',
            'Texte : upper, lower, strip, len, concat, replace, substring',
            'Conditionnelle : if(condition, valeur_si_vrai, valeur_si_faux)',
          ] },
          { kind: 'code', text: 'marge = ({Revenu} - {Cout}) / {Revenu} * 100\nstatut = if({marge} > 20, "Rentable", "À surveiller")' },
        ],
        related: ['dm-columns-transform', 'up-example'],
      },
      {
        id: 'dm-columns-transform',
        title: 'Transformer une colonne',
        keywords: ['binning', 'encodage', 'lag', 'rolling', 'discrétisation'],
        body: [
          { kind: 'list', items: [
            'Binning — découpe une colonne numérique en classes (largeur égale, quantiles, ou bornes personnalisées).',
            "Encodage — transforme une colonne catégorielle en valeurs numériques (label ou one-hot) avant du machine learning.",
            "Lag — décale une colonne de N lignes (utile pour comparer une valeur à sa précédente).",
            "Rolling — moyenne/somme/écart-type glissant sur une fenêtre de N lignes.",
          ] },
        ],
        related: ['dm-columns-formulas', 'ex-profile-anomalies'],
      },
      {
        id: 'dm-columns-manage',
        title: 'Renommer, dupliquer, réordonner, supprimer',
        keywords: ['renommer', 'dupliquer', 'supprimer colonne', 'réordonner'],
        body: [
          { kind: 'p', text: "L'onglet Colonnes permet de renommer une colonne, la dupliquer, la supprimer (au moins une colonne doit toujours rester) ou changer l'ordre d'affichage des colonnes — sans jamais toucher au fichier source." },
        ],
        related: ['dm-columns-formulas'],
      },
      {
        id: 'dm-groupby-basics',
        title: 'GroupBy : regroupement et agrégations',
        keywords: ['groupby', 'agrégation', 'moyenne par groupe', 'somme'],
        body: [
          { kind: 'p', text: "GroupBy regroupe les lignes par une ou plusieurs colonnes et calcule une ou plusieurs agrégations par groupe." },
          { kind: 'list', items: [
            'Fonctions disponibles : mean, sum, count, min, max, std, var, sem, median, quantile, first, last, nunique.',
            "Plusieurs agrégations peuvent porter sur des colonnes différentes dans le même GroupBy (ex : moyenne du Profit et somme du Revenu, groupés par Région).",
          ] },
          { kind: 'code', text: 'Regrouper par : Région, Produit\nAgrégations : Revenu → sum, Profit → mean' },
        ],
        related: ['dm-groupby-multi', 'up-example'],
      },
      {
        id: 'dm-groupby-multi',
        title: 'GroupBy multi-colonnes et tri',
        keywords: ['multi-colonnes', 'tri', 'limite'],
        body: [
          { kind: 'p', text: "Le résultat d'un GroupBy peut être trié par n'importe quelle colonne du tableau agrégé (croissant/décroissant) et limité à un nombre de lignes — utile pour un « top 10 des produits par profit », par exemple. Le résultat peut être ajouté directement à un rapport PDF." },
        ],
        related: ['dm-groupby-basics', 'exp-pdf-optional'],
      },
      {
        id: 'dm-pivot',
        title: 'Tableaux croisés dynamiques',
        keywords: ['pivot', 'tableau croisé', 'marges', 'pourcentage'],
        body: [
          { kind: 'p', text: "Un tableau croisé dynamique met une colonne en index (lignes), une autre en colonnes, et agrège une troisième valeur à l'intersection. Les marges (totaux de ligne/colonne) sont optionnelles, ainsi que l'affichage en pourcentage (du total général, de la ligne, ou de la colonne)." },
          { kind: 'note', text: "Attention à l'interprétation des pourcentages « % du total » quand les marges sont activées : DataVortex exclut bien les lignes/colonnes de marge du dénominateur pour que les pourcentages d'une ligne somment à 100%, pas à 50%." },
        ],
        related: ['dm-groupby-basics', 'exp-pdf-optional'],
      },
      {
        id: 'dm-export-tables',
        title: 'Exporter un tableau (GroupBy, Pivot, Stats)',
        keywords: ['export csv', 'export excel', 'latex'],
        body: [
          { kind: 'p', text: "Les tableaux GroupBy, Pivot et les tableaux de statistiques s'exportent en CSV, Excel ou LaTeX (pratique pour coller directement dans un article ou un rapport académique)." },
        ],
        related: ['exp-data-csv'],
      },
    ],
  },

  {
    id: 'ml',
    title: 'Machine Learning',
    topics: [
      {
        id: 'ml-regression',
        title: 'Régression : méthodes disponibles',
        keywords: ['régression', 'ridge', 'lasso', 'elastic net', 'svr', 'gpr', 'random forest'],
        body: [
          { kind: 'p', text: "Neuf méthodes de régression : linéaire, polynomiale, Ridge, Lasso, Elastic Net, SVR (support vector regression), processus gaussien (GPR), gradient boosting et forêt aléatoire." },
          { kind: 'list', items: [
            'Linéaire / polynomiale / Ridge / Lasso / Elastic Net — rapides, coefficients interprétables.',
            'SVR et GPR — capturent des relations non linéaires complexes, coûteux au-delà de ~15 000 (SVR) ou 5 000 (GPR) lignes.',
            'Gradient boosting et forêt aléatoire — robustes, fournissent une importance des variables.',
          ] },
        ],
        related: ['ml-regression-interpreting', 'ml-large-datasets'],
      },
      {
        id: 'ml-regression-interpreting',
        title: 'Interpréter un résultat de régression',
        keywords: ['r2', 'rmse', 'mae', 'résidus', 'coefficients', 'validation croisée'],
        body: [
          { kind: 'list', items: [
            'R² — proportion de variance expliquée (proche de 1 = bon ajustement, peut être négatif si le modèle est pire qu\'une prédiction constante).',
            'RMSE / MAE — erreur moyenne dans l\'unité de la variable cible ; MAE est moins sensible aux valeurs extrêmes.',
            'Résidus — leur nuage doit être sans motif visible ; un motif en entonnoir ou en courbe indique un modèle mal spécifié.',
            'Validation croisée — le R² est aussi calculé sur plusieurs découpages train/test pour vérifier que le modèle généralise, pas seulement qu\'il colle aux données d\'entraînement.',
          ] },
        ],
        related: ['ml-regression'],
      },
      {
        id: 'ml-classification',
        title: 'Classification : méthodes disponibles',
        keywords: ['classification', 'svm', 'knn', 'naive bayes', 'mlp', 'vote', 'stacking'],
        body: [
          { kind: 'p', text: "Dix méthodes : régression logistique, arbre de décision, forêt aléatoire, SVM, gradient boosting, k plus proches voisins (KNN), naïve bayésien, perceptron multicouche (MLP), vote (combine plusieurs modèles) et stacking (empile plusieurs modèles sous un méta-modèle)." },
          { kind: 'note', text: "La colonne cible est automatiquement exclue de la liste des variables explicatives proposées, pour éviter qu'un modèle « apprenne » en utilisant la réponse elle-même comme variable d'entrée (fuite de données)." },
        ],
        related: ['ml-classification-interpreting'],
      },
      {
        id: 'ml-classification-interpreting',
        title: 'Interpréter un résultat de classification',
        keywords: ['accuracy', 'précision', 'rappel', 'f1', 'matrice de confusion', 'roc', 'auc'],
        body: [
          { kind: 'list', items: [
            'Accuracy — proportion de prédictions correctes ; trompeuse si les classes sont déséquilibrées.',
            'Précision / rappel / F1 — précision = parmi les prédits positifs, combien le sont réellement ; rappel = parmi les vrais positifs, combien sont retrouvés ; F1 = leur moyenne harmonique.',
            'Matrice de confusion — détaille les erreurs par paire de classes.',
            'Courbe ROC / AUC — capacité du modèle à séparer les classes à tous les seuils de décision (0.5 = hasard, 1 = séparation parfaite).',
          ] },
        ],
        related: ['ml-classification'],
      },
      {
        id: 'ml-clustering',
        title: 'Clustering : méthodes disponibles',
        keywords: ['clustering', 'kmeans', 'dbscan', 'hiérarchique', 'gmm', 'mean shift'],
        body: [
          { kind: 'p', text: "Six méthodes : k-means, DBSCAN (densité, détecte le bruit), hiérarchique (avec dendrogramme), agglomératif, mélange de gaussiennes (GMM, clusters à formes elliptiques) et mean shift." },
        ],
        related: ['ml-clustering-interpreting', 'ml-large-datasets'],
      },
      {
        id: 'ml-clustering-interpreting',
        title: 'Choisir K et interpréter le clustering',
        keywords: ['silhouette', 'davies-bouldin', 'calinski-harabasz', 'coude', 'elbow'],
        body: [
          { kind: 'list', items: [
            "Méthode du coude — trace l'inertie en fonction de K ; le « coude » de la courbe suggère un K raisonnable pour k-means.",
            'Score de silhouette — proche de 1 : points bien assignés à leur cluster ; proche de 0 : clusters qui se chevauchent ; négatif : point probablement mal assigné.',
            'Davies-Bouldin — plus bas est meilleur (clusters compacts et bien séparés).',
            'Calinski-Harabasz — plus haut est meilleur.',
          ] },
          { kind: 'note', text: "Sur les gros jeux de données, le score de silhouette est calculé sur un échantillon plutôt que sur toutes les lignes (il est de complexité quadratique) — le résultat reste une estimation fiable, pas un artefact." },
        ],
        related: ['ml-clustering', 'ml-large-datasets'],
      },
      {
        id: 'ml-neural-networks',
        title: 'Construire un réseau de neurones',
        keywords: ['réseau de neurones', 'mlp', 'keras', 'tensorflow', 'couches', 'epochs'],
        body: [
          { kind: 'p', text: "L'onglet Réseau de neurones permet de composer un perceptron multicouche pour de la régression ou de la classification : nombre de couches, neurones par couche, fonction d'activation (ReLU, tanh, sigmoïde, linéaire) et dropout par couche." },
          { kind: 'list', items: [
            'Optimiseur : Adam, SGD ou RMSprop.',
            "Taux d'apprentissage, taille de batch, nombre d'époques, proportion de validation.",
            "L'entraînement est réel (TensorFlow/Keras côté serveur), pas simulé : les courbes de perte affichées reflètent l'entraînement effectif.",
          ] },
        ],
        related: ['ml-neural-networks-diagram'],
      },
      {
        id: 'ml-neural-networks-diagram',
        title: 'Visualiser et interpréter le réseau',
        keywords: ['diagramme', 'poids', 'architecture'],
        body: [
          { kind: 'p', text: "Après entraînement, un diagramme affiche l'architecture réellement entraînée : chaque connexion est tracée avec une épaisseur proportionnelle au poids appris, ce qui donne une intuition visuelle de quelles entrées pèsent le plus dans les prédictions." },
        ],
        related: ['ml-neural-networks'],
      },
      {
        id: 'ml-dimensionality',
        title: 'Réduction de dimension (PCA, t-SNE, UMAP)',
        keywords: ['pca', 'tsne', 'umap', 'composantes principales'],
        body: [
          { kind: 'p', text: "Pour visualiser un jeu de données à plusieurs variables en 2D ou 3D : PCA (linéaire, variance expliquée directement interprétable), t-SNE (préserve les voisinages locaux, utile pour repérer des groupes), UMAP (similaire à t-SNE, généralement plus rapide sur de gros volumes)." },
        ],
        related: ['ml-clustering'],
      },
      {
        id: 'ml-large-datasets',
        title: 'Limites sur les gros jeux de données',
        keywords: ['performance', '100k lignes', 'trop de lignes', 'too_many_samples'],
        body: [
          { kind: 'p', text: "Certaines méthodes ont une complexité qui explose avec le nombre de lignes (SVM/SVR, processus gaussien, clustering hiérarchique, mean shift). Au-delà d'un seuil de sécurité, DataVortex refuse l'exécution avec un message clair plutôt que de bloquer le navigateur pendant plusieurs minutes." },
          { kind: 'list', items: [
            'SVM / SVR : jusqu\'à 15 000 lignes.',
            'Processus gaussien (GPR) : jusqu\'à 5 000 lignes.',
            'Clustering hiérarchique : jusqu\'à 5 000 lignes.',
            'Mean shift : jusqu\'à 3 000 lignes.',
            'DBSCAN : jusqu\'à 30 000 lignes.',
          ] },
          { kind: 'note', text: "Si votre jeu dépasse ces seuils, filtrez au préalable, ou choisissez une méthode alternative sans cette limite (ex. k-means/GMM à la place du clustering hiérarchique, forêt aléatoire à la place du SVR)." },
        ],
        related: ['ml-regression', 'ml-clustering'],
      },
    ],
  },

  {
    id: 'stats-tests',
    title: 'Analyse statistique',
    topics: [
      {
        id: 'st-hypothesis',
        title: "Tests d'hypothèse",
        keywords: ['t-test', 'mann-whitney', 'wilcoxon', 'comparer deux groupes'],
        body: [
          { kind: 'p', text: "Comparer deux groupes ou une moyenne à une valeur de référence : test t pour échantillons indépendants (ttest_ind), appariés (ttest_rel), ou contre une constante (ttest_1samp) ; Mann-Whitney et Wilcoxon comme alternatives non paramétriques quand la normalité n'est pas vérifiée." },
        ],
        related: ['st-anova', 'st-goodness-of-fit'],
      },
      {
        id: 'st-anova',
        title: 'ANOVA',
        keywords: ['anova', 'un facteur', 'deux facteurs', 'tukey', 'bonferroni', 'post-hoc'],
        body: [
          { kind: 'p', text: "ANOVA à un facteur compare les moyennes de 3 groupes ou plus. ANOVA à deux facteurs (sommes de carrés de type II) teste aussi l'interaction entre deux variables catégorielles. Si l'ANOVA est significative, un test post-hoc (Tukey ou Bonferroni) identifie quelles paires de groupes diffèrent réellement." },
        ],
        related: ['st-hypothesis'],
      },
      {
        id: 'st-correlation-tests',
        title: 'Tests de corrélation',
        keywords: ['pearson', 'spearman', 'kendall', 'significativité'],
        body: [
          { kind: 'p', text: "Teste si une corrélation (Pearson, Spearman ou Kendall) entre deux colonnes est statistiquement significative, au-delà du simple coefficient affiché dans l'onglet Stats." },
        ],
        related: ['ex-stats-correlations'],
      },
      {
        id: 'st-goodness-of-fit',
        title: "Tests d'ajustement (goodness-of-fit)",
        keywords: ['shapiro', 'kolmogorov-smirnov', 'anderson-darling', 'chi2', 'normalité'],
        body: [
          { kind: 'p', text: "Shapiro-Wilk et Anderson-Darling testent si une colonne suit une loi normale. Kolmogorov-Smirnov compare à une loi théorique au choix (normale, exponentielle, uniforme, log-normale). Le test du Chi² d'indépendance teste l'association entre deux colonnes catégorielles." },
        ],
        related: ['ex-stats-distributions'],
      },
    ],
  },

  {
    id: 'export',
    title: 'Export & rapports',
    topics: [
      {
        id: 'exp-data-csv',
        title: 'Exporter les données',
        keywords: ['export csv', 'télécharger données'],
        body: [
          { kind: 'p', text: "L'onglet Export télécharge les données actuellement affichées (filtres et colonnes calculées appliqués) en CSV, avec séparateur et encoding configurables. Le filtre actif peut être documenté en commentaire en tête de fichier." },
        ],
        related: ['dm-export-tables'],
      },
      {
        id: 'exp-plots',
        title: 'Exporter les graphiques',
        keywords: ['export graphique', 'png', 'svg', 'html'],
        body: [
          { kind: 'p', text: "Voir Visualisation → Exporter un graphique : PNG/SVG pour un usage statique (rapport, présentation), HTML pour conserver l'interactivité." },
        ],
        related: ['viz-export'],
      },
      {
        id: 'exp-model',
        title: 'Exporter un modèle ML',
        keywords: ['export modèle', 'joblib', 'pickle', 'onnx', 'tflite'],
        body: [
          { kind: 'p', text: "Un modèle entraîné (régression, classification, clustering ou réseau de neurones) reste en mémoire côté session et peut être exporté sans le ré-entraîner." },
          { kind: 'list', items: [
            'joblib / pickle — format Python natif, à recharger avec scikit-learn.',
            'json — coefficients et métadonnées lisibles, pour les modèles linéaires.',
            'onnx — format portable, utilisable depuis d\'autres langages/runtimes (C++, Java, .NET…).',
            'tflite — modèle TensorFlow Lite, pour déploiement mobile/embarqué (réseaux de neurones uniquement).',
          ] },
        ],
        related: ['exp-model-repro', 'ml-neural-networks'],
      },
      {
        id: 'exp-model-repro',
        title: "Script d'entraînement et reproductibilité",
        keywords: ['reproductibilité', 'notebook', 'script'],
        body: [
          { kind: 'p', text: "En plus du modèle exporté, DataVortex peut générer les métadonnées d'entraînement (colonnes utilisées, hyperparamètres, métriques obtenues) et un notebook Python qui reproduit l'entraînement depuis zéro — utile pour documenter une analyse ou la rejouer avec de nouvelles données." },
        ],
        related: ['exp-model'],
      },
      {
        id: 'exp-pdf-defaults',
        title: 'Rapport PDF : sections toujours incluses',
        keywords: ['pdf', 'rapport', 'sections par défaut'],
        body: [
          { kind: 'p', text: "Un rapport PDF inclut toujours, sans avoir à les cocher : le résumé du jeu de données, les statistiques détaillées par colonne, les corrélations, le score de qualité et les suggestions d'amélioration. L'idée : un rapport minimal reste immédiatement utile, sans configuration." },
        ],
        related: ['exp-pdf-optional', 'ex-stats-summary'],
      },
      {
        id: 'exp-pdf-optional',
        title: 'Rapport PDF : sections optionnelles',
        keywords: ['pdf', 'rapport', 'sections optionnelles', 'graphiques dans le rapport'],
        body: [
          { kind: 'p', text: "Au-delà du contenu par défaut, un rapport peut inclure des sections plus coûteuses à générer, ajoutées explicitement : graphiques (depuis Visualisation), résultats GroupBy ou Pivot (bouton « Ajouter au rapport » dans ces onglets), résultats de modèles ML." },
          { kind: 'note', text: "Format A4 ou Letter, portrait ou paysage, et redimensionnement automatique des graphiques pour qu'ils tiennent sur la page." },
        ],
        related: ['exp-pdf-defaults', 'dm-groupby-multi', 'dm-pivot'],
      },
    ],
  },

  {
    id: 'workflows',
    title: 'Workflows avancés',
    topics: [
      {
        id: 'wf-multi-file',
        title: 'Travailler avec plusieurs fichiers',
        keywords: ['multi-fichier', 'onglets', 'fusion', 'merge', 'concat'],
        body: [
          { kind: 'p', text: "Plusieurs fichiers peuvent être ouverts en parallèle, chacun dans son propre onglet de haut niveau (indépendant des onglets d'analyse Stats/Visualisations/etc. à l'intérieur d'un fichier). Deux fichiers peuvent être combinés : concaténation (empiler les lignes) ou fusion façon SQL join sur une colonne clé commune." },
        ],
        related: ['up-formats'],
      },
      {
        id: 'wf-operation-stack',
        title: "Empiler les opérations",
        keywords: ['annuler', 'refaire', 'historique', 'undo redo'],
        body: [
          { kind: 'p', text: "Filtres, colonnes créées et transformations s'empilent sur la session sans jamais modifier le fichier importé. Ctrl+Z / Ctrl+Shift+Z permettent de revenir en arrière ou de rejouer une opération annulée." },
        ],
        related: ['dm-filters-simple', 'dm-columns-formulas'],
      },
      {
        id: 'wf-reproducibility',
        title: 'Reproductibilité : rapports et scripts',
        keywords: ['reproductible', 'partager', 'documenter'],
        body: [
          { kind: 'p', text: "Pour documenter une analyse de façon reproductible : un rapport PDF capture l'état des statistiques et graphiques à un instant donné ; un script d'entraînement exporté (voir Export & rapports) permet à quelqu'un d'autre de rejouer exactement un modèle ML avec les mêmes hyperparamètres." },
        ],
        related: ['exp-pdf-defaults', 'exp-model-repro'],
      },
    ],
  },

  {
    id: 'shortcuts',
    title: 'Raccourcis clavier',
    topics: [
      {
        id: 'shortcuts-reference',
        title: 'Référence complète',
        keywords: ['raccourcis', 'clavier', 'touches', 'liste complète'],
        dynamic: 'shortcuts',
        body: [
          { kind: 'p', text: "Tous les raccourcis actifs une fois un fichier chargé. La plupart sont désactivés pendant la saisie dans un champ de texte (sauf Ctrl+K et Échap, toujours actifs)." },
        ],
        related: ['gs-shortcuts'],
      },
    ],
  },

  {
    id: 'troubleshooting',
    title: 'Dépannage',
    topics: [
      {
        id: 'ts-common-issues',
        title: 'Problèmes courants',
        keywords: ['erreur', 'bug', 'ne fonctionne pas', 'graphique ne s\'affiche pas'],
        body: [
          { kind: 'list', items: [
            '« Port already in use » — un autre process occupe déjà le port : datavortex --port 9000.',
            'Un graphique ne s\'affiche pas — vérifiez que les colonnes choisies contiennent bien des valeurs numériques exploitables (pas 100% de valeurs manquantes ou une colonne constante).',
            'Un modèle ML refuse de s\'entraîner — le message d\'erreur indique la cause précise (colonne cible manquante dans les features, trop de lignes pour la méthode choisie, valeurs manquantes non gérées…).',
            'Mémoire insuffisante avec un très gros fichier — voir Gros fichiers et performance ci-dessous.',
          ] },
        ],
        related: ['ts-performance', 'ml-large-datasets'],
      },
      {
        id: 'ts-performance',
        title: 'Gros fichiers et performance',
        keywords: ['performance', 'lenteur', 'gros fichier', 'mémoire'],
        body: [
          { kind: 'list', items: [
            "Filtrez avant d'analyser : travailler sur un sous-ensemble pertinent est presque toujours plus rapide qu'analyser 100% des lignes.",
            "Exportez un résultat agrégé (GroupBy) plutôt que le jeu complet quand c'est suffisant pour votre usage.",
            'Pour le machine learning sur de très gros volumes, voir Limites sur les gros jeux de données (section Machine Learning).',
          ] },
        ],
        related: ['ml-large-datasets', 'dm-groupby-basics'],
      },
      {
        id: 'ts-browser',
        title: 'Compatibilité navigateur',
        keywords: ['navigateur', 'chrome', 'firefox', 'safari'],
        body: [
          { kind: 'p', text: "Navigateurs récents recommandés : Chrome/Edge (Chromium) 90+, Firefox, Safari. La boîte de dialogue native « Enregistrer sous » (exports) nécessite un navigateur basé sur Chromium récent ; sur les autres, DataVortex retombe automatiquement sur un téléchargement classique." },
        ],
        related: ['exp-data-csv'],
      },
      {
        id: 'ts-getting-help',
        title: 'Obtenir de l\'aide',
        keywords: ['aide', 'support', 'github issues', 'bug report'],
        body: [
          { kind: 'p', text: "Pour un bug ou une question : ouvrez une issue sur GitHub (github.com/nils-malmberg/datavortex/issues) avec le message d'erreur exact, le fichier concerné si possible (ou sa structure), et les étapes pour reproduire le problème." },
        ],
        related: ['about-faq'],
      },
    ],
  },

  {
    id: 'about',
    title: 'À propos',
    topics: [
      {
        id: 'about-datavortex',
        title: 'À propos de DataVortex',
        keywords: ['à propos', 'version', 'crédits'],
        body: [
          { kind: 'p', text: "DataVortex est une plateforme interactive de visualisation et d'analyse de données : upload, exploration statistique, visualisation, manipulation (filtres/formules/GroupBy/pivot), machine learning et génération de rapports PDF — le tout depuis un navigateur, sans envoyer vos données où que ce soit hors de votre machine." },
        ],
        related: ['about-license'],
      },
      {
        id: 'about-license',
        title: 'Licence',
        keywords: ['licence', 'mit', 'open source'],
        body: [
          { kind: 'p', text: "DataVortex est distribué sous licence MIT : usage, modification et redistribution libres, y compris à des fins commerciales, sans garantie. Voir le fichier LICENSE à la racine du dépôt." },
        ],
        related: ['about-datavortex'],
      },
      {
        id: 'about-faq',
        title: 'FAQ',
        keywords: ['faq', 'questions fréquentes'],
        body: [
          { kind: 'p', text: 'Quels formats sont supportés ? CSV, Excel (.xls/.xlsx) et JSON en entrée.' },
          { kind: 'p', text: 'Puis-je utiliser mes propres données ? Oui, tout reste local à votre machine — rien n\'est envoyé à un service externe.' },
          { kind: 'p', text: 'Comment exporter mon analyse ? Données en CSV, graphiques en PNG/SVG/HTML, tableaux GroupBy/Pivot/Stats en CSV/Excel/LaTeX, modèles ML en joblib/pickle/json/ONNX/TFLite, ou un rapport PDF complet.' },
          { kind: 'p', text: 'Est-ce que ça marche hors-ligne ? Oui : une fois installé, DataVortex tourne entièrement en local, aucune connexion Internet n\'est nécessaire pour l\'utiliser.' },
          { kind: 'p', text: 'Comment signaler un bug ? Voir Obtenir de l\'aide, dans la section Dépannage.' },
        ],
        related: ['ts-getting-help'],
      },
    ],
  },
]

/** Index plat de tous les topics, pour la recherche et la navigation par id. */
export const ALL_TOPICS = HELP_SECTIONS.flatMap((section) =>
  section.topics.map((topic) => ({ ...topic, sectionId: section.id, sectionTitle: section.title })),
)

export function findTopic(id) {
  return ALL_TOPICS.find((t) => t.id === id) || null
}
