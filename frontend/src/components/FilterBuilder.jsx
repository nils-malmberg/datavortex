import { useEffect, useMemo, useRef, useState } from 'react'
import { applyFilter, getPreview } from '../api/client'

const NUMERIC_TYPES = ['integer', 'float']

const OPERATORS_BY_CATEGORY = {
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
    { value: 'is_null', label: 'est vide' },
    { value: 'is_not_null', label: "n'est pas vide" },
  ],
  string: [
    { value: 'eq', label: 'égal à' },
    { value: 'ne', label: 'différent de' },
    { value: 'contains', label: 'contient' },
    { value: 'starts_with', label: 'commence par' },
    { value: 'ends_with', label: 'finit par' },
    { value: 'regex', label: 'expression régulière' },
    { value: 'in', label: 'dans la liste' },
    { value: 'not_in', label: 'hors de la liste' },
    { value: 'is_null', label: 'est vide' },
    { value: 'is_not_null', label: "n'est pas vide" },
  ],
  boolean: [
    { value: 'is_true', label: 'est vrai' },
    { value: 'is_false', label: 'est faux' },
    { value: 'is_null', label: 'est vide' },
    { value: 'is_not_null', label: "n'est pas vide" },
  ],
  datetime: [
    { value: 'eq', label: '=' },
    { value: 'gt', label: 'après' },
    { value: 'lt', label: 'avant' },
    { value: 'between', label: 'entre' },
    { value: 'year', label: 'année =' },
    { value: 'month', label: 'mois =' },
    { value: 'day', label: 'jour =' },
    { value: 'is_null', label: 'est vide' },
    { value: 'is_not_null', label: "n'est pas vide" },
  ],
}

const NO_VALUE_OPS = new Set(['is_null', 'is_not_null', 'is_true', 'is_false'])
const RANGE_OPS = new Set(['between'])
const LIST_OPS = new Set(['in', 'not_in'])

function categoryFor(colType) {
  if (NUMERIC_TYPES.includes(colType)) return 'numeric'
  if (colType === 'boolean') return 'boolean'
  if (colType === 'datetime') return 'datetime'
  return 'string'
}

let nextId = 1
function newCondition(column) {
  return { id: nextId++, column, operator: 'eq', value: '' }
}

function buildPayload(logic, conditions, columnTypes) {
  const built = conditions
    .filter((c) => c.column)
    .map((c) => {
      const category = categoryFor(columnTypes[c.column])
      let value = c.value
      if (NO_VALUE_OPS.has(c.operator)) {
        value = null
      } else if (LIST_OPS.has(c.operator)) {
        const items = String(value || '').split(',').map((v) => v.trim()).filter((v) => v !== '')
        value = category === 'numeric' ? items.map(Number) : items
      } else if (RANGE_OPS.has(c.operator)) {
        const [lo, hi] = Array.isArray(value) ? value : ['', '']
        value = category === 'numeric' ? [Number(lo), Number(hi)] : [lo, hi]
      } else if (category === 'numeric') {
        value = value === '' ? null : Number(value)
      }
      return { type: 'condition', column: c.column, operator: c.operator, value }
    })

  if (built.length === 0) return null
  if (built.length === 1) return built[0]
  return { type: 'group', logic, conditions: built }
}

function ConditionRow({ condition, columns, columnTypes, onChange, onRemove }) {
  const category = categoryFor(columnTypes[condition.column])
  const operators = OPERATORS_BY_CATEGORY[category] || OPERATORS_BY_CATEGORY.string
  const isNumeric = category === 'numeric'
  const inputType = isNumeric ? 'number' : 'text'

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2">
      <select
        value={condition.column}
        onChange={(e) => {
          const nextCategory = categoryFor(columnTypes[e.target.value])
          const firstOp = (OPERATORS_BY_CATEGORY[nextCategory] || OPERATORS_BY_CATEGORY.string)[0].value
          onChange({ ...condition, column: e.target.value, operator: firstOp, value: '' })
        }}
        className="rounded-md border border-slate-300 px-2 py-1 text-sm"
      >
        {columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <select
        value={condition.operator}
        onChange={(e) => onChange({ ...condition, operator: e.target.value, value: '' })}
        className="rounded-md border border-slate-300 px-2 py-1 text-sm"
      >
        {operators.map((op) => (
          <option key={op.value} value={op.value}>
            {op.label}
          </option>
        ))}
      </select>

      {NO_VALUE_OPS.has(condition.operator) ? null : RANGE_OPS.has(condition.operator) ? (
        <div className="flex items-center gap-1.5">
          <input
            type={inputType}
            value={condition.value?.[0] ?? ''}
            onChange={(e) => onChange({ ...condition, value: [e.target.value, condition.value?.[1] ?? ''] })}
            placeholder="min"
            className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <span className="text-sm text-slate-500">et</span>
          <input
            type={inputType}
            value={condition.value?.[1] ?? ''}
            onChange={(e) => onChange({ ...condition, value: [condition.value?.[0] ?? '', e.target.value] })}
            placeholder="max"
            className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
      ) : LIST_OPS.has(condition.operator) ? (
        <input
          type="text"
          value={condition.value ?? ''}
          onChange={(e) => onChange({ ...condition, value: e.target.value })}
          placeholder="valeur1, valeur2, ..."
          className="w-48 rounded-md border border-slate-300 px-2 py-1 text-sm"
        />
      ) : (
        <input
          type={inputType}
          value={condition.value ?? ''}
          onChange={(e) => onChange({ ...condition, value: e.target.value })}
          placeholder="valeur"
          className="w-36 rounded-md border border-slate-300 px-2 py-1 text-sm"
        />
      )}

      <button
        onClick={onRemove}
        className="ml-auto rounded-md px-2 py-1 text-sm text-red-600 hover:bg-red-50"
        aria-label="Supprimer cette condition"
      >
        ✕
      </button>
    </div>
  )
}

