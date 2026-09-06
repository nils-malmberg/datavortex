# Guide d'utilisation

Tutoriels pas à pas, du premier import à un workflow d'analyse complet. Les exemples utilisent le jeu de données fourni [`examples/ventes_demo.csv`](examples/ventes_demo.csv) : 400 lignes de ventes fictives avec les colonnes `Date`, `Region`, `Produit`, `Unites`, `Prix_Unitaire`, `Revenu`, `Cout`, `Profit`.

Pour une référence exhaustive de chaque fonctionnalité, utilisez l'aide intégrée (F1 dans l'application) — ce guide se concentre sur des parcours concrets, pas sur l'exhaustivité.

## Sommaire

- [Niveau débutant : première analyse (5 minutes)](#niveau-débutant--première-analyse-5-minutes)
- [Niveau intermédiaire : GroupBy, formules, filtres (15 minutes)](#niveau-intermédiaire--groupby-formules-filtres-15-minutes)
- [Niveau avancé : Machine Learning (10 minutes)](#niveau-avancé--machine-learning-10-minutes)
- [Bonnes pratiques](#bonnes-pratiques)
- [Conseils de performance](#conseils-de-performance)
- [Schémas d'usage courants](#schémas-dusage-courants)

---

## Niveau débutant : première analyse (5 minutes)

1. Lancez `datavortex` et importez `examples/ventes_demo.csv` (glisser-déposer sur la zone d'upload).
2. Le séparateur virgule et l'encoding sont détectés automatiquement — cliquez directement sur **Valider et parser**.
3. Dans l'onglet **Stats**, observez la moyenne et la médiane de `Profit` : si elles sont proches, la distribution est plutôt symétrique.
4. Dans l'onglet **Visualisations**, créez un nuage de points (`scatter`) : X = `Unites`, Y = `Revenu`, couleur = `Region`. La relation quasi-linéaire attendue (plus d'unités vendues → plus de revenu) doit apparaître, avec des pentes différentes selon la région (prix unitaires différents par produit dominant).
5. Exportez ce graphique en PNG depuis le bouton d'export sous le graphique.

## Niveau intermédiaire : GroupBy, formules, filtres (15 minutes)

**Objectif** : identifier les combinaisons Région × Produit les plus rentables, et isoler celles qui méritent une attention particulière.

1. Onglet **Colonnes**, créez une colonne calculée :
   ```
   Nom : Marge
   Formule : ({Revenu} - {Cout}) / {Revenu} * 100
   ```
   Prévisualisez avant de valider — la marge doit se situer entre 15% et 45% environ sur ce jeu de données.

2. Onglet **GroupBy** :
   - Regrouper par : `Region`, `Produit`
   - Agrégations : `Revenu` → `sum`, `Profit` → `mean`, `Marge` → `mean`
   - Trier par `Revenu_sum` décroissant

   Le tableau obtenu classe chaque combinaison Région/Produit par chiffre d'affaires total, avec sa marge moyenne à côté — les lignes à fort revenu mais faible marge sautent immédiatement aux yeux.

3. Onglet **Filtres** : ajoutez une condition `Marge` `inférieur à` `20`, pour isoler les ventes à surveiller. Le nombre de lignes concernées s'affiche en temps réel dans l'aperçu.

4. Onglet **Pivot** : Index = `Region`, Colonnes = `Produit`, Valeurs = `Revenu`, agrégation `sum`, avec marges activées et pourcentage « du total » — pour voir en un coup d'œil quelle région pèse le plus dans le chiffre d'affaires global.

5. Depuis l'onglet GroupBy (ou Pivot), cliquez **+ Ajouter au rapport** pour inclure ce tableau dans un futur rapport PDF sans avoir à le reconstruire.

## Niveau avancé : Machine Learning (10 minutes)

**Objectif** : prédire le `Profit` d'une vente à partir de `Unites`, `Prix_Unitaire` et `Region`.

1. Onglet **Colonnes** → transformer `Region` par **encodage** (one-hot) : les méthodes ML ont besoin de variables numériques.
2. Onglet **Machine Learning** → **Régression** :
   - Variables (features) : `Unites`, `Prix_Unitaire`, et les colonnes encodées de `Region`
   - Cible (target) : `Profit`
   - Méthode : commencez par **Forêt aléatoire** (robuste par défaut, donne une importance des variables directement interprétable)
3. Lisez les résultats : R² (proportion de variance expliquée), RMSE (erreur moyenne en unité de `Profit`), et le graphique d'importance des variables — `Prix_Unitaire` et `Unites` devraient dominer sur ce jeu synthétique.
4. Essayez **Gradient Boosting** ou **Ridge** sur le même jeu pour comparer le R² obtenu — voir l'aide intégrée (Machine Learning → Interpréter un résultat de régression) pour ce que chaque métrique signifie exactement.
5. Une fois satisfait, exportez le modèle (bouton d'export du modèle) au format **joblib** pour le recharger plus tard avec scikit-learn, ou générez le **script d'entraînement** pour documenter exactement comment le modèle a été obtenu.

---

## Bonnes pratiques

- **Filtrez avant d'agréger** : un GroupBy sur des données déjà filtrées est plus rapide à lire et évite les pièges d'interprétation (moyennes tirées par des lignes hors sujet).
- **Vérifiez le type de colonne détecté** avant une analyse statistique — l'onglet Colonnes affiche le type déduit ; une colonne numérique importée comme texte (à cause d'une virgule décimale non standard, par exemple) fausserait silencieusement les stats.
- **Prévisualisez toujours une formule** avant de valider une colonne calculée — l'aperçu tourne sur un échantillon, sans risque d'écraser une colonne existante par erreur.
- **Un rapport PDF minimal reste utile** : les sections par défaut (stats, corrélations, qualité, suggestions) suffisent souvent ; n'ajoutez des graphiques/modèles en sections optionnelles que si le destinataire du rapport en a besoin.
- **Sur un modèle ML, comparez toujours au moins deux méthodes** avant de conclure — un R² élevé sur une seule méthode ne dit rien sur si une autre approche ferait mieux ou pire.

## Conseils de performance

- Les opérations (filtres, formules, GroupBy) restent rapides jusqu'à plusieurs centaines de milliers de lignes.
- Pour le machine learning sur de très gros volumes, certaines méthodes ont des limites de sécurité explicites (SVM/SVR, processus gaussien, clustering hiérarchique, mean shift) — voir l'aide intégrée → Machine Learning → *Limites sur les gros jeux de données*. Au-delà du seuil, préférez une méthode sans cette limite (forêt aléatoire, k-means/GMM) ou filtrez d'abord.
- Exportez un résultat agrégé (GroupBy/Pivot) plutôt que le jeu de données complet quand l'usage final ne nécessite pas le détail ligne par ligne.

## Schémas d'usage courants

**Nettoyage rapide avant analyse** : Profil (repérer les colonnes à problème) → Colonnes (binning/encodage sur les colonnes signalées) → Filtres (exclure les lignes clairement aberrantes) → Stats (revérifier que les chiffres sont maintenant cohérents).

**Rapport pour un tiers non technique** : GroupBy/Pivot sur les questions métier posées → bouton « Ajouter au rapport » sur chacun → générateur de rapport PDF, sections par défaut + les tableaux ajoutés, rien de plus.

**Comparaison de plusieurs fichiers** : ouvrez chaque fichier dans son propre onglet (haut de l'écran) ; pour les combiner, utilisez la fusion multi-fichiers (concaténation si même structure, jointure sur colonne clé sinon) avant de poursuivre l'analyse sur le résultat combiné.
