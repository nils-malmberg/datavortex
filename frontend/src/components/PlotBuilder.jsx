import { useEffect, useMemo, useState } from 'react'
import { getPreview, plot1D, plot2D, plot3D } from '../api/client'
import PlotPreview from './PlotPreview'
import ExportPlot from './ExportPlot'

const NUMERIC_TYPES = ['integer', 'float']
const CATEGORICAL_TYPES = ['string', 'boolean']

const CATEGORIES = [
  { value: '1d', label: '1D (univarié)' },
  { value: '2d', label: '2D (bivarié)' },
  { value: '3d', label: '3D (trivarié)' },
]

const PLOT_TYPES = {
  '1d': [
    { value: 'histogram', label: 'Histogramme', fields: ['column', 'group_by', 'bins'], required: ['column'] },
    { value: 'box', label: 'Box plot', fields: ['column', 'group_by'], required: ['column'] },
    { value: 'violin', label: 'Violin plot', fields: ['column', 'group_by'], required: ['column'] },
    { value: 'kde', label: 'Densité (KDE)', fields: ['column'], required: ['column'] },
    { value: 'bar', label: 'Bar chart (catégories)', fields: ['column'], required: ['column'] },
    { value: 'pie', label: 'Pie chart', fields: ['column'], required: ['column'] },
  ],
  '2d': [
    { value: 'scatter', label: 'Scatter plot', fields: ['x', 'y', 'color_by', 'size_by'], required: ['x', 'y'] },
    { value: 'line', label: 'Line chart', fields: ['x', 'y', 'color_by'], required: ['x', 'y'] },
    { value: 'bar_grouped', label: 'Bar chart groupé', fields: ['x', 'y', 'color_by'], required: ['x', 'y', 'color_by'] },
    { value: 'bubble', label: 'Bubble chart', fields: ['x', 'y', 'size_by', 'color_by'], required: ['x', 'y', 'size_by'] },
    { value: 'heatmap', label: 'Heatmap (corrélations)', fields: ['columns'], required: [] },
    { value: 'hexbin', label: 'Hexbin (densité 2D)', fields: ['x', 'y', 'bins'], required: ['x', 'y'] },
  ],
  '3d': [
    { value: 'scatter3d', label: 'Scatter 3D', fields: ['x', 'y', 'z', 'color_by'], required: ['x', 'y', 'z'] },
    { value: 'surface', label: 'Surface plot', fields: ['x', 'y', 'z'], required: ['x', 'y', 'z'] },
  ],
}

const NUMERIC_ONLY_FIELDS = {
  x: ['scatter', 'hexbin', 'bubble', 'scatter3d', 'surface'],
  y: ['scatter', 'hexbin', 'bubble', 'scatter3d', 'surface', 'line'],
  z: ['scatter3d', 'surface'],
}

const FIELD_LABELS = {
  column: 'Colonne',
  group_by: 'Grouper par (optionnel)',
  x: 'Axe X',
  y: 'Axe Y',
  z: 'Axe Z',
  color_by: 'Couleur par (optionnel)',
  size_by: 'Taille par',
  columns: 'Colonnes incluses',
  bins: 'Nombre de bins',
}

function columnFilterFor(field, plotType) {
  if (field === 'size_by' || field === 'columns') return 'numeric'
  if (field === 'group_by') return 'categorical'
  if (NUMERIC_ONLY_FIELDS[field]?.includes(plotType)) return 'numeric'
  return 'any'
}

const DEFAULT_PARAMS = {
  column: '', group_by: '', x: '', y: '', z: '',
  color_by: '', size_by: '', columns: [], bins: 20, title: '',
}

