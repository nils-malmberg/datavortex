import { useEffect, useState } from 'react'
import { getStats } from '../api/client'

function formatNumber(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value !== 'number') return String(value)
  return Number.isInteger(value) ? value.toString() : value.toFixed(2)
}

const TYPE_BADGE_COLORS = {
  integer: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  float: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  boolean: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  datetime: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  string: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300',
}

function NumericStats({ stats }) {
  const rows = [
    ['Count', stats.count],
    ['Mean', formatNumber(stats.mean)],
    ['Median', formatNumber(stats.median)],
    ['Std dev', formatNumber(stats.std)],
    ['Min', formatNumber(stats.min)],
    ['Q1', formatNumber(stats.q1)],
    ['Q3', formatNumber(stats.q3)],
    ['Max', formatNumber(stats.max)],
  ]
  return <StatRows rows={rows} />
}

function StringStats({ stats }) {
  const rows = [
    ['Count', stats.count],
    ['Unique', stats.unique],
    ['Mode', stats.mode ?? '—'],
  ]
  return <StatRows rows={rows} />
}

function BooleanStats({ stats }) {
  const rows = [
    ['True', stats.true_count],
    ['False', stats.false_count],
    ['% True', `${stats.pct_true}%`],
  ]
  return <StatRows rows={rows} />
}

function StatRows({ rows }) {
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
          <dd className="text-right font-medium text-slate-800 dark:text-slate-100">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function ColumnCard({ name, summary }) {
  const { type, missing_count: missingCount, missing_pct: missingPct, stats } = summary
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <h4 className="truncate font-semibold text-slate-800 dark:text-slate-100" title={name}>
          {name}
        </h4>
        <span
          className={`rounded px-2 py-0.5 text-xs font-medium ${
            TYPE_BADGE_COLORS[type] || 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
          }`}
        >
          {type}
        </span>
      </div>

      {(type === 'integer' || type === 'float') && <NumericStats stats={stats} />}
      {type === 'boolean' && <BooleanStats stats={stats} />}
      {(type === 'string' || type === 'datetime') && <StringStats stats={stats} />}

      {missingCount > 0 && (
        <p className="text-xs text-orange-600 dark:text-orange-400">
          {missingCount} valeur(s) manquante(s) ({missingPct}%)
        </p>
      )}
    </div>
  )
}

export default function StatsPanel({ sessionId, refreshKey }) {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getStats(sessionId)
      .then(({ data }) => {
        if (!cancelled) setSummary(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err?.response?.data?.error?.message ||
              'Impossible de charger les statistiques.',
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
    return <p className="p-4 text-sm text-slate-500 dark:text-slate-400">Calcul des statistiques…</p>
  }
  if (error) {
    return <p className="rounded-md bg-red-50 p-4 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{error}</p>
  }
  if (!summary) return null

  const { columns, n_rows: nRows, n_columns: nColumns, memory_usage_bytes: memoryBytes, filtered } = summary

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-50">
          Statistiques par colonne
          {filtered && (
            <span className="ml-2 rounded bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
              filtré
            </span>
          )}
        </h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {nRows} lignes × {nColumns} colonnes — {(memoryBytes / 1024).toFixed(1)} KB en mémoire
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(columns).map(([name, colSummary]) => (
          <ColumnCard key={name} name={name} summary={colSummary} />
        ))}
      </div>
    </div>
  )
}
