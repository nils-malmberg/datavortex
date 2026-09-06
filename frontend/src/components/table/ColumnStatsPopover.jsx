import { useEffect, useState } from 'react'
import { getColumnStats } from '../../api/client'
import { Badge, ErrorBox, StatRow, formatNumber } from '../ui/common'

/** Fiche statistique d'une colonne, ouverte depuis le menu contextuel du tableau. */
export default function ColumnStatsPopover({ sessionId, column, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getColumnStats(sessionId, column)
      .then(({ data: payload }) => !cancelled && setData(payload))
      .catch((err) =>
        !cancelled && setError(err?.response?.data?.error?.message || 'Statistiques indisponibles.'),
      )
    return () => {
      cancelled = true
    }
  }, [sessionId, column])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-4 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h4 className="truncate font-semibold text-slate-800 dark:text-slate-100">{column}</h4>
          {data && <Badge tone="blue">{data.type}</Badge>}
          <button onClick={onClose} className="rounded px-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-100">
            ✕
          </button>
        </div>
        {error && <ErrorBox>{error}</ErrorBox>}
        {!data && !error && <p className="text-sm text-slate-500 dark:text-slate-400">Calcul…</p>}
        {data && (
          <dl className="text-sm">
            {Object.entries(data.stats).map(([key, value]) =>
              Array.isArray(value) ? null : (
                <StatRow key={key} label={key} value={formatNumber(value, 4)} />
              ),
            )}
            <StatRow label="Manquantes" value={`${data.missing_count} (${data.missing_pct} %)`} />
            <StatRow label="Doublons" value={data.duplicated_count} />
          </dl>
        )}
      </div>
    </div>
  )
}
