import { useMemo, useState } from 'react'
import ThemedPlot from '../ui/ThemedPlot'
import ResultTable from '../ui/ResultTable'
import { Badge, EmptyState, FieldSelect, InfoTip, Panel, StatCard, formatNumber } from '../ui/common'

/**
 * Onglet « Anomalies » : trois détections complémentaires — valeurs extrêmes
 * par colonne (IQR et z-score), valeurs incompatibles avec le type, et lignes
 * atypiques par la combinaison de leurs valeurs (Isolation Forest).
 */
export default function ProfileAnomaliesTab({ anomalies, precision }) {
  const withOutliers = anomalies.per_column.filter((c) => c.outliers)
  const withMismatches = anomalies.per_column.filter((c) => c.type_mismatch_count || c.sentinel_count)
  const [selected, setSelected] = useState(withOutliers[0]?.column || '')

  const current = useMemo(
    () => withOutliers.find((c) => c.column === selected) || withOutliers[0],
    [withOutliers, selected],
  )

  const multivariate = anomalies.multivariate

  return (
    <div className="flex flex-col gap-4">
      {withMismatches.length > 0 && (
        <Panel className="flex flex-col gap-2">
          <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Valeurs non conformes
            <InfoTip text="Valeurs qui ne respectent pas le type de leur colonne, ou marqueurs d'absence déguisés." />
          </h4>
          {withMismatches.map((col) => (
            <div key={col.column} className="flex flex-wrap items-center gap-2 text-sm">
              <Badge tone="blue">{col.column}</Badge>
              {col.type_mismatch_count > 0 && (
                <span className="text-slate-700 dark:text-slate-200">
                  {col.type_mismatch_count} valeur(s) incompatible(s) avec le type « {col.type} »
                  {col.type_mismatch_examples?.length > 0 && (
                    <span className="text-slate-500 dark:text-slate-400">
                      {' '}
                      — ex. {col.type_mismatch_examples.map((v) => `« ${v} »`).join(', ')}
                    </span>
                  )}
                </span>
              )}
              {col.sentinel_count > 0 && (
                <Badge tone="amber">{col.sentinel_count} marqueur(s) d&apos;absence</Badge>
              )}
            </div>
          ))}
        </Panel>
      )}

      {withOutliers.length === 0 ? (
        <EmptyState>Aucune colonne numérique exploitable pour la détection de valeurs extrêmes.</EmptyState>
      ) : (
        <Panel className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end gap-4">
            <FieldSelect
              label="Colonne analysée"
              value={current?.column || ''}
              onChange={setSelected}
              options={withOutliers.map((c) => c.column)}
            />
            <StatCard
              label={current?.outliers.rule === 'iqr' ? 'Règle de Tukey (IQR)' : 'Règle robuste'}
              value={current?.outliers.iqr_count ?? 0}
              sub={`${current?.outliers.iqr_pct ?? 0} % de la colonne`}
              tone={current?.outliers.iqr_count ? 'amber' : 'green'}
            />
            <StatCard
              label="Z-score > 3"
              value={current?.outliers.zscore_count ?? 0}
              sub={`${current?.outliers.zscore_pct ?? 0} % de la colonne`}
              tone={current?.outliers.zscore_count ? 'amber' : 'green'}
            />
          </div>

          {current && (
            <>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Règle appliquée : {current.outliers.rule_label}. Bornes : [
                {formatNumber(current.outliers.lower_fence, precision)} ;{' '}
                {formatNumber(current.outliers.upper_fence, precision)}]. Les deux méthodes ne coïncident pas
                toujours : le z-score suppose une distribution proche de la normale, l&apos;IQR non.
              </p>
              {current.outliers.examples.length > 0 && (
                <ThemedPlot
                  height={260}
                  exportName={`anomalies_${current.column}`}
                  data={[
                    {
                      type: 'scatter',
                      mode: 'markers',
                      x: current.outliers.examples,
                      y: current.outliers.examples.map(() => 0),
                      marker: { color: '#E45756', size: 11, symbol: 'x' },
                      name: 'valeurs extrêmes',
                      hovertemplate: '%{x}<extra></extra>',
                    },
                  ]}
                  layout={{
                    title: `Valeurs les plus extrêmes de ${current.column}`,
                    margin: { t: 50, r: 20, b: 50, l: 40 },
                    xaxis: { title: current.column },
                    yaxis: { showticklabels: false, zeroline: true, range: [-1, 1] },
                    shapes: [
                      {
                        type: 'line', x0: current.outliers.lower_fence, x1: current.outliers.lower_fence,
                        y0: -1, y1: 1, line: { color: '#94a3b8', dash: 'dash' },
                      },
                      {
                        type: 'line', x0: current.outliers.upper_fence, x1: current.outliers.upper_fence,
                        y0: -1, y1: 1, line: { color: '#94a3b8', dash: 'dash' },
                      },
                    ],
                    showlegend: false,
                  }}
                />
              )}
            </>
          )}
        </Panel>
      )}

      <Panel className="flex flex-col gap-3">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          Lignes atypiques (Isolation Forest)
          <InfoTip text="Détection multivariée : une ligne peut être anormale par la combinaison de ses valeurs même si chacune, prise seule, est banale." />
        </h4>
        {!multivariate.available ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">{multivariate.reason}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <StatCard
                label="Lignes signalées"
                value={multivariate.anomaly_count}
                sub={`${multivariate.anomaly_pct} % de ${multivariate.rows_evaluated} lignes évaluées`}
                tone="amber"
              />
              <div className="flex flex-wrap gap-1">
                {multivariate.columns.map((c) => (
                  <Badge key={c} tone="blue">
                    {c}
                  </Badge>
                ))}
              </div>
              {multivariate.sampled && <Badge tone="slate">échantillon</Badge>}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">{multivariate.note}</p>
            <ResultTable
              columns={['row', 'score', ...multivariate.columns]}
              rows={multivariate.examples.map((e) => ({ row: e.row, score: e.score, ...e.values }))}
              highlightColumns={['row']}
              precision={precision}
              maxHeight="280px"
              emptyMessage="Aucune ligne atypique détectée."
            />
          </>
        )}
      </Panel>
    </div>
  )
}
