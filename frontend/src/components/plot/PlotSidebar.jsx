import { Badge, ChipMultiSelect, FieldSelect, InfoTip, NumberField } from '../ui/common'
import { FIELD_LABELS, PLOT_GROUPS, plotConfig } from './plotCatalog'

/**
 * Colonne de gauche : choix du type de graphique puis des colonnes à tracer.
 * Les listes déroulantes sont restreintes aux colonnes compatibles avec le
 * champ, pour éviter de proposer une combinaison que le backend refusera.
 */
export default function PlotSidebar({ spec, onChange, columns, numericColumns, categoricalColumns }) {
  const config = plotConfig(spec.plot_type)

  const optionsFor = (field) => {
    if (field === 'size_by' || field === 'columns') return numericColumns
    if (field === 'group_by') return categoricalColumns
    if (config.numeric?.includes(field)) return numericColumns
    return columns
  }

  const set = (patch) => onChange({ ...spec, ...patch })

  const toggleColumn = (col) => {
    const current = spec.columns || []
    set({ columns: current.includes(col) ? current.filter((c) => c !== col) : [...current, col] })
  }

  return (
    <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-64">
      <div className="flex flex-col gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Type de graphique
        </h4>
        <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 dark:border-slate-800 dark:bg-slate-900 lg:max-h-none">
          {PLOT_GROUPS.map((group) => (
            <div key={group.label} className="mb-1">
              <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                {group.label}
              </p>
              {group.types.map((type) => (
                <button
                  key={type.value}
                  onClick={() => set({ plot_type: type.value })}
                  title={type.hint}
                  className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                    spec.plot_type === type.value
                      ? 'bg-blue-600 text-white dark:bg-blue-500'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                  }`}
                >
                  <span className="flex-1 truncate">{type.label}</span>
                  {type.isNew && (
                    <span
                      className={`rounded px-1 text-[9px] font-bold uppercase ${
                        spec.plot_type === type.value
                          ? 'bg-white/25 text-white'
                          : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300'
                      }`}
                    >
                      new
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>
        {config.hint && (
          <p className="rounded-md bg-slate-50 px-2 py-1.5 text-xs text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
            {config.hint}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Données</h4>
        {['x', 'y', 'z', 'group_by', 'color_by', 'size_by'].map((field) =>
          config.fields.includes(field) ? (
            <FieldSelect
              key={field}
              label={FIELD_LABELS[field]}
              value={spec[field]}
              onChange={(v) => set({ [field]: v })}
              options={optionsFor(field)}
              allowEmpty={!config.required.includes(field)}
            />
          ) : null,
        )}
        {config.fields.includes('bins') && (
          <NumberField
            label={FIELD_LABELS.bins}
            value={spec.bins}
            onChange={(v) => set({ bins: v })}
            min={2}
            max={200}
          />
        )}
        {config.fields.includes('columns') && (
          <div className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1 text-sm font-medium text-slate-600 dark:text-slate-300">
              {FIELD_LABELS.columns}
              <InfoTip text="Sans sélection, toutes les colonnes numériques sont utilisées." />
            </span>
            <ChipMultiSelect options={numericColumns} selected={spec.columns || []} onToggle={toggleColumn} />
          </div>
        )}
        {config.required.length === 0 && <Badge tone="slate">Aucun champ obligatoire</Badge>}
      </div>
    </aside>
  )
}
