import ThemedPlot from '../ui/ThemedPlot'
import { Badge, InfoTip, Panel, StatCard, formatNumber } from '../ui/common'
import ResultTable from '../ui/ResultTable'

/**
 * Onglet « Qualité » : score global, détail par dimension, doublons exacts et
 * variantes d'écriture. Chaque indicateur est accompagné de sa définition —
 * un score n'a de valeur que si l'on sait ce qu'il mesure.
 */
const GRADE_TONES = {
  excellent: 'green',
  bon: 'green',
  correct: 'amber',
  fragile: 'amber',
  problématique: 'red',
}

function scoreColor(score) {
  if (score >= 98) return '#54A24B'
  if (score >= 90) return '#EECA3B'
  if (score >= 75) return '#F58518'
  return '#E45756'
}

export default function ProfileQualityTab({ quality, duplicates, missing }) {
  const dimensions = Object.entries(quality.dimensions)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel className="flex flex-col items-center justify-center gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Propreté au niveau cellule
          </p>
          <p className="text-5xl font-bold tabular-nums" style={{ color: scoreColor(quality.score) }}>
            {quality.score}
          </p>
          <Badge tone={GRADE_TONES[quality.grade] || 'slate'}>{quality.grade}</Badge>
          <p className="px-2 text-center text-xs text-slate-500 dark:text-slate-400">{quality.score_definition}</p>
          <p className="px-2 text-center text-xs text-slate-500 dark:text-slate-400">{quality.grade_definition}</p>
        </Panel>

        <div className="flex flex-col gap-3 lg:col-span-2">
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              label="Colonnes avec anomalies"
              value={`${quality.n_columns_with_issues} / ${quality.n_columns}`}
              sub={quality.columns_with_issues.slice(0, 4).join(', ') || 'aucune'}
              tone={quality.n_columns_with_issues === 0 ? 'green' : 'amber'}
            />
            <StatCard
              label="Lignes dupliquées"
              value={duplicates.duplicate_rows}
              sub={`${duplicates.duplicate_rows_pct} % du jeu`}
              tone={duplicates.duplicate_rows === 0 ? 'green' : 'amber'}
            />
          </div>
          <Panel className="flex flex-col gap-3">
            {dimensions.map(([key, dim]) => (
              <div key={key} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="flex items-center gap-1 font-medium text-slate-700 dark:text-slate-200">
                    {dim.label}
                    <InfoTip text={dim.definition} />
                    {key === quality.weakest_dimension && <Badge tone="amber">maillon faible</Badge>}
                  </span>
                  <span className="tabular-nums text-slate-600 dark:text-slate-300">{dim.score} %</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${dim.score}%`, backgroundColor: scoreColor(dim.score) }}
                  />
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{dim.detail}</p>
              </div>
            ))}
          </Panel>
        </div>
      </div>

      {missing.total_missing > 0 && (
        <ThemedPlot
          height={Math.max(260, 60 + missing.matrix.columns.length * 26)}
          exportName="patterns_manquants"
          data={[
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
          ]}
          layout={{
            title: `Structure des valeurs manquantes${missing.matrix.sampled ? ' (échantillon de lignes)' : ''}`,
            margin: { t: 50, r: 20, b: 90, l: 60 },
            xaxis: { tickangle: -45, automargin: true },
            yaxis: { title: 'Ligne', autorange: 'reversed' },
          }}
        />
      )}

      <Panel className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Détail par colonne</h4>
        <ResultTable
          columns={[
            'column', 'type', 'missing', 'type_mismatches',
            'sentinel_values', 'inconsistent_formatting', 'extreme_values',
          ]}
          rows={quality.per_column}
          highlightColumns={['column']}
          precision={0}
          maxHeight="320px"
        />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          <strong>type_mismatches</strong> : valeurs incompatibles avec le type de la colonne ·{' '}
          <strong>sentinel_values</strong> : marqueurs d&apos;absence déguisés (« N/A », « -999 ») ·{' '}
          <strong>inconsistent_formatting</strong> : libellés en variante de casse ou d&apos;espaces ·{' '}
          <strong>extreme_values</strong> : au-delà de 3·IQR.
        </p>
      </Panel>

      <Panel className="flex flex-col gap-2">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          Doublons et variantes d&apos;écriture
          <InfoTip text="Deux détections : les copies exactes de lignes, et les libellés qui désignent probablement la même chose." />
        </h4>
        {duplicates.duplicate_rows === 0 && duplicates.fuzzy_groups.length === 0 ? (
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            Aucune ligne dupliquée ni variante d&apos;écriture détectée.
          </p>
        ) : (
          <>
            {duplicates.duplicate_rows > 0 && (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {duplicates.duplicate_rows} ligne(s) sont des copies exactes ({duplicates.rows_involved} lignes
                impliquées au total en comptant les originaux).
              </p>
            )}
            {duplicates.fuzzy_groups.length > 0 && (
              <div className="flex flex-col gap-2">
                {duplicates.fuzzy_groups.map((group, i) => (
                  <div key={i} className="rounded-md bg-slate-50 p-2 text-sm dark:bg-slate-800/60">
                    <p className="flex flex-wrap items-center gap-2 text-slate-700 dark:text-slate-200">
                      <Badge tone="blue">{group.column}</Badge>
                      <Badge tone="slate">
                        {group.kind === 'casse_ou_espaces' ? 'casse / espaces' : 'orthographe proche'}
                      </Badge>
                      <span>
                        forme majoritaire : <strong>{group.canonical}</strong>
                      </span>
                    </p>
                    <p className="mt-1 flex flex-wrap gap-1.5">
                      {group.variants.map((v) => (
                        <span
                          key={v.value}
                          className={`rounded px-1.5 py-0.5 text-xs ${
                            v.value === group.canonical
                              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                              : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                          }`}
                        >
                          « {v.value} » × {formatNumber(v.count, 0)}
                        </span>
                      ))}
                    </p>
                  </div>
                ))}
              </div>
            )}
            {duplicates.fuzzy_limit_reached && (
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Certaines colonnes textuelles ont trop de valeurs distinctes pour une comparaison exhaustive :
                elles ont été écartées de la recherche de variantes.
              </p>
            )}
          </>
        )}
      </Panel>
    </div>
  )
}
