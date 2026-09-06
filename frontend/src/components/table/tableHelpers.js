/** Constantes et utilitaires partagés par le tableau de données. */

export const TYPE_ICONS = {
  integer: '#',
  float: '#',
  string: 'A',
  boolean: '⊤',
  datetime: '⏱',
}

export const TYPE_TITLES = {
  integer: 'Nombre entier',
  float: 'Nombre décimal',
  string: 'Texte',
  boolean: 'Booléen',
  datetime: 'Date / heure',
}

export const DENSITIES = [
  { value: 'compact', label: 'Compact', rowHeight: 26, padding: 'px-2 py-0.5' },
  { value: 'normal', label: 'Normal', rowHeight: 34, padding: 'px-3 py-1.5' },
  { value: 'spacious', label: 'Aéré', rowHeight: 46, padding: 'px-4 py-3' },
]

export const PAGE_SIZES = [10, 25, 50, 100, 500, 1000]

export function densityConfig(value) {
  return DENSITIES.find((d) => d.value === value) || DENSITIES[1]
}

export function isOutlier(value, bounds) {
  if (!bounds || typeof value !== 'number') return false
  return value < bounds[0] || value > bounds[1]
}

export function formatCellValue(value) {
  if (value === null || value === undefined) return null
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}
