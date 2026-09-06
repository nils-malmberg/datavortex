import { useEffect, useMemo, useState } from 'react'
import { exportPivot, getPreview, runPivot } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'
import PlotPreview from './PlotPreview'
import ResultTable from './ui/ResultTable'
import {
  BUTTON_CLASS,
  Badge,
  ChipMultiSelect,
  ErrorBox,
  FieldSelect,
  InfoTip,
  Loading,
  PRIMARY_BUTTON_CLASS,
  Panel,
  Segmented,
  SliderField,
  StatCard,
  Toggle,
  rankGroupingColumns,
} from './ui/common'

const NUMERIC_TYPES = ['integer', 'float']

const AGGFUNCS = [
  { value: 'mean', label: 'Moyenne', numeric: true },
  { value: 'median', label: 'Médiane', numeric: true },
  { value: 'sum', label: 'Somme', numeric: true },
  { value: 'std', label: 'Écart-type', numeric: true },
  { value: 'var', label: 'Variance', numeric: true },
  { value: 'count', label: 'Effectif', numeric: false },
  { value: 'nunique', label: 'Valeurs distinctes', numeric: false },
  { value: 'min', label: 'Minimum', numeric: false },
  { value: 'max', label: 'Maximum', numeric: false },
]

const PERCENTAGE_MODES = [
  { value: 'none', label: 'Valeurs' },
  { value: 'total', label: '% du total' },
  { value: 'row', label: '% par ligne' },
  { value: 'column', label: '% par colonne' },
]

/**
 * Tableau croisé dynamique : lignes × colonnes, une valeur agrégée par cellule.
 * La heatmap associée rend immédiatement lisible où se concentrent les valeurs.
 */
