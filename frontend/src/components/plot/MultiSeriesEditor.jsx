import { useEffect, useMemo, useState } from 'react'
import { getPreview, plotMultiSeries } from '../../api/client'
import PlotPreview from '../PlotPreview'
import { BUTTON_CLASS, FieldSelect, INPUT_CLASS } from '../ui/common'

const NUMERIC_TYPES = ['integer', 'float']
const MAX_SERIES = 10

// Même palette que le backend (app/plotting.py) : la couleur affichée dans le
// sélecteur avant toute personnalisation correspond déjà à celle du graphique.
const DEFAULT_PALETTE = [
  '#4C78A8', '#F58518', '#54A24B', '#E45756', '#72B7B2',
  '#EECA3B', '#B279A2', '#FF9DA6', '#9D755D', '#BAB0AC',
]

const PLOT_TYPE_OPTIONS = [
  { value: 'scatter', label: 'Scatter' },
  { value: 'line', label: 'Ligne' },
  { value: 'bar', label: 'Barres' },
  { value: 'area', label: 'Aire' },
]

let nextSeriesId = 1
function makeSeries(yColumn) {
  return {
    id: `series_${nextSeriesId++}`,
    yColumn: yColumn || '',
    yAxis: 'left',
    plotType: 'scatter',
    name: '',
    color: DEFAULT_PALETTE[(nextSeriesId - 2) % DEFAULT_PALETTE.length],
  }
}

/**
 * Un graphique, plusieurs séries Y indépendantes, avec axe Y secondaire
 * optionnel (Phase 10). Chaque série choisit sa propre colonne, son type de
 * trace et son axe — utile pour superposer des grandeurs d'échelles très
 * différentes (ex : chiffre d'affaires en euros et unités vendues) sans que
 * l'une écrase visuellement l'autre.
 *
 * `onConfigChange` remonte la configuration courante à chaque changement,
 * pour qu'un parent (tableau de bord multi-graphiques) puisse la conserver en
 * vue d'un export groupé, sans que ce composant ait besoin de connaître ce
 * parent.
 */
export default function MultiSeriesEditor({ sessionId, refreshKey, initialConfig, onConfigChange }) {
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})

  const [title, setTitle] = useState(initialConfig?.title || '')
  const [xAxis, setXAxis] = useState(initialConfig?.xAxis || '')
  const [series, setSeries] = useState(initialConfig?.series?.length ? initialConfig.series : [])

  const [figure, setFigure] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const numericColumns = useMemo(
    () => columns.filter((c) => NUMERIC_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      const numeric = data.columns.filter((c) => NUMERIC_TYPES.includes(data.column_types[c]))
      setXAxis((prev) => prev || data.columns[0] || '')
      setSeries((prev) => (prev.length > 0 ? prev : numeric[0] ? [makeSeries(numeric[0])] : []))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, refreshKey])

  const addSeries = () => {
    if (series.length >= MAX_SERIES) return
    setSeries((prev) => [...prev, makeSeries(numericColumns.find((c) => !prev.some((s) => s.yColumn === c)) || numericColumns[0])])
  }

  const removeSeries = (id) => setSeries((prev) => prev.filter((s) => s.id !== id))

  const updateSeries = (id, patch) =>
    setSeries((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)))

  const hasSecondaryAxis = series.some((s) => s.yAxis === 'right')
  const isReady = Boolean(xAxis) && series.length > 0 && series.every((s) => s.yColumn)

  // --- Génération du graphique (débouncée) ---------------------------------
  useEffect(() => {
    if (!isReady) {
      setFigure(null)
      setError(null)
      return
    }
    const payload = {
      title: title || undefined,
      xAxis,
      series: series.map((s) => ({
        y_column: s.yColumn,
        y_axis: s.yAxis,
        plot_type: s.plotType,
        name: s.name || undefined,
        color: s.color || undefined,
      })),
    }
    setIsLoading(true)
    setError(null)
    const timer = setTimeout(async () => {
      try {
        const { data } = await plotMultiSeries(sessionId, payload)
        setFigure(data.figure)
      } catch (err) {
        setError(err?.response?.data?.error?.message || 'Impossible de générer ce graphique.')
        setFigure(null)
      } finally {
        setIsLoading(false)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(series), xAxis, title, sessionId, isReady])

  // --- Remontée de la configuration au parent -------------------------------
  useEffect(() => {
    onConfigChange?.({ title, xAxis, series })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(series), xAxis, title])

  if (columns.length === 0) {
    return <p className="p-4 text-sm text-slate-500 dark:text-slate-400">Chargement des colonnes…</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Titre</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Titre du graphique (optionnel)"
            className={`${INPUT_CLASS} w-56`}
          />
        </label>
        <FieldSelect label="Axe X" value={xAxis} onChange={setXAxis} options={columns} />
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Séries ({series.length})
          </h4>
          {hasSecondaryAxis && (
            <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
              ✓ Axe Y secondaire activé
            </span>
          )}
        </div>

        {series.map((s) => (
          <div
            key={s.id}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-2.5 dark:border-slate-800 dark:bg-slate-900"
          >
            <input
              type="text"
              value={s.name}
              onChange={(e) => updateSeries(s.id, { name: e.target.value })}
              placeholder={s.yColumn || 'Nom de la série'}
              className={`${INPUT_CLASS} w-32`}
            />
            <FieldSelect
              value={s.yColumn}
              onChange={(v) => updateSeries(s.id, { yColumn: v })}
              options={numericColumns}
              allowEmpty
              emptyLabel="Colonne Y…"
            />
            <FieldSelect
              value={s.plotType}
              onChange={(v) => updateSeries(s.id, { plotType: v })}
              options={PLOT_TYPE_OPTIONS}
            />
            <FieldSelect
              value={s.yAxis}
              onChange={(v) => updateSeries(s.id, { yAxis: v })}
              options={[
                { value: 'left', label: 'Axe gauche' },
                { value: 'right', label: 'Axe droit (secondaire)' },
              ]}
            />
            <input
              type="color"
              value={s.color}
              onChange={(e) => updateSeries(s.id, { color: e.target.value })}
              title="Couleur de la série"
              className="h-8 w-8 cursor-pointer rounded border border-slate-300 dark:border-slate-600"
            />
            <button
              onClick={() => removeSeries(s.id)}
              disabled={series.length <= 1}
              title="Retirer cette série"
              className="ml-auto rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30 dark:hover:bg-red-950/40"
            >
              ✕
            </button>
          </div>
        ))}

        <button onClick={addSeries} disabled={series.length >= MAX_SERIES} className={`${BUTTON_CLASS} self-start`}>
          + Ajouter une série
        </button>
      </div>

      <PlotPreview figure={figure} isLoading={isLoading} error={error} />
    </div>
  )
}
