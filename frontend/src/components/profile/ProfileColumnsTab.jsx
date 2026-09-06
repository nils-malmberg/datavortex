import { useState } from 'react'
import { Badge, InfoTip, Panel, StatRow, formatNumber } from '../ui/common'

/** Onglet « Profil » : fiche détaillée de chaque colonne. */
const TYPE_TONES = { integer: 'blue', float: 'blue', boolean: 'purple', datetime: 'amber', string: 'slate' }

function ColumnCard({ name, info, precision }) {
  const fmt = (v) => formatNumber(v, precision)
  const isNumeric = info.type === 'integer' || info.type === 'float'

  return (
    <Panel className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h4 className="truncate font-semibold text-slate-800 dark:text-slate-100" title={name}>
          {name}
        </h4>
        <span className="flex gap-1">
          {info.is_probable_key && (
            <Badge tone="purple">
              <span title="Toutes les valeurs sont distinctes : c'est probablement un identifiant.">clé ?</span>
            </Badge>
          )}
          {info.is_constant && (
            <Badge tone="amber">
              <span title="Une seule valeur distincte : cette colonne n'apporte aucune information.">constante</span>
            </Badge>
          )}
          <Badge tone={TYPE_TONES[info.type] || 'slate'}>{info.type}</Badge>
        </span>
      </div>

      <dl className="text-sm">
        <StatRow label="Valeurs renseignées" value={info.count} />
        <StatRow label="Manquantes" value={`${info.missing} (${info.missing_pct} %)`} />
        <StatRow
          label="Distinctes"
          value={`${info.unique} (${info.unique_pct} %)`}
          hint="Pourcentage rapporté aux valeurs renseignées."
        />
        <StatRow label="Mode" value={info.mode === null ? '—' : `${info.mode} (×${info.mode_count})`} />

        {isNumeric && (
          <>
            <div className="my-1.5 border-t border-dashed border-slate-200 dark:border-slate-700" />
            <StatRow label="Moyenne" value={fmt(info.mean)} />
            <StatRow label="Médiane" value={fmt(info.median)} />
            <StatRow label="Écart-type" value={fmt(info.std)} />
            <StatRow label="Étendue" value={`${fmt(info.min)} → ${fmt(info.max)}`} />
            <StatRow label="Q1 / Q3" value={`${fmt(info.q1)} / ${fmt(info.q3)}`} />
            <StatRow label="Asymétrie" value={fmt(info.skewness)} hint="0 = symétrique." />
            <StatRow label="Kurtosis" value={fmt(info.kurtosis)} hint="Excès de Fisher : 0 pour une loi normale." />
            <StatRow label="Zéros / négatifs" value={`${info.zeros} / ${info.negatives}`} />
          </>
        )}

        {info.type === 'string' && info.min_length !== undefined && (
          <>
            <div className="my-1.5 border-t border-dashed border-slate-200 dark:border-slate-700" />
            <StatRow label="Longueur min / max" value={`${info.min_length} / ${info.max_length}`} />
            <StatRow label="Longueur moyenne" value={fmt(info.mean_length)} />
            {info.empty_strings > 0 && <StatRow label="Chaînes vides" value={info.empty_strings} />}
          </>
        )}
      </dl>

      {isNumeric && info.shape && (
        <p className="rounded-md bg-slate-50 px-2 py-1 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
          Distribution {info.shape}.
        </p>
      )}

      {info.top_values.length > 1 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Valeurs les plus fréquentes
          </p>
          {info.top_values.slice(0, 5).map((item) => (
            <div key={item.value} className="flex items-center gap-2 text-xs">
              <span className="w-24 truncate text-slate-600 dark:text-slate-300" title={item.value}>
                {item.value}
              </span>
              <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <span
                  className="block h-full rounded-full bg-blue-500"
                  style={{ width: `${(item.count / info.top_values[0].count) * 100}%` }}
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

export default function ProfileColumnsTab({ profile, precision }) {
  const [filter, setFilter] = useState('')
  const entries = Object.entries(profile).filter(([name]) =>
    name.toLowerCase().includes(filter.trim().toLowerCase()),
  )

  return (
    <div className="flex flex-col gap-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
          Filtrer les colonnes
          <InfoTip text="Recherche par nom, utile sur les jeux de données à plusieurs dizaines de colonnes." />
        </span>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="nom de colonne"
          className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
        />
        <span className="text-xs text-slate-400 dark:text-slate-500">
          {entries.length} colonne(s) affichée(s)
        </span>
      </label>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {entries.map(([name, info]) => (
          <ColumnCard key={name} name={name} info={info} precision={precision} />
        ))}
      </div>
    </div>
  )
}
