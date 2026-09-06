/** Catalogue des tests statistiques, par famille, avec les champs requis. */

export const FAMILIES = [
  { value: 'hypothesis', label: 'Comparaison de groupes' },
  { value: 'anova', label: 'ANOVA' },
  { value: 'correlation', label: 'Corrélation' },
  { value: 'goodness_of_fit', label: 'Ajustement' },
]

export const TESTS = {
  hypothesis: [
    {
      value: 'ttest_ind',
      label: 'Test t (deux groupes indépendants)',
      fields: ['column', 'group_column', 'group_a', 'group_b', 'alternative', 'equal_variance'],
      hint: "Compare les moyennes de deux groupes. Par défaut en version de Welch, qui ne suppose pas l'égalité des variances.",
    },
    {
      value: 'mannwhitney',
      label: 'Mann-Whitney (deux groupes)',
      fields: ['column', 'group_column', 'group_a', 'group_b', 'alternative'],
      hint: "Alternative au test t qui ne suppose aucune forme de distribution : compare les rangs plutôt que les moyennes.",
    },
    {
      value: 'ttest_rel',
      label: 'Test t apparié (deux colonnes)',
      fields: ['column', 'column_b', 'alternative'],
      hint: 'Pour deux mesures faites sur les mêmes individus (avant / après, gauche / droite).',
    },
    {
      value: 'wilcoxon',
      label: 'Wilcoxon apparié (deux colonnes)',
      fields: ['column', 'column_b', 'alternative'],
      hint: 'Version non paramétrique du test t apparié.',
    },
    {
      value: 'ttest_1samp',
      label: 'Test t sur un échantillon',
      fields: ['column', 'popmean', 'alternative'],
      hint: 'Compare la moyenne observée à une valeur de référence connue.',
    },
  ],
  anova: [
    {
      value: 'one_way',
      label: 'ANOVA à un facteur',
      fields: ['column', 'factor_a', 'post_hoc'],
      hint: 'Compare les moyennes de plusieurs groupes simultanément, sans multiplier les tests deux à deux.',
    },
    {
      value: 'two_way',
      label: 'ANOVA à deux facteurs',
      fields: ['column', 'factor_a', 'factor_b'],
      hint: "Étudie deux facteurs et leur interaction : l'effet de l'un dépend-il du niveau de l'autre ?",
    },
  ],
  correlation: [
    { value: 'pearson', label: 'Pearson (linéaire)', fields: ['column', 'column_b'], hint: 'Mesure une relation linéaire. Sensible aux valeurs extrêmes.' },
    { value: 'spearman', label: 'Spearman (monotone)', fields: ['column', 'column_b'], hint: 'Travaille sur les rangs : détecte toute relation monotone, même non linéaire.' },
    { value: 'kendall', label: 'Kendall (tau)', fields: ['column', 'column_b'], hint: 'Fondé sur les paires concordantes. Plus robuste sur petits échantillons.' },
  ],
  goodness_of_fit: [
    { value: 'shapiro', label: 'Shapiro-Wilk (normalité)', fields: ['column'], hint: 'Test de référence pour la normalité.' },
    { value: 'ks', label: 'Kolmogorov-Smirnov', fields: ['column', 'distribution'], hint: "Compare la distribution observée à une loi théorique ajustée." },
    { value: 'anderson', label: 'Anderson-Darling', fields: ['column', 'distribution'], hint: 'Plus sensible que Shapiro dans les queues de distribution.' },
    { value: 'chi2', label: "Khi² d'indépendance", fields: ['column', 'column_b'], hint: 'Teste si deux variables catégorielles sont liées.' },
  ],
}

export const ALTERNATIVES = [
  { value: 'two-sided', label: 'Bilatéral (différent)' },
  { value: 'less', label: 'Unilatéral (inférieur)' },
  { value: 'greater', label: 'Unilatéral (supérieur)' },
]

export const POST_HOC = [
  { value: 'tukey', label: 'Tukey HSD' },
  { value: 'bonferroni', label: 'Bonferroni' },
  { value: 'none', label: 'Aucun' },
]

export const DISTRIBUTIONS = [
  { value: 'norm', label: 'Normale' },
  { value: 'expon', label: 'Exponentielle' },
  { value: 'uniform', label: 'Uniforme' },
  { value: 'lognorm', label: 'Log-normale' },
]

export function testConfig(family, test) {
  return TESTS[family].find((t) => t.value === test) || TESTS[family][0]
}
