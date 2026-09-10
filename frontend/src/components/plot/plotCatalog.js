/**
 * Catalogue des types de graphiques et de leurs champs.
 *
 * `fields` pilote l'affichage du panneau de données, `required` conditionne le
 * bouton de génération, et `numeric` liste les champs qui n'acceptent que des
 * colonnes numériques.
 */
export const PLOT_GROUPS = [
  {
    label: '1D — distribution',
    types: [
      { value: 'histogram', label: 'Histogramme', fields: ['y', 'group_by', 'bins'], required: ['y'], numeric: ['y'] },
      { value: 'kde', label: 'Densité (KDE)', fields: ['y', 'group_by'], required: ['y'], numeric: ['y'] },
      { value: 'box', label: 'Box plot', fields: ['y', 'group_by'], required: ['y'], numeric: ['y'] },
      { value: 'violin', label: 'Violin plot', fields: ['y', 'group_by'], required: ['y'], numeric: ['y'] },
      {
        value: 'violin_swarm',
        label: 'Violin + observations',
        fields: ['y', 'group_by'],
        required: ['y'],
        numeric: ['y'],
        isNew: true,
        hint: 'Densité et points individuels superposés : on voit la forme ET les observations réelles.',
      },
      {
        value: 'strip',
        label: 'Strip plot',
        fields: ['y', 'group_by'],
        required: ['y'],
        numeric: ['y'],
        isNew: true,
        hint: 'Nuage de points par catégorie, légèrement dispersé pour éviter les superpositions.',
      },
      {
        value: 'ridge',
        label: 'Ridge plot',
        fields: ['y', 'group_by'],
        required: ['y', 'group_by'],
        numeric: ['y'],
        isNew: true,
        hint: 'Une densité par groupe, décalées verticalement : idéal pour comparer des distributions.',
      },
      { value: 'bar', label: 'Bar chart (catégories)', fields: ['x'], required: ['x'] },
      { value: 'pie', label: 'Pie chart', fields: ['x'], required: ['x'] },
    ],
  },
  {
    label: '2D — relations',
    types: [
      {
        value: 'scatter',
        label: 'Scatter plot',
        fields: ['x', 'y', 'color_by', 'size_by'],
        required: ['x', 'y'],
        numeric: ['x', 'y'],
        trend: true,
      },
      { value: 'line', label: 'Line chart', fields: ['x', 'y', 'color_by'], required: ['x', 'y'], numeric: ['y'], trend: true },
      {
        value: 'bubble',
        label: 'Bubble chart',
        fields: ['x', 'y', 'size_by', 'color_by'],
        required: ['x', 'y', 'size_by'],
        numeric: ['x', 'y'],
        trend: true,
      },
      {
        value: 'bar_grouped',
        label: 'Bar chart groupé',
        fields: ['x', 'y', 'color_by'],
        required: ['x', 'y', 'color_by'],
      },
      { value: 'hexbin', label: 'Hexbin (densité 2D)', fields: ['x', 'y', 'bins'], required: ['x', 'y'], numeric: ['x', 'y'] },
      { value: 'heatmap', label: 'Heatmap (corrélations)', fields: ['columns'], required: [] },
      {
        value: 'joint',
        label: 'Joint plot',
        fields: ['x', 'y', 'bins'],
        required: ['x', 'y'],
        numeric: ['x', 'y'],
        isNew: true,
        trend: true,
        hint: 'Nuage de points central entouré des distributions marginales de X et Y.',
      },
      {
        value: 'pair',
        label: 'Pair plot',
        fields: ['columns', 'color_by'],
        required: [],
        isNew: true,
        hint: 'Matrice de nuages de points : toutes les paires de variables numériques d’un coup.',
      },
    ],
  },
  {
    label: '3D',
    types: [
      {
        value: 'scatter3d',
        label: 'Scatter 3D',
        fields: ['x', 'y', 'z', 'color_by'],
        required: ['x', 'y', 'z'],
        numeric: ['x', 'y', 'z'],
      },
      { value: 'surface', label: 'Surface', fields: ['x', 'y', 'z'], required: ['x', 'y', 'z'], numeric: ['x', 'y', 'z'] },
    ],
  },
]