export default function FilterBuilder({ sessionId, onFilterApplied }) {
  const storageKey = `datavortex_filter_${sessionId}`
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})
  const [logic, setLogic] = useState('AND')
  const [conditions, setConditions] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const hasRestored = useRef(false)

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      if (!hasRestored.current) {
        hasRestored.current = true
        try {
          const saved = sessionStorage.getItem(storageKey)
          if (saved) {
            const parsed = JSON.parse(saved)
            if (parsed.logic) setLogic(parsed.logic)
            if (Array.isArray(parsed.conditions) && parsed.conditions.length > 0) {
              setConditions(parsed.conditions.map((c) => ({ ...c, id: nextId++ })))
            }
          }
        } catch {
          // sessionStorage indisponible ou corrompu : on ignore silencieusement.
        }
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const addCondition = () => {
    if (columns.length === 0) return
    setConditions((prev) => [...prev, newCondition(columns[0])])
  }

  const updateCondition = (id, next) => {
    setConditions((prev) => prev.map((c) => (c.id === id ? next : c)))
  }

  const removeCondition = (id) => {
    setConditions((prev) => prev.filter((c) => c.id !== id))
  }

  const resetFilters = () => setConditions([])

  const payload = useMemo(
    () => buildPayload(logic, conditions, columnTypes),
    [logic, conditions, columnTypes],
  )

  useEffect(() => {
    if (columns.length === 0) return
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({ logic, conditions }))
    } catch {
      // stockage indisponible : pas bloquant pour la fonctionnalité.
    }

    setIsLoading(true)
    setError(null)
    const timer = setTimeout(async () => {
      try {
        const { data } = await applyFilter(sessionId, payload)
        setResult(data)
        onFilterApplied?.()
      } catch (err) {
        setError(
          err?.response?.data?.error?.message ||
            'Impossible d’appliquer ce filtre.',
        )
      } finally {
        setIsLoading(false)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(payload), sessionId])

  if (columns.length === 0) {
    return <p className="p-4 text-sm text-slate-500">Chargement des colonnes…</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-600">Combiner avec :</span>
          <select
            value={logic}
            onChange={(e) => setLogic(e.target.value)}
            disabled={conditions.length < 2}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm disabled:opacity-50"
          >
            <option value="AND">ET (toutes les conditions)</option>
            <option value="OR">OU (au moins une condition)</option>
          </select>
        </div>
        <p className="text-sm text-slate-500">
          {result
            ? `${result.total_rows} ligne(s) sélectionnée(s) sur ${result.total_rows_unfiltered} au total`
            : `${conditions.length === 0 ? 'Aucun filtre actif' : ''}`}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {conditions.map((condition) => (
          <ConditionRow
            key={condition.id}
            condition={condition}
            columns={columns}
            columnTypes={columnTypes}
            onChange={(next) => updateCondition(condition.id, next)}
            onRemove={() => removeCondition(condition.id)}
          />
        ))}
      </div>

      <div className="flex gap-2">
        <button
          onClick={addCondition}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          + Ajouter une condition
        </button>
        <button
          onClick={resetFilters}
          disabled={conditions.length === 0}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
        >
          Réinitialiser
        </button>
        {isLoading && <span className="self-center text-sm text-slate-400">Application du filtre…</span>}
      </div>

      {error && <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>}
    </div>
  )
}
