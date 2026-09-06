import { useEffect, useMemo, useState } from 'react'
import { exportGroupBy, getPreview, runGroupBy } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'
import PlotPreview from './PlotPreview'
import ResultTable from './ui/ResultTable'
import {
  BUTTON_CLASS,
  Badge,
  ChipMultiSelect,
  ErrorBox,
  INPUT_CLASS,
  InfoTip,
  Loading,
  PRIMARY_BUTTON_CLASS,
  Panel,
  SliderField,
  StatCard,
  rankGroupingColumns,
} from './ui/common'

const NUMERIC_TYPES = ['integer', 'float']

const AGG_FUNCS = [
  { value: 'mean', label: 'Moyenne', numeric: true },
  { value: 'median', label: 'Médiane', numeric: true },
  { value: 'sum', label: 'Somme', numeric: true },
  { value: 'std', label: 'Écart-type', numeric: true },
  { value: 'var', label: 'Variance', numeric: true },
  { value: 'sem', label: 'Erreur standard', numeric: true },
  { value: 'quantile', label: 'Quantile', numeric: true },
  { value: 'min', label: 'Minimum', numeric: false },
  { value: 'max', label: 'Maximum', numeric: false },
  { value: 'count', label: 'Effectif', numeric: false },
  { value: 'nunique', label: 'Valeurs distinctes', numeric: false },
  { value: 'first', label: 'Première valeur', numeric: false },
  { value: 'last', label: 'Dernière valeur', numeric: false },
]

let nextId = 1

/**
 * Agrégations par groupe : « quelle est la moyenne de X, par Y ? ».
 * Chaque ligne d'agrégation cible une colonne, une fonction et un nom de
 * résultat ; le tableau et le graphique sont recalculés à la demande.
 */