export const ALL_PLOT_TYPES = PLOT_GROUPS.flatMap((g) => g.types)

export function plotConfig(value) {
  return ALL_PLOT_TYPES.find((t) => t.value === value) || ALL_PLOT_TYPES[0]
}

export const FIELD_LABELS = {
  x: 'Axe X',
  y: 'Axe Y',
  z: 'Axe Z',
  color_by: 'Couleur par',
  size_by: 'Taille par',
  group_by: 'Grouper par',
  columns: 'Colonnes incluses',
  bins: 'Nombre de bins',
}

export const PALETTES = ['Default', 'Viridis', 'Plasma', 'Inferno', 'Cividis', 'Twilight', 'Okabe-Ito', 'Tol Bright']

export const COLORBLIND_MODES = [
  { value: 'none', label: 'Aucune adaptation' },
  { value: 'safe', label: 'Palette sûre (Okabe-Ito)' },
  { value: 'deuteranopia', label: 'Simuler : deutéranopie' },
  { value: 'protanopia', label: 'Simuler : protanopie' },
  { value: 'tritanopia', label: 'Simuler : tritanopie' },
  { value: 'grayscale', label: 'Simuler : niveaux de gris' },
]

export const LEGEND_POSITIONS = [
  { value: 'top-right', label: 'Haut droite' },
  { value: 'top-left', label: 'Haut gauche' },
  { value: 'bottom-right', label: 'Bas droite' },
  { value: 'bottom-left', label: 'Bas gauche' },
  { value: 'top', label: 'Au-dessus' },
  { value: 'bottom', label: 'En dessous' },
  { value: 'none', label: 'Masquée' },
]

// Modes de disposition de l'atelier (Phase 10.1). Ils vivent dans le même
// `spec` que le reste de la configuration : l'historique, les presets et le
// partage de configuration fonctionnent ainsi dans les trois modes sans
// traitement particulier.
export const LAYOUT_MODES = [
  { value: 'single', label: '📊 Graphique simple', hint: 'Un seul graphique, tous les types et toutes les options.' },
  { value: 'multi_series', label: '📈 Multi-séries', hint: 'Plusieurs colonnes Y sur le même axe X, avec axe Y secondaire optionnel.' },
  { value: 'subplots', label: '🔲 Grille', hint: 'Plusieurs graphiques indépendants disposés en grille.' },
]

export const SERIES_PLOT_TYPES = [
  { value: 'scatter', label: 'Nuage de points' },
  { value: 'line', label: 'Ligne' },
  { value: 'bar', label: 'Barres' },
  { value: 'area', label: 'Aire' },
]

export const SUBPLOT_TYPES = [
  ...SERIES_PLOT_TYPES,
  { value: 'histogram', label: 'Histogramme' },
  { value: 'box', label: 'Box plot' },
  { value: 'violin', label: 'Violin plot' },
]

// Types ne portant qu'une variable : l'éditeur n'y demande pas de colonne X.
export const SINGLE_VARIABLE_TYPES = ['histogram', 'box', 'violin']

export const GRID_PRESETS = [
  { rows: 1, cols: 2 },
  { rows: 2, cols: 2 },
  { rows: 2, cols: 3 },
  { rows: 3, cols: 3 },
  { rows: 4, cols: 2 },
]

export const MAX_SERIES = 10
export const MAX_GRID_SIDE = 4

