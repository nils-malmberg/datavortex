import { BUTTON_CLASS, FieldSelect, INPUT_CLASS, NumberField } from '../ui/common'
import { GRID_PRESETS, MAX_GRID_SIDE, SINGLE_VARIABLE_TYPES, SUBPLOT_TYPES } from './plotCatalog'

const DEFAULT_PALETTE = [
  '#4C78A8', '#F58518', '#54A24B', '#E45756', '#72B7B2',
  '#EECA3B', '#B279A2', '#FF9DA6', '#9D755D', '#BAB0AC',
]

let nextSubplotId = 1
export function makeSubplot(index = 0, defaults = {}) {
  return {
    id: `subplot_${nextSubplotId++}`,
    plot_type: 'scatter',
    x: '',
    y: '',
    title: '',
    color: DEFAULT_PALETTE[index % DEFAULT_PALETTE.length],
    ...defaults,
  }
}

/**
 * Panneau de configuration du mode grille (Phase 10.1).
 *
 * Redimensionner la grille ne détruit pas les cases déjà configurées : passer
 * de 2x2 à 3x3 conserve les quatre premières et complète avec des cases
 * vierges. Perdre son travail en changeant d'avis sur la taille serait le
 * genre de détail qui décourage d'utiliser la fonctionnalité.
 */
export default function SubplotsEditor({ spec, onChange, columns, numericColumns }) {
  const grid = spec.subplot_grid || { rows: 2, cols: 2 }
  const subplots = spec.subplots || []
  const capacity = grid.rows * grid.cols

  const set = (patch) => onChange({ ...spec, ...patch })

  const resize = (rows, cols) => {
    const safeRows = Math.max(1, Math.min(MAX_GRID_SIDE, rows || 1))
    const safeCols = Math.max(1, Math.min(MAX_GRID_SIDE, cols || 1))
    const needed = safeRows * safeCols
    const next = subplots.slice(0, needed)
    while (next.length < needed) next.push(makeSubplot(next.length))
    set({ subplot_grid: { rows: safeRows, cols: safeCols }, subplots: next })
  }

  const updateSubplot = (id, patch) =>
    set({ subplots: subplots.map((s) => (s.id === id ? { ...s, ...patch } : s)) })

  const visible = subplots.slice(0, capacity)

  return (
    <div className="flex w-full shrink-0 flex-col gap-4 lg:w-72">
      <div className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Taille de la grille
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {GRID_PRESETS.map((preset) => {
            const isActive = grid.rows === preset.rows && grid.cols === preset.cols
            return (
              <button
                key={`${preset.rows}x${preset.cols}`}
                onClick={() => resize(preset.rows, preset.cols)}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
                    : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300'
                }`}
              >
                {preset.rows}×{preset.cols}
              </button>
            )
          })}
        </div>
        <div className="flex items-end gap-2">
          <NumberField label="Lignes" value={grid.rows} onChange={(v) => resize(v, grid.cols)} min={1} max={MAX_GRID_SIDE} />
          <NumberField label="Colonnes" value={grid.cols} onChange={(v) => resize(grid.rows, v)} min={1} max={MAX_GRID_SIDE} />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Cases ({visible.length})
        </h4>
        {visible.map((s, index) => {
          const isSingleVariable = SINGLE_VARIABLE_TYPES.includes(s.plot_type)
          return (
            <div
              key={s.id}
              className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-2.5 dark:border-slate-800 dark:bg-slate-900"
            >
              <div className="flex items-center gap-2">
                <span className="shrink-0 rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-200">
                  {index + 1}
                </span>
                <input
                  type="color"
                  value={s.color}
                  onChange={(e) => updateSubplot(s.id, { color: e.target.value })}
                  title="Couleur"
                  className="h-7 w-7 shrink-0 cursor-pointer rounded border border-slate-300 dark:border-slate-600"
                />
                <input
                  type="text"
                  value={s.title}
                  onChange={(e) => updateSubplot(s.id, { title: e.target.value })}
                  placeholder={`Graphique ${index + 1}`}
                  className={`${INPUT_CLASS} min-w-0 flex-1`}
                />
              </div>
              <FieldSelect
                label="Type"
                value={s.plot_type}
                onChange={(v) => updateSubplot(s.id, { plot_type: v })}
                options={SUBPLOT_TYPES}
              />
              {!isSingleVariable && (
                <FieldSelect
                  label="Axe X"
                  value={s.x}
                  onChange={(v) => updateSubplot(s.id, { x: v })}
                  options={columns}
                  allowEmpty
                  emptyLabel="Choisir…"
                />
              )}
              <FieldSelect
                label={isSingleVariable ? 'Colonne' : 'Axe Y'}
                value={s.y}
                onChange={(v) => updateSubplot(s.id, { y: v })}
                options={numericColumns}
                allowEmpty
                emptyLabel="Choisir…"
              />
            </div>
          )
        })}
        {visible.length < capacity && (
          <button onClick={() => resize(grid.rows, grid.cols)} className={`${BUTTON_CLASS} self-start`}>
            Compléter la grille
          </button>
        )}
      </div>
    </div>
  )
}
