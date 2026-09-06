/** Catalogue des opérateurs de filtre, par famille de type de colonne. */

export const NUMERIC_TYPES = ['integer', 'float']

const COMMON_NULL_OPS = [
  { value: 'is_null', label: 'est vide' },
  { value: 'is_not_null', label: "n'est pas vide" },
]

export const OPERATORS_BY_CATEGORY = {
  numeric: [
    { value: 'eq', label: '=' },
    { value: 'ne', label: '≠' },
    { value: 'gt', label: '>' },
    { value: 'lt', label: '<' },
    { value: 'gte', label: '≥' },
    { value: 'lte', label: '≤' },
    { value: 'between', label: 'entre' },
    { value: 'in', label: 'dans la liste' },
    { value: 'not_in', label: 'hors de la liste' },
    ...COMMON_NULL_OPS,
    { value: 'top_n', label: 'N plus grandes', hint: 'Conserve les N lignes aux plus grandes valeurs.' },
    { value: 'bottom_n', label: 'N plus petites', hint: 'Conserve les N lignes aux plus petites valeurs.' },
    {
      value: 'outlier_iqr',
      label: 'valeurs aberrantes (IQR)',
      hint: 'Règle de Tukey : hors de [Q1 − 1,5·IQR ; Q3 + 1,5·IQR].',
    },
    { value: 'not_outlier_iqr', label: 'sans les aberrantes (IQR)', hint: 'Le complément de la règle de Tukey.' },
    {
      value: 'outlier_zscore',
      label: 'valeurs aberrantes (z-score)',
      hint: 'Écart à la moyenne, en nombre d’écarts-types. Seuil usuel : 3.',
    },
    { value: 'not_outlier_zscore', label: 'sans les aberrantes (z-score)' },
  ],
  string: [
    { value: 'eq', label: 'égal à' },
    { value: 'ne', label: 'différent de' },
    { value: 'contains', label: 'contient' },
    { value: 'starts_with', label: 'commence par' },
    { value: 'ends_with', label: 'finit par' },
    { value: 'regex', label: 'expression régulière', hint: 'Syntaxe Python (re). Exemple : ^item_0\\d+$' },
    { value: 'in', label: 'dans la liste' },
    { value: 'not_in', label: 'hors de la liste' },
    ...COMMON_NULL_OPS,
  ],
  boolean: [
    { value: 'is_true', label: 'est vrai' },
    { value: 'is_false', label: 'est faux' },
    ...COMMON_NULL_OPS,
  ],
  datetime: [
    { value: 'eq', label: '=' },
    { value: 'gt', label: 'après' },
    { value: 'lt', label: 'avant' },
    { value: 'between', label: 'entre' },
    { value: 'year', label: 'année =' },
    { value: 'month', label: 'mois =' },
    { value: 'day', label: 'jour =' },
    ...COMMON_NULL_OPS,
  ],
}

export const NO_VALUE_OPS = new Set([
  'is_null', 'is_not_null', 'is_true', 'is_false', 'outlier_iqr', 'not_outlier_iqr',
])
export const RANGE_OPS = new Set(['between'])
export const LIST_OPS = new Set(['in', 'not_in'])
export const COUNT_OPS = new Set(['top_n', 'bottom_n'])
export const THRESHOLD_OPS = new Set(['outlier_zscore', 'not_outlier_zscore'])

export function categoryFor(colType) {
  if (NUMERIC_TYPES.includes(colType)) return 'numeric'
  if (colType === 'boolean') return 'boolean'
  if (colType === 'datetime') return 'datetime'
  return 'string'
}

export function operatorsFor(colType) {
  return OPERATORS_BY_CATEGORY[categoryFor(colType)] || OPERATORS_BY_CATEGORY.string
}

let nextId = 1
export function newCondition(column) {
  return { id: nextId++, type: 'condition', column, operator: 'eq', value: '' }
}

export function newGroup(column) {
  return { id: nextId++, type: 'group', logic: 'AND', conditions: [newCondition(column)] }
}

/** Réhydrate un arbre chargé depuis le stockage en lui redonnant des ids uniques. */
export function reassignIds(node) {
  if (!node) return null
  if (node.type === 'group') {
    return { ...node, id: nextId++, conditions: (node.conditions || []).map(reassignIds).filter(Boolean) }
  }
  return { ...node, id: nextId++ }
}

function isConditionComplete(condition) {
  const { operator, value } = condition
  if (NO_VALUE_OPS.has(operator)) return true
  if (RANGE_OPS.has(operator)) {
    const [lo, hi] = Array.isArray(value) ? value : []
    return lo !== undefined && lo !== '' && hi !== undefined && hi !== ''
  }
  if (LIST_OPS.has(operator)) return String(value ?? '').trim() !== ''
  if (THRESHOLD_OPS.has(operator)) return true // seuil par défaut côté serveur
  return value !== '' && value !== undefined && value !== null
}

/** Convertit l'arbre de l'interface en charge utile acceptée par l'API. */
export function buildFilterPayload(node, columnTypes) {
  if (!node) return null

  if (node.type === 'group') {
    const children = (node.conditions || [])
      .map((child) => buildFilterPayload(child, columnTypes))
      .filter(Boolean)
    if (children.length === 0) return null
    if (children.length === 1) return children[0]
    return { type: 'group', logic: node.logic, conditions: children }
  }

  if (!node.column || !isConditionComplete(node)) return null

  const category = categoryFor(columnTypes[node.column])
  const { operator } = node
  let value = node.value

  if (NO_VALUE_OPS.has(operator)) {
    value = null
  } else if (COUNT_OPS.has(operator)) {
    value = Number(value) || 1
  } else if (THRESHOLD_OPS.has(operator)) {
    value = value === '' || value === undefined ? 3 : Number(value)
  } else if (LIST_OPS.has(operator)) {
    const items = String(value ?? '').split(',').map((v) => v.trim()).filter(Boolean)
    value = category === 'numeric' ? items.map(Number) : items
  } else if (RANGE_OPS.has(operator)) {
    const [lo, hi] = Array.isArray(value) ? value : ['', '']
    value = category === 'numeric' ? [Number(lo), Number(hi)] : [lo, hi]
  } else if (category === 'numeric') {
    value = value === '' ? null : Number(value)
  }

  // L'id remonte inchangé dans les indicateurs : il relie chaque mesure à sa ligne.
  return { type: 'condition', id: String(node.id), column: node.column, operator, value }
}

export function countConditions(node) {
  if (!node) return 0
  if (node.type === 'condition') return 1
  return (node.conditions || []).reduce((total, child) => total + countConditions(child), 0)
}

export function describeFilter(node, depth = 0) {
  if (!node) return 'aucun filtre'
  if (node.type === 'condition') {
    const value = Array.isArray(node.value) ? node.value.join(' / ') : node.value
    return `${node.column} ${node.operator}${value !== '' && value != null ? ` ${value}` : ''}`
  }
  const joiner = node.logic === 'AND' ? ' ET ' : ' OU '
  const inner = (node.conditions || []).map((c) => describeFilter(c, depth + 1)).join(joiner)
  return depth > 0 ? `(${inner})` : inner
}
