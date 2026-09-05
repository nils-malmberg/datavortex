import { useEffect, useState } from 'react'
import { getPreview } from '../api/client'

function formatCell(value) {
  if (value === null || value === undefined) {
    return <span className="italic text-slate-400">null</span>
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }
  return String(value)
}

export default function DataPreview({ sessionId, refreshKey }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getPreview(sessionId)
      .then(({ data }) => {
        if (!cancelled) setPreview(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err?.response?.data?.error?.message ||
              "Impossible de charger l'aperçu des données.",
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId, refreshKey])

  if (loading) {
    return <p className="p-4 text-sm text-slate-500">Chargement de l&apos;aperçu…</p>
  }
  if (error) {
    return <p className="rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</p>
  }
  if (!preview) return null

  const {
    columns,
    column_types: columnTypes,
    rows,
    total_rows: totalRows,
    shown_rows: shownRows,
    filtered,
    total_rows_unfiltered: totalRowsUnfiltered,
  } = preview

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold text-slate-800">
          Aperçu des données
          {filtered && (
            <span className="ml-2 rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
              filtré : {totalRows}/{totalRowsUnfiltered}
            </span>
          )}
        </h3>
        <p className="text-sm text-slate-500">
          Affichage de {shownRows} ligne(s) sur {totalRows} au total
        </p>
      </div>
      <div className="max-h-[420px] overflow-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="sticky top-0 bg-slate-100">
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  className="whitespace-nowrap px-3 py-2 text-left font-semibold text-slate-700"
                >
                  {col}
                  <span className="ml-1.5 rounded bg-slate-200 px-1.5 py-0.5 text-xs font-normal text-slate-500">
                    {columnTypes?.[col]}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {rows.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50">
                {columns.map((col) => (
                  <td key={col} className="whitespace-nowrap px-3 py-1.5 text-slate-700">
                    {formatCell(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