export const DEFAULT_SPEC = {
  layout_mode: 'single',
  series: [],
  subplot_grid: { rows: 2, cols: 2 },
  subplots: [],
  plot_type: 'scatter',
  x: '',
  y: '',
  z: '',
  color_by: '',
  size_by: '',
  group_by: '',
  columns: [],
  bins: 30,
  trend: { type: 'none', degree: 2, frac: 0.35, confidence: 'none', show_equation: true },
  overlays: { mean: false, median: false, std: false, std_sigmas: 2, percentiles: [] },
  style: {
    title: '',
    subtitle: '',
    x_label: '',
    y_label: '',
    palette: 'Default',
    colorblind_mode: 'none',
    grid: true,
    legend_position: 'top-right',
    x_scale: 'linear',
    y_scale: 'linear',
    theme: 'auto',
    width: 900,
    height: 600,
    dpi: 100,
    annotations: [],
  },
}

/** Retire les champs vides pour n'envoyer au backend que ce qui est renseigné. */
export function buildPayload(spec) {
  const config = plotConfig(spec.plot_type)
  const payload = { plot_type: spec.plot_type, trend: spec.trend, overlays: spec.overlays, style: spec.style }
  for (const field of config.fields) {
    const value = spec[field]
    const isEmpty = value === '' || value === undefined || value === null || (Array.isArray(value) && value.length === 0)
    if (!isEmpty) payload[field] = value
  }
  // Une tendance n'a de sens que sur les types qui la supportent.
  if (!config.trend) payload.trend = { ...spec.trend, type: 'none' }
  return payload
}

/** Charge utile du mode multi-séries : mêmes options avancées que le mode simple. */
export function buildMultiSeriesPayload(spec) {
  return {
    title: spec.style?.title || undefined,
    x_axis: spec.x,
    series: (spec.series || []).map((s) => ({
      y_column: s.y_column,
      y_axis: s.y_axis,
      plot_type: s.plot_type,
      name: s.name || undefined,
      color: s.color || undefined,
    })),
    trend: spec.trend,
    style: spec.style,
  }
}

/** Charge utile du mode grille : une configuration par case. */
export function buildSubplotsPayload(spec) {
  const { rows, cols } = spec.subplot_grid
  return {
    title: spec.style?.title || undefined,
    rows,
    cols,
    subplots: (spec.subplots || []).slice(0, rows * cols).map((s) => ({
      plot_type: s.plot_type,
      x: SINGLE_VARIABLE_TYPES.includes(s.plot_type) ? undefined : s.x || undefined,
      y: s.y || undefined,
      title: s.title || undefined,
      color: s.color || undefined,
    })),
    style: spec.style,
  }
}

function isSubplotComplete(subplot) {
  if (!subplot.y) return false
  return SINGLE_VARIABLE_TYPES.includes(subplot.plot_type) ? true : Boolean(subplot.x)
}

export function isSpecComplete(spec) {
  if (spec.layout_mode === 'multi_series') {
    return Boolean(spec.x) && (spec.series || []).length > 0 && spec.series.every((s) => s.y_column)
  }
  if (spec.layout_mode === 'subplots') {
    const { rows, cols } = spec.subplot_grid
    const active = (spec.subplots || []).slice(0, rows * cols)
    return active.length > 0 && active.every(isSubplotComplete)
  }
  return plotConfig(spec.plot_type).required.every((field) => {
    const value = spec[field]
    return !(value === '' || value === undefined || value === null || (Array.isArray(value) && value.length === 0))
  })
}

export function describeSpec(spec) {
  if (spec.layout_mode === 'multi_series') {
    const names = (spec.series || []).map((s) => s.name || s.y_column).filter(Boolean)
    return `Multi-séries — ${names.join(', ') || '…'} vs ${spec.x || '…'}`
  }
  if (spec.layout_mode === 'subplots') {
    const { rows, cols } = spec.subplot_grid
    return `Grille ${rows}x${cols}`
  }
  const label = plotConfig(spec.plot_type).label
  if (spec.y && spec.x) return `${label} — ${spec.y} vs ${spec.x}`
  if (spec.y) return `${label} — ${spec.y}`
  if (spec.x) return `${label} — ${spec.x}`
  return label
}
