import { useState } from 'react'
import { INPUT_CLASS, InfoTip, Segmented } from '../ui/common'
import {
  COUNT_OPS,
  LIST_OPS,
  NO_VALUE_OPS,
  RANGE_OPS,
  THRESHOLD_OPS,
  categoryFor,
  newCondition,
  newGroup,
  operatorsFor,
} from './filterCatalog'

/**
 * Rendu récursif d'un nœud de filtre : une condition simple, ou un groupe qui
 * combine ses enfants en ET / OU. Les groupes imbriqués jouent le rôle des
 * parenthèses d'une expression logique.
 */
const LOGIC_OPTIONS = [
  { value: 'AND', label: 'ET' },
  { value: 'OR', label: 'OU' },
]

function ConditionValue({ condition, columnTypes, onChange }) {
  const { operator } = condition
  const category = categoryFor(columnTypes[condition.column])
  const inputType = category === 'numeric' ? 'number' : 'text'

  if (NO_VALUE_OPS.has(operator)) return null

  if (COUNT_OPS.has(operator)) {
    return (
      <input
        type="number"
        min={1}
        value={condition.value ?? ''}
        onChange={(e) => onChange({ ...condition, value: e.target.value })}
        placeholder="N"
        className={`${INPUT_CLASS} w-24`}
      />
    )
  }

  if (THRESHOLD_OPS.has(operator)) {
    return (
      <span className="flex items-center gap-1">
        <input
          type="number"
          step="0.1"
          min={0.5}
          value={condition.value ?? ''}
          onChange={(e) => onChange({ ...condition, value: e.target.value })}
          placeholder="3"
          className={`${INPUT_CLASS} w-24`}
        />
        <InfoTip text="Seuil en écarts-types. Par défaut 3 : au-delà, la valeur est jugée atypique." />
      </span>
    )
  }

  if (RANGE_OPS.has(operator)) {
    return (
      <span className="flex items-center gap-1.5">
        <input
          type={inputType}
          value={condition.value?.[0] ?? ''}
          onChange={(e) => onChange({ ...condition, value: [e.target.value, condition.value?.[1] ?? ''] })}
          placeholder="min"
          className={`${INPUT_CLASS} w-24`}
        />
        <span className="text-sm text-slate-500 dark:text-slate-400">et</span>
        <input
          type={inputType}
          value={condition.value?.[1] ?? ''}
          onChange={(e) => onChange({ ...condition, value: [condition.value?.[0] ?? '', e.target.value] })}
          placeholder="max"
          className={`${INPUT_CLASS} w-24`}
        />
      </span>
    )
  }

  return (
    <input
      type={LIST_OPS.has(operator) ? 'text' : inputType}
      value={condition.value ?? ''}
      onChange={(e) => onChange({ ...condition, value: e.target.value })}
      placeholder={LIST_OPS.has(operator) ? 'valeur1, valeur2, …' : 'valeur'}
      className={`${INPUT_CLASS} ${LIST_OPS.has(operator) ? 'w-52' : 'w-36'}`}
    />
  )
}