export default function GroupByAnalysis({ sessionId, refreshKey }) {
  const saveFile = useSaveFile()
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})
  const [groupBy, setGroupBy] = useState([])
  const [aggregations, setAggregations] = useState([])
  const [sortBy, setSortBy] = useState('')
  const [sortAscending, setSortAscending] = useState(true)
  const [limit, setLimit] = useState(200)
  const [precision, setPrecision] = useState(4)

  const [result, setResult] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState(null)
  const [exportError, setExportError] = useState(null)

  const numericColumns = useMemo(
    () => columns.filter((c) => NUMERIC_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      const grouping = rankGroupingColumns(data.columns, data.column_types, data.rows)
      const numeric = data.columns.filter((c) => NUMERIC_TYPES.includes(data.column_types[c]))
      setGroupBy(grouping.slice(0, 1))
      setAggregations(numeric.slice(0, 1).map((col) => ({ id: nextId++, column: col, func: 'mean', quantile: 0.5, alias: '' })))
      setResult(null)
    })
  }, [sessionId, refreshKey])

  const toggleGroupColumn = (col) =>
    setGroupBy((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]))

  const addAggregation = () => {
    const column = numericColumns[0] || columns[0]
    if (!column) return
    setAggregations((prev) => [...prev, { id: nextId++, column, func: 'mean', quantile: 0.5, alias: '' }])
  }

  const updateAggregation = (id, patch) =>
    setAggregations((prev) => prev.map((a) => (a.id === id ? { ...a, ...patch } : a)))

  const removeAggregation = (id) => setAggregations((prev) => prev.filter((a) => a.id !== id))

  const payload = () => ({
    groupBy,
    aggregations: aggregations.map(({ column, func, quantile, alias }) => ({
      column,
      func,
      quantile: Number(quantile) || 0.5,
      alias: alias.trim() || undefined,
    })),
    sortBy,
    sortAscending,
    limit,
  })

  const compute = async () => {
    setIsRunning(true)
    setError(null)
    try {
      const { data } = await runGroupBy(sessionId, payload())
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Impossible de calculer ces agrégations.")
      setResult(null)
    } finally {
      setIsRunning(false)
    }
  }

  const handleExport = async (format) => {
    setExportError(null)
    try {
      const response = await exportGroupBy(sessionId, { ...payload(), format, precision })
      const filename = extractFilename(response.headers['content-disposition'], `groupby.${format}`)
      await saveFile(response.data, filename)
    } catch (err) {
      let message = "Échec de l'export."
      try {
        message = JSON.parse(await err.response.data.text())?.error?.message || message
      } catch {
        message = err?.message || message
      }
      setExportError(message)
    }
  }

  const handleSort = (column) => {
    if (sortBy === column) setSortAscending((v) => !v)
    else {
      setSortBy(column)
      setSortAscending(true)
    }
  }

  // Le tri est appliqué côté serveur : on relance dès qu'il change, si un
  // résultat existe déjà (sinon l'utilisateur n'a pas encore lancé le calcul).
  useEffect(() => {
    if (result) compute()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortBy, sortAscending])

  if (columns.length === 0) return <Loading>Chargement des colonnes…</Loading>

  const canCompute = groupBy.length > 0 && aggregations.length > 0

  return (
    <div className="flex flex-col gap-4">
      <Panel className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-300">
            Regrouper par
            <InfoTip text="Plusieurs colonnes créent des groupes croisés : une ligne de résultat par combinaison observée." />
          </span>
          <ChipMultiSelect groupLabel="Colonnes de regroupement" options={columns} selected={groupBy} onToggle={toggleGroupColumn} />
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Agrégations</span>
          {aggregations.map((agg) => (
            <div
              key={agg.id}
              className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-800"
            >
              <select
                value={agg.column}
                onChange={(e) => updateAggregation(agg.id, { column: e.target.value })}
                className={INPUT_CLASS}
              >
                {columns.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <select
                value={agg.func}
                onChange={(e) => updateAggregation(agg.id, { func: e.target.value })}
                className={INPUT_CLASS}
              >
                {AGG_FUNCS.map((f) => (
                  <option
                    key={f.value}
                    value={f.value}
                    disabled={f.numeric && !NUMERIC_TYPES.includes(columnTypes[agg.column])}
                  >
                    {f.label}
                    {f.numeric && !NUMERIC_TYPES.includes(columnTypes[agg.column]) ? ' (numérique requis)' : ''}
                  </option>
                ))}
              </select>
              {agg.func === 'quantile' && (
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={agg.quantile}
                  onChange={(e) => updateAggregation(agg.id, { quantile: e.target.value })}
                  className={`${INPUT_CLASS} w-24`}
                  title="Quantile entre 0 et 1 (0,5 = médiane)"
                />
              )}
              <input
                value={agg.alias}
                onChange={(e) => updateAggregation(agg.id, { alias: e.target.value })}
                placeholder="nom du résultat (optionnel)"
                className={`${INPUT_CLASS} w-56`}
              />
              <button
                onClick={() => removeAggregation(agg.id)}
                className="ml-auto rounded px-2 py-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-950/40"
                aria-label="Supprimer cette agrégation"
              >
                ✕
              </button>
            </div>
          ))}
          <button onClick={addAggregation} className={`${BUTTON_CLASS} self-start`}>
            + Agrégation
          </button>
        </div>

        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <SliderField
            label="Lignes affichées"
            value={limit}
            onChange={setLimit}
            min={10}
            max={1000}
            step={10}
            hint="Le nombre total de groupes est indiqué avec le résultat, même si l'affichage est tronqué."
          />
          <SliderField label="Précision" value={precision} onChange={setPrecision} min={0} max={8} format={(v) => `${v} déc.`} />
          <button onClick={compute} disabled={!canCompute || isRunning} className={PRIMARY_BUTTON_CLASS}>
            {isRunning ? 'Calcul…' : 'Calculer'}
          </button>
          {!canCompute && (
            <span className="text-sm text-slate-400 dark:text-slate-500">
              Choisissez au moins une colonne de regroupement et une agrégation.
            </span>
          )}
        </div>
      </Panel>

      {error && <ErrorBox>{error}</ErrorBox>}
      {exportError && <ErrorBox>{exportError}</ErrorBox>}

      {result && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <StatCard label="Groupes" value={result.group_count} sub={`${result.shown_rows} affiché(s)`} tone="blue" />
            <StatCard label="Colonnes calculées" value={result.value_columns.length} />
            {result.truncated && <Badge tone="amber">affichage tronqué à {limit} lignes</Badge>}
            <div className="ml-auto flex items-center gap-2">
              <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Exporter :</span>
              {['csv', 'excel', 'latex'].map((fmt) => (
                <button key={fmt} onClick={() => handleExport(fmt)} className={BUTTON_CLASS}>
                  {fmt.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <ResultTable
            columns={result.columns}
            rows={result.rows}
            highlightColumns={result.group_columns}
            precision={precision}
            sortBy={sortBy}
            sortAscending={sortAscending}
            onSort={handleSort}
          />

          {result.figure && (
            <div className="flex flex-col gap-1">
              <PlotPreview figure={result.figure} />
              <p className="px-1 text-xs text-slate-500 dark:text-slate-400">
                Les agrégations partagent le même axe : cliquez sur une entrée de légende pour masquer une série dont
                l&apos;échelle écrase les autres.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
