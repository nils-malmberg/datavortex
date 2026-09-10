import { BUTTON_CLASS, FieldSelect, INPUT_CLASS } from '../ui/common'
import { MAX_SERIES, SERIES_PLOT_TYPES } from './plotCatalog'

// Même palette que le backend (app/plotting.py) : la couleur affichée dans le
// sélecteur avant toute personnalisation correspond déjà à celle du graphique.
const DEFAULT_PALETTE = [
  '#4C78A8', '#F58518', '#54A24B', '#E45756', '#72B7B2',
  '#EECA3B', '#B279A2', '#FF9DA6', '#9D755D', '#BAB0AC',
]

let nextSeriesId = 1
export function makeSeries(yColumn, index = 0) {
  return {
    id: `series_${nextSeriesId++}`,
    y_column: yColumn || '',
    y_axis: 'left',
    plot_type: 'scatter',
    name: '',
    color: DEFAULT_PALETTE[index % DEFAULT_PALETTE.length],
  }
}

/**
 * Panneau de configuration du mode multi-séries (Phase 10.1).
 *
 * Ne s'occupe que de la configuration : l'aperçu, le chargement des colonnes
 * et les options avancées appartiennent à l'atelier qui l'accueille, pour que
 * les trois modes partagent exactement la même chaîne de rendu.
 */
export default function MultiSeriesEditor({ spec, onChange, columns, numericColumns }) {
  const series = spec.series || []
  const set = (patch) => onChange({ ...spec, ...patch })
  const setSeries = (next) => set({ series: next })

  const addSeries = () => {
    if (series.length >= MAX_SERIES) return
    const unused = numericColumns.find((c) => !series.some((s) => s.y_column === c))
    setSeries([...series, makeSeries(unused || numericColumns[0], series.length)])
  }

  const updateSeries = (id, patch) =>
    setSeries(series.map((s) => (s.id === id ? { ...s, ...patch } : s)))

  const hasSecondaryAxis = series.some((s) => s.y_axis === 'right')

  return (
    <div className="flex w-full shrink-0 flex-col gap-4 lg:w-72">
      <FieldSelect
        label="Axe X (commun aux séries)"
        value={spec.x}
        onChange={(v) => set({ x: v })}
        options={columns}
        allowEmpty
        emptyLabel="Choisir une colonne…"
      />

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Séries ({series.length})
          </h4>
          {hasSecondaryAxis && (
            <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
              axe Y secondaire actif
            </span>
          )}
        </div>

        {series.length === 0 && (
          <p className="rounded-md bg-slate-50 px-2 py-1.5 text-xs text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
            Ajoutez une série pour commencer.
          </p>
        )}

        {series.map((s) => (
          <div
            key={s.id}
            className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-2.5 dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={s.color}
                onChange={(e) => updateSeries(s.id, { color: e.target.value })}
                title="Couleur de la série"
                className="h-7 w-7 shrink-0 cursor-pointer rounded border border-slate-300 dark:border-slate-600"
              />
              <input
                type="text"
                value={s.name}
                onChange={(e) => updateSeries(s.id, { name: e.target.value })}
                placeholder={s.y_column || 'Nom de la série'}
                className={`${INPUT_CLASS} min-w-0 flex-1`}
              />
              <button
                onClick={() => setSeries(series.filter((item) => item.id !== s.id))}
                title="Retirer cette série"
                className="shrink-0 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40"
              >
                ✕
              </button>
            </div>
            <FieldSelect
              label="Colonne Y"
              value={s.y_column}
              onChange={(v) => updateSeries(s.id, { y_column: v })}
              options={numericColumns}
              allowEmpty
              emptyLabel="Choisir…"
            />
            <div className="flex flex-wrap gap-2">
              <FieldSelect
                label="Type"
                value={s.plot_type}
                onChange={(v) => updateSeries(s.id, { plot_type: v })}
                options={SERIES_PLOT_TYPES}
              />
              <FieldSelect
                label="Axe Y"
                value={s.y_axis}
                onChange={(v) => updateSeries(s.id, { y_axis: v })}
                options={[
                  { value: 'left', label: 'Gauche' },
                  { value: 'right', label: 'Droite' },
                ]}
              />
            </div>
          </div>
        ))}

        <button onClick={addSeries} disabled={series.length >= MAX_SERIES} className={`${BUTTON_CLASS} self-start`}>
          + Ajouter une série
        </button>
      </div>
    </div>
  )
}
