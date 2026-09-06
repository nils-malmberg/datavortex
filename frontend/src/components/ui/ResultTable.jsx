import { formatNumber } from './common'

/**
 * Tableau de résultats compact et triable, partagé par les panneaux d'analyse
 * (groupby, pivot, profiling…). Les colonnes numériques sont alignées à droite
 * et arrondies à la précision demandée.
 */
export default function ResultTable({
  columns,
  rows,
  highlightColumns = [],
  precision = 4,
  sortBy,
  sortAscending,
  onSort,
  maxHeight = '420px',
  emptyMessage = 'Aucun résultat.',
}) {
  if (!rows || rows.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
        {emptyMessage}
      </p>
    )
  }

  return (
    <div className="overflow-auto rounded-lg border border-slate-200 dark:border-slate-800" style={{ maxHeight }}>
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800">
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                onClick={() => onSort?.(col)}
                className={`whitespace-nowrap px-3 py-2 text-left font-semibold ${
                  onSort ? 'cursor-pointer select-none hover:text-blue-700 dark:hover:text-blue-300' : ''
                } ${
                  highlightColumns.includes(col)
                    ? 'text-blue-700 dark:text-blue-300'
                    : 'text-slate-700 dark:text-slate-200'
                }`}
                title={onSort ? 'Cliquer pour trier' : undefined}
              >
                {col}
                {sortBy === col && <span className="ml-1">{sortAscending ? '▲' : '▼'}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
              {columns.map((col) => {
                const value = row[col]
                const numeric = typeof value === 'number'
                return (
                  <td
                    key={col}
                    className={`whitespace-nowrap px-3 py-1.5 ${
                      numeric ? 'text-right tabular-nums' : ''
                    } ${
                      value === null || value === undefined
                        ? 'italic text-slate-400 dark:text-slate-500'
                        : 'text-slate-700 dark:text-slate-200'
                    }`}
                  >
                    {value === null || value === undefined ? '—' : numeric ? formatNumber(value, precision) : String(value)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
