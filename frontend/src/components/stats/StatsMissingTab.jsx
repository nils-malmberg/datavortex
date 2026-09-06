import ThemedPlot from '../ui/ThemedPlot'
import { Badge, EmptyState, Panel, StatCard, formatNumber } from '../ui/common'

/**
 * Onglet "Missing Data" : volume manquant par colonne, structure des trous
 * (patterns) et suggestion d'imputation justifiée pour chaque colonne.
 */
const METHOD_TONES = {
  none: 'green',
  mean: 'blue',
  median: 'blue',
  mode: 'purple',
  interpolate: 'amber',
  constant: 'amber',
  drop_column: 'red',
}

export default function StatsMissingTab({ missing, precision }) {
  const withMissing = missing.by_column.filter((c) => c.missing_count > 0)

  const barData = [
    {
      type: 'bar',
      x: missing.by_column.map((c) => c.missing_pct),
      y: missing.by_column.map((c) => c.column),
      orientation: 'h',
      marker: {
        color: missing.by_column.map((c) =>
          c.missing_pct > 60 ? '#E45756' : c.missing_pct > 20 ? '#F58518' : c.missing_pct > 0 ? '#EECA3B' : '#54A24B',
        ),
      },
      hovertemplate: '%{y}<br>%{x:.2f} % manquant<extra></extra>',
    },
  ]

  const heatmapData = [
    {
      type: 'heatmap',
      z: missing.matrix.rows,
      x: missing.matrix.columns,
      y: missing.matrix.row_labels,
      colorscale: [
        [0, '#e2e8f0'],
        [1, '#E45756'],
      ],
      showscale: false,
      hovertemplate: 'ligne %{y} · %{x}<br>%{z}<extra></extra>',
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Cellules manquantes"
          value={missing.total_missing}
          sub={`${missing.total_missing_pct} % du tableau`}
          tone={missing.total_missing === 0 ? 'green' : 'amber'}
        />
        <StatCard
          label="Lignes complètes"
          value={missing.complete_rows}
          sub={`sur ${missing.n_rows} lignes`}
          tone={missing.complete_rows === missing.n_rows ? 'green' : 'slate'}
        />
        <StatCard label="Colonnes touchées" value={missing.columns_with_missing} sub={`sur ${missing.n_columns}`} />
        <StatCard label="Patterns distincts" value={missing.patterns.length} sub="combinaisons de trous" />
      </div>

      {missing.total_missing === 0 ? (
        <EmptyState>
          Aucune valeur manquante dans ce jeu de données : les {missing.n_rows} lignes sont complètes.
        </EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <ThemedPlot
              height={Math.max(280, 60 + missing.by_column.length * 26)}
              exportName="valeurs_manquantes_par_colonne"
              data={barData}
              layout={{
                title: 'Valeurs manquantes par colonne',
                margin: { t: 50, r: 20, b: 50, l: 130 },
                xaxis: { title: '% manquant', range: [0, 100] },
                yaxis: { automargin: true, autorange: 'reversed' },
              }}
            />
            <ThemedPlot
              height={Math.max(280, 60 + missing.by_column.length * 26)}
              exportName="patterns_valeurs_manquantes"
              data={heatmapData}
              layout={{
                title: `Carte des valeurs manquantes${missing.matrix.sampled ? ' (échantillon de lignes)' : ''}`,
                margin: { t: 50, r: 20, b: 90, l: 60 },
                xaxis: { tickangle: -45, automargin: true },
                yaxis: { title: 'Ligne', autorange: 'reversed' },
              }}
            />
          </div>

          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Structures de valeurs manquantes
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Des colonnes systématiquement manquantes ensemble signalent une cause commune (champ optionnel d&apos;un
              même formulaire, jointure incomplète) plutôt que des trous aléatoires.
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                    <th className="py-1 pr-4 font-medium">Colonnes manquantes</th>
                    <th className="py-1 pr-4 font-medium">Lignes</th>
                    <th className="py-1 font-medium">Part</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {missing.patterns.map((pattern, i) => (
                    <tr key={i}>
                      <td className="py-1.5 pr-4">
                        {pattern.is_complete ? (
                          <Badge tone="green">ligne complète</Badge>
                        ) : (
                          <span className="flex flex-wrap gap-1">
                            {pattern.columns_missing.map((c) => (
                              <Badge key={c} tone="red">
                                {c}
                              </Badge>
                            ))}
                          </span>
                        )}
                      </td>
                      <td className="py-1.5 pr-4 tabular-nums text-slate-700 dark:text-slate-200">{pattern.count}</td>
                      <td className="py-1.5 tabular-nums text-slate-600 dark:text-slate-300">
                        {formatNumber(pattern.pct, Math.min(precision, 2))} %
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Imputation suggérée</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                    <th className="py-1 pr-4 font-medium">Colonne</th>
                    <th className="py-1 pr-4 font-medium">Manquantes</th>
                    <th className="py-1 pr-4 font-medium">Méthode</th>
                    <th className="py-1 font-medium">Pourquoi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {withMissing.map((col) => (
                    <tr key={col.column}>
                      <td className="py-1.5 pr-4 font-medium text-slate-700 dark:text-slate-200">{col.column}</td>
                      <td className="py-1.5 pr-4 tabular-nums text-slate-600 dark:text-slate-300">
                        {col.missing_count} ({col.missing_pct} %)
                      </td>
                      <td className="py-1.5 pr-4">
                        <Badge tone={METHOD_TONES[col.suggestion.method] || 'slate'}>{col.suggestion.label}</Badge>
                      </td>
                      <td className="py-1.5 text-slate-600 dark:text-slate-300">{col.suggestion.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  )
}