export default function PlotBuilder({ sessionId }) {
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})
  const [category, setCategory] = useState('2d')
  const [plotType, setPlotType] = useState('scatter')
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [figure, setFigure] = useState(null)
  const [lastSpec, setLastSpec] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
    })
  }, [sessionId])

  const numericColumns = useMemo(
    () => columns.filter((c) => NUMERIC_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )
  const categoricalColumns = useMemo(
    () => columns.filter((c) => CATEGORICAL_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )

  const columnOptionsFor = (filterType) => {
    if (filterType === 'numeric') return numericColumns
    if (filterType === 'categorical') return categoricalColumns
    return columns
  }

  const activeConfig = PLOT_TYPES[category].find((t) => t.value === plotType)

  const updateParam = (key, value) => setParams((prev) => ({ ...prev, [key]: value }))

  const handleCategoryChange = (newCategory) => {
    setCategory(newCategory)
    const firstType = PLOT_TYPES[newCategory][0].value
    setPlotType(firstType)
  }

  const toggleHeatmapColumn = (col) => {
    setParams((prev) => {
      const current = prev.columns || []
      const next = current.includes(col) ? current.filter((c) => c !== col) : [...current, col]
      return { ...prev, columns: next }
    })
  }

  useEffect(() => {
    if (!activeConfig) return
    const missingRequired = activeConfig.required.some((f) => {
      const v = params[f]
      return v === undefined || v === null || v === '' || (Array.isArray(v) && v.length === 0)
    })
    if (missingRequired) {
      setFigure(null)
      setError(null)
      return
    }

    const payload = { plot_type: plotType }
    for (const field of activeConfig.fields) {
      const value = params[field]
      const isEmpty = value === '' || value === undefined || (Array.isArray(value) && value.length === 0)
      if (!isEmpty) payload[field] = value
    }
    if (params.title) payload.title = params.title

    setIsLoading(true)
    setError(null)
    const timer = setTimeout(async () => {
      try {
        let response
        if (category === '1d') response = await plot1D(sessionId, payload)
        else if (category === '2d') response = await plot2D(sessionId, payload)
        else response = await plot3D(sessionId, payload)
        setFigure(response.data.figure)
        setLastSpec({ kind: category, params: payload })
      } catch (err) {
        setError(
          err?.response?.data?.error?.message ||
            'Impossible de générer ce graphique avec ces paramètres.',
        )
        setFigure(null)
      } finally {
        setIsLoading(false)
      }
    }, 400)

    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, plotType, JSON.stringify(params), sessionId])

  if (columns.length === 0) {
    return <p className="p-4 text-sm text-slate-500">Chargement des colonnes…</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              onClick={() => handleCategoryChange(c.value)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                category === c.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600">Type de graphique</span>
            <select
              value={plotType}
              onChange={(e) => setPlotType(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5"
            >
              {PLOT_TYPES[category].map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          {activeConfig.fields.includes('column') && (
            <FieldSelect
              label={FIELD_LABELS.column}
              value={params.column}
              onChange={(v) => updateParam('column', v)}
              options={columnOptionsFor(columnFilterFor('column', plotType))}
            />
          )}
          {activeConfig.fields.includes('x') && (
            <FieldSelect
              label={FIELD_LABELS.x}
              value={params.x}
              onChange={(v) => updateParam('x', v)}
              options={columnOptionsFor(columnFilterFor('x', plotType))}
            />
          )}
          {activeConfig.fields.includes('y') && (
            <FieldSelect
              label={FIELD_LABELS.y}
              value={params.y}
              onChange={(v) => updateParam('y', v)}
              options={columnOptionsFor(columnFilterFor('y', plotType))}
            />
          )}
          {activeConfig.fields.includes('z') && (
            <FieldSelect
              label={FIELD_LABELS.z}
              value={params.z}
              onChange={(v) => updateParam('z', v)}
              options={columnOptionsFor(columnFilterFor('z', plotType))}
            />
          )}
          {activeConfig.fields.includes('group_by') && (
            <FieldSelect
              label={FIELD_LABELS.group_by}
              value={params.group_by}
              onChange={(v) => updateParam('group_by', v)}
              options={columnOptionsFor('categorical')}
              allowEmpty
            />
          )}
          {activeConfig.fields.includes('color_by') && (
            <FieldSelect
              label={FIELD_LABELS.color_by}
              value={params.color_by}
              onChange={(v) => updateParam('color_by', v)}
              options={columnOptionsFor(columnFilterFor('color_by', plotType))}
              allowEmpty={!activeConfig.required.includes('color_by')}
            />
          )}
          {activeConfig.fields.includes('size_by') && (
            <FieldSelect
              label={FIELD_LABELS.size_by}
              value={params.size_by}
              onChange={(v) => updateParam('size_by', v)}
              options={columnOptionsFor('numeric')}
              allowEmpty={!activeConfig.required.includes('size_by')}
            />
          )}
          {activeConfig.fields.includes('bins') && (
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-slate-600">{FIELD_LABELS.bins}</span>
              <input
                type="number"
                min={2}
                max={200}
                value={params.bins}
                onChange={(e) => updateParam('bins', Number(e.target.value))}
                className="w-24 rounded-md border border-slate-300 px-3 py-1.5"
              />
            </label>
          )}

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600">Titre (optionnel)</span>
            <input
              type="text"
              value={params.title}
              onChange={(e) => updateParam('title', e.target.value)}
              placeholder="Titre personnalisé"
              className="rounded-md border border-slate-300 px-3 py-1.5"
            />
          </label>
        </div>

        {activeConfig.fields.includes('columns') && (
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-slate-600">
              {FIELD_LABELS.columns} (par défaut : toutes les colonnes numériques)
            </span>
            <div className="flex flex-wrap gap-2">
              {numericColumns.map((col) => (
                <label
                  key={col}
                  className={`cursor-pointer rounded-md border px-2.5 py-1 text-xs font-medium ${
                    params.columns.includes(col)
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-slate-300 bg-white text-slate-600'
                  }`}
                >
                  <input
                    type="checkbox"
                    className="hidden"
                    checked={params.columns.includes(col)}
                    onChange={() => toggleHeatmapColumn(col)}
                  />
                  {col}
                </label>
              ))}
            </div>
          </div>
        )}
      </div>

      <PlotPreview figure={figure} isLoading={isLoading} error={error} />

      <ExportPlot
        sessionId={sessionId}
        kind={category}
        params={lastSpec?.kind === category ? lastSpec.params : null}
        disabled={!figure || isLoading}
      />
    </div>
  )
}

function FieldSelect({ label, value, onChange, options, allowEmpty }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-slate-600">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-[9rem] rounded-md border border-slate-300 px-3 py-1.5"
      >
        {allowEmpty && <option value="">—</option>}
        {options.map((col) => (
          <option key={col} value={col}>
            {col}
          </option>
        ))}
      </select>
    </label>
  )
}
