# Phase 7 : Machine Learning Features

## Features ML

### Régression
- Linear regression : y ~ x1, x2, x3, ...
- Polynomial regression : degré configurable
- Affiche : équation, R², RMSE, graphique fit
- Route : POST /api/ml/regression

### Classification (si colonnes catégories)
- Logistic regression
- Decision tree (visualisation arbre)
- Random forest (feature importance)
- Route : POST /api/ml/classification

### Clustering
- K-Means (nombre clusters configurable, elbow method)
- DBSCAN (eps, min_samples)
- Affiche : scatter plot coloré par cluster
- Route : POST /api/ml/clustering

### Dimensionality Reduction
- PCA : 2D/3D
- t-SNE : 2D
- UMAP : 2D
- Affiche scatter plot résultat
- Route : POST /api/ml/pca

### UI - ML Panel
- MLAnalysis.jsx : onglet dans Dashboard
- Sélecteur: Regression / Classification / Clustering / PCA
- Input fields : colonnes, paramètres (dépend du type)
- Run button
- Résultats : équation, scores, graphiques
- Export résultats

### Backend Dependencies
- scikit-learn : ML models
- scipy : stats avancées
- matplotlib : plots (pour export)

### Tests
- Regression : iris sepal_length ~ petal_length
- Clustering K-means : iris, 3 clusters, voir espèces groupées
- PCA : iris 4D → 2D
- Classification : iris espèce ~ features