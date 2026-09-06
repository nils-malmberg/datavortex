import { Badge, CopyButton, Panel, StatRow, formatNumber } from '../ui/common'

/**
 * Onglet "Summary" : statistiques descriptives par colonne.
 * Le mode avancé révèle les indicateurs attendus par un statisticien
 * (erreur standard, coefficient de variation, MAD, intervalles de confiance).
 */
const TYPE_TONES = {
  integer: 'blue',
  float: 'blue',
  boolean: 'purple',
  datetime: 'amber',
  string: 'slate',
}

function NumericCard({ name, stats, advanced, precision }) {
  const fmt = (v) => formatNumber(v, precision)
  const ci = stats.ci95

  return (
    <Panel className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h4 className="group flex min-w-0 items-center gap-1 font-semibold text-slate-800 dark:text-slate-100">
          <span className="truncate" title={name}>
            {name}
          </span>
          <CopyButton value={name} title="Copier le nom de la colonne" />
        </h4>
        <Badge tone="blue">numérique</Badge>
      </div>

      <dl className="text-sm">
        <StatRow label="N" value={stats.count} />
        <StatRow label="Moyenne" value={fmt(stats.mean)} />
        <StatRow label="Médiane" value={fmt(stats.median)} />
        <StatRow label="Écart-type" value={fmt(stats.std)} />
        <StatRow label="Min" value={fmt(stats.min)} />
        <StatRow label="Max" value={fmt(stats.max)} />

        {advanced && (
          <>
            <div className="my-1.5 border-t border-dashed border-slate-200 dark:border-slate-700" />
            <StatRow
              label="Erreur standard"
              value={fmt(stats.std_error)}
              hint="Écart-type de la moyenne : σ / √n. Mesure la précision de la moyenne estimée."
            />
            <StatRow
              label="CV"
              value={stats.cv_percent === null ? 'n/a' : `${fmt(stats.cv_percent)} %`}
              hint="Coefficient de variation = σ / |moyenne|. Dispersion relative, comparable entre variables d'unités différentes. Non défini si la moyenne est proche de 0."
            />
            <StatRow label="Q1" value={fmt(stats.q1)} />
            <StatRow label="Q3" value={fmt(stats.q3)} />
            <StatRow label="IQR" value={fmt(stats.iqr)} hint="Écart interquartile = Q3 − Q1." />
            <StatRow
              label="MAD"
              value={fmt(stats.mad)}
              hint="Median Absolute Deviation : dispersion robuste, insensible aux valeurs extrêmes."
            />
            <StatRow label="P5 / P95" value={`${fmt(stats.p05)} / ${fmt(stats.p95)}`} />
            <StatRow
              label="IC 95 %"
              value={ci ? `[${fmt(ci.low)} ; ${fmt(ci.high)}]` : '—'}
              hint="Intervalle de confiance à 95 % de la moyenne (loi de Student)."
            />
            <StatRow
              label="IC 99 %"
              value={stats.ci99 ? `[${fmt(stats.ci99.low)} ; ${fmt(stats.ci99.high)}]` : '—'}
              hint="Intervalle de confiance à 99 % de la moyenne."
            />
            <StatRow
              label="Outliers (IQR)"
              value={`${stats.outlier_count} hors [${fmt(stats.lower_fence)} ; ${fmt(stats.upper_fence)}]`}
              hint="Valeurs au-delà de Q1 − 1,5·IQR ou Q3 + 1,5·IQR (règle de Tukey)."
            />
          </>
        )}
      </dl>
    </Panel>
  )
}

function CategoricalCard({ name, summary, precision }) {
  const { type, stats, missing_count: missingCount, missing_pct: missingPct } = summary
  return (
    <Panel className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h4 className="group flex min-w-0 items-center gap-1 font-semibold text-slate-800 dark:text-slate-100">
          <span className="truncate" title={name}>
            {name}
          </span>
          <CopyButton value={name} title="Copier le nom de la colonne" />
        </h4>
        <Badge tone={TYPE_TONES[type] || 'slate'}>{type}</Badge>
      </div>
      <dl className="text-sm">
        {type === 'boolean' ? (
          <>
            <StatRow label="Vrai" value={stats.true_count} />
            <StatRow label="Faux" value={stats.false_count} />
            <StatRow label="% vrai" value={`${formatNumber(stats.pct_true, precision)} %`} />
          </>
        ) : (
          <>
            <StatRow label="N" value={stats.count} />
            <StatRow label="Valeurs distinctes" value={stats.unique} />
            <StatRow label="Mode" value={stats.mode ?? '—'} />
          </>
        )}
        {missingCount > 0 && <StatRow label="Manquantes" value={`${missingCount} (${missingPct} %)`} />}
      </dl>
      {stats.top_values?.length > 1 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Valeurs les plus fréquentes
          </p>
          {stats.top_values.slice(0, 5).map((item) => (
            <div key={item.value} className="flex items-center gap-2 text-xs">
              <span className="w-28 truncate text-slate-600 dark:text-slate-300" title={item.value}>
                {item.value}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <span
                  className="block h-full rounded-full bg-blue-500"
                  style={{ width: `${(item.count / stats.top_values[0].count) * 100}%` }}
                />
              </span>
              <span className="w-10 text-right tabular-nums text-slate-500 dark:text-slate-400">{item.count}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

export default function StatsSummaryTab({ advancedStats, basicStats, columnFilter, advanced, precision }) {
  const numericCols = advancedStats.numeric_columns
  const allCols = Object.keys(basicStats?.columns || {})
  const categoricalCols = allCols.filter((c) => !numericCols.includes(c))

  const showNumeric = columnFilter !== 'categorical'
  const showCategorical = columnFilter !== 'numeric'

  const visible = [
    ...(showNumeric ? numericCols.map((c) => ({ name: c, kind: 'numeric' })) : []),
    ...(showCategorical ? categoricalCols.map((c) => ({ name: c, kind: 'categorical' })) : []),
  ]

  if (visible.length === 0) {
    return (
      <p className="p-4 text-sm text-slate-500 dark:text-slate-400">
        Aucune colonne ne correspond au filtre sélectionné.
      </p>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {visible.map(({ name, kind }) =>
        kind === 'numeric' ? (
          <NumericCard
            key={name}
            name={name}
            stats={advancedStats.summary[name]}
            advanced={advanced}
            precision={precision}
          />
        ) : (
          <CategoricalCard key={name} name={name} summary={basicStats.columns[name]} precision={precision} />
        ),
      )}
    </div>
  )
}