export default function PivotTableBuilder({ sessionId, refreshKey, onAddToReport }) {
  const saveFile = useSaveFile()
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})

  const [index, setIndex] = useState([])
  const [pivotColumns, setPivotColumns] = useState([])
  const [values, setValues] = useState('')
  const [aggfunc, setAggfunc] = useState('mean')
  const [margins, setMargins] = useState(true)
  const [percentage, setPercentage] = useState('none')
  const [precision, setPrecision] = useState(3)

  const [result, setResult] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState(null)
  const [exportError, setExportError] = useState(null)

  const valueIsNumeric = NUMERIC_TYPES.includes(columnTypes[values])

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      const grouping = rankGroupingColumns(data.columns, data.column_types, data.rows)
      const numeric = data.columns.filter((c) => NUMERIC_TYPES.includes(data.column_types[c]))
      setIndex(grouping.slice(0, 1))
      setPivotColumns(grouping.slice(1, 2))
      setValues(numeric[0] || data.columns[0] || '')
      setResult(null)
    })
  }, [sessionId, refreshKey])

  // Une agrégation numérique sur une colonne texte serait refusée : on bascule.
  useEffect(() => {
    const config = AGGFUNCS.find((f) => f.value === aggfunc)
    if (config?.numeric && values && !valueIsNumeric) setAggfunc('count')
  }, [values, valueIsNumeric, aggfunc])

  const payload = useMemo(
    () => ({ index, columns: pivotColumns, values, aggfunc, margins, percentage }),
    [index, pivotColumns, values, aggfunc, margins, percentage],
  )

  const compute = async () => {
    setIsRunning(true)
    setError(null)
    try {
      const { data } = await runPivot(sessionId, payload)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Impossible de construire ce tableau croisé.')
      setResult(null)
    } finally {
      setIsRunning(false)
    }
  }

  const handleExport = async (format) => {
    setExportError(null)
    try {
      const response = await exportPivot(sessionId, { ...payload, format, precision })
      const filename = extractFilename(response.headers['content-disposition'], `pivot.${format}`)
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

  const toggle = (setter, current) => (col) =>
    setter(current.includes(col) ? current.filter((c) => c !== col) : [...current, col])

  if (columns.length === 0) return <Loading>Chargement des colonnes…</Loading>

  const canCompute = index.length > 0 && values

  return (
    <div className="flex flex-col gap-4">
      <Panel className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-300">
              Lignes (index)
              <InfoTip text="Les modalités de ces colonnes deviennent les lignes du tableau." />
            </span>
            <ChipMultiSelect
              groupLabel="Lignes (index)"
              options={columns.filter((c) => !pivotColumns.includes(c))}
              selected={index}
              onToggle={toggle(setIndex, index)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-300">
              Colonnes
              <InfoTip text="Les modalités de ces colonnes deviennent les colonnes du tableau. Facultatif." />
            </span>
            <ChipMultiSelect
              groupLabel="Colonnes du tableau croisé"
              options={columns.filter((c) => !index.includes(c))}
              selected={pivotColumns}
              onToggle={toggle(setPivotColumns, pivotColumns)}
            />
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <FieldSelect
            label="Valeurs à agréger"
            value={values}
            onChange={setValues}
            options={columns}
            hint="La colonne dont chaque cellule résume les valeurs."
          />
          <FieldSelect
            label="Agrégation"
            value={aggfunc}
            onChange={setAggfunc}
            options={AGGFUNCS.filter((f) => !f.numeric || valueIsNumeric)}
          />
          <label className="flex flex-col gap-1 text-sm">
            <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
              Affichage
              <InfoTip text="« % par ligne » répond à « comment se répartit cette ligne ? », « % par colonne » à la question symétrique." />
            </span>
            <Segmented options={PERCENTAGE_MODES} value={percentage} onChange={setPercentage} size="sm" />
          </label>
          <Toggle
            label="Afficher les totaux"
            checked={margins}
            onChange={setMargins}
            hint="Ajoute une ligne et une colonne de totaux. Ces marges sont exclues des dénominateurs des pourcentages."
          />
          <SliderField label="Précision" value={precision} onChange={setPrecision} min={0} max={6} format={(v) => `${v} déc.`} />
          <button onClick={compute} disabled={!canCompute || isRunning} className={PRIMARY_BUTTON_CLASS}>
            {isRunning ? 'Calcul…' : 'Construire le tableau'}
          </button>
          {!canCompute && (
            <span className="text-sm text-slate-400 dark:text-slate-500">
              Choisissez au moins une colonne de lignes et une colonne de valeurs.
            </span>
          )}
        </div>
      </Panel>

      {error && <ErrorBox>{error}</ErrorBox>}
      {exportError && <ErrorBox>{exportError}</ErrorBox>}

      {result && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <StatCard label="Lignes" value={result.n_rows} tone="blue" />
            <StatCard label="Colonnes de valeurs" value={result.n_value_columns} />
            {result.percentage !== 'none' && (
              <Badge tone="amber">
                {PERCENTAGE_MODES.find((m) => m.value === result.percentage)?.label}
              </Badge>
            )}
            {result.margins && <Badge tone="slate">totaux inclus</Badge>}
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
            highlightColumns={result.index_columns}
            precision={percentage === 'none' ? precision : 2}
          />

          {result.figure && (
            <div className="flex flex-col gap-1">
              <PlotPreview figure={result.figure} />
              {result.heatmap_truncated && (
                <p className="px-1 text-xs text-amber-700 dark:text-amber-400">
                  Le tableau ci-dessus est complet, mais la heatmap ne montre que ses premières lignes : au-delà,
                  les libellés deviennent illisibles. Réduisez le nombre de modalités en lignes pour une lecture
                  visuelle utile.
                </p>
              )}
            </div>
          )}

          {onAddToReport && (
            <button
              onClick={() =>
                onAddToReport({
                  id: crypto.randomUUID(),
                  kind: 'pivot',
                  params: payload,
                  label: `Pivot : ${index.join(', ')} × ${pivotColumns.join(', ') || '—'}`,
                })
              }
              className={`${BUTTON_CLASS} self-start`}
            >
              + Ajouter au rapport
            </button>
          )}
        </>
      )}
    </div>
  )
}