function ConditionRow({ node, columns, columnTypes, insight, onChange, onRemove, dragHandlers }) {
  const operators = operatorsFor(columnTypes[node.column])
  const activeOperator = operators.find((op) => op.value === node.operator)

  return (
    <div
      {...dragHandlers}
      className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-800"
    >
      <span
        className="cursor-grab select-none px-1 text-slate-400 active:cursor-grabbing dark:text-slate-500"
        title="Glisser pour réordonner"
      >
        ⠿
      </span>

      <select
        value={node.column}
        onChange={(e) => {
          const firstOp = operatorsFor(columnTypes[e.target.value])[0].value
          onChange({ ...node, column: e.target.value, operator: firstOp, value: '' })
        }}
        className={INPUT_CLASS}
      >
        {columns.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <select
        value={node.operator}
        onChange={(e) => onChange({ ...node, operator: e.target.value, value: '' })}
        className={INPUT_CLASS}
      >
        {operators.map((op) => (
          <option key={op.value} value={op.value}>
            {op.label}
          </option>
        ))}
      </select>

      {activeOperator?.hint && <InfoTip text={activeOperator.hint} />}

      <ConditionValue condition={node} columnTypes={columnTypes} onChange={onChange} />

      {insight?.matched_rows != null && (
        <span
          className="rounded bg-slate-200 px-1.5 py-0.5 text-xs tabular-nums text-slate-600 dark:bg-slate-700 dark:text-slate-300"
          title="Lignes retenues par cette condition seule, indépendamment des autres."
        >
          {insight.matched_rows} lignes · {insight.matched_pct} %
        </span>
      )}

      <button
        onClick={onRemove}
        className="ml-auto rounded-md px-2 py-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-950/40"
        aria-label="Supprimer cette condition"
      >
        ✕
      </button>
    </div>
  )
}

export default function FilterNodeView({
  node,
  columns,
  columnTypes,
  insights,
  depth = 0,
  onChange,
  onRemove,
  dragHandlers,
}) {
  const [dragIndex, setDragIndex] = useState(null)

  if (node.type === 'condition') {
    return (
      <ConditionRow
        node={node}
        columns={columns}
        columnTypes={columnTypes}
        insight={insights?.[String(node.id)]}
        onChange={onChange}
        onRemove={onRemove}
        dragHandlers={dragHandlers}
      />
    )
  }

  const updateChild = (index, next) =>
    onChange({ ...node, conditions: node.conditions.map((c, i) => (i === index ? next : c)) })

  const removeChild = (index) =>
    onChange({ ...node, conditions: node.conditions.filter((_, i) => i !== index) })

  const moveChild = (from, to) => {
    if (from === to || from == null || to == null) return
    const next = [...node.conditions]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    onChange({ ...node, conditions: next })
  }

  const firstColumn = columns[0]

  return (
    <div
      className={`flex flex-col gap-2 rounded-lg ${
        depth > 0 ? 'border-l-4 border-blue-300 bg-slate-50/60 p-2 pl-3 dark:border-blue-700 dark:bg-slate-800/40' : ''
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        {depth > 0 && (
          <span
            className="cursor-grab select-none px-1 text-slate-400 active:cursor-grabbing dark:text-slate-500"
            title="Glisser pour réordonner"
            {...dragHandlers}
          >
            ⠿
          </span>
        )}
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {depth === 0 ? 'Combiner avec' : 'Sous-groupe'}
        </span>
        <Segmented
          options={LOGIC_OPTIONS}
          value={node.logic}
          onChange={(logic) => onChange({ ...node, logic })}
          size="sm"
        />
        <InfoTip
          text={
            node.logic === 'AND'
              ? 'Toutes les conditions de ce groupe doivent être vraies.'
              : 'Au moins une condition de ce groupe doit être vraie.'
          }
        />
        {depth > 0 && (
          <button
            onClick={onRemove}
            className="ml-auto rounded-md px-2 py-1 text-sm text-red-600 hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-950/40"
            aria-label="Supprimer ce sous-groupe"
          >
            ✕
          </button>
        )}
      </div>

      {node.conditions.map((child, index) => (
        <FilterNodeView
          key={child.id}
          node={child}
          columns={columns}
          columnTypes={columnTypes}
          insights={insights}
          depth={depth + 1}
          onChange={(next) => updateChild(index, next)}
          onRemove={() => removeChild(index)}
          dragHandlers={{
            draggable: true,
            onDragStart: () => setDragIndex(index),
            onDragOver: (e) => e.preventDefault(),
            onDrop: () => {
              moveChild(dragIndex, index)
              setDragIndex(null)
            },
            onDragEnd: () => setDragIndex(null),
          }}
        />
      ))}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onChange({ ...node, conditions: [...node.conditions, newCondition(firstColumn)] })}
          className="rounded-md border border-dashed border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-500 hover:border-slate-400 hover:text-slate-700 dark:border-slate-600 dark:text-slate-400 dark:hover:text-slate-200"
        >
          + Condition
        </button>
        {depth < 3 && (
          <button
            onClick={() => onChange({ ...node, conditions: [...node.conditions, newGroup(firstColumn)] })}
            className="rounded-md border border-dashed border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-500 hover:border-slate-400 hover:text-slate-700 dark:border-slate-600 dark:text-slate-400 dark:hover:text-slate-200"
            title="Un sous-groupe joue le rôle de parenthèses dans l'expression logique."
          >
            + Sous-groupe ( … )
          </button>
        )}
      </div>
    </div>
  )
}
