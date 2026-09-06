import { useEffect, useMemo, useState } from 'react'
import ThemedPlot from '../ui/ThemedPlot'
import {
  Badge,
  EmptyState,
  FieldSelect,
  Panel,
  StatRow,
  formatNumber,
  formatPValue,
} from '../ui/common'

/**
 * Onglet "Distributions" : forme de la distribution, tests de normalité,
 * loi ajustée et Q-Q plot contre la loi normale.
 */
const LAW_LABELS = {
  normal: 'Normale',
  lognormal: 'Log-normale',
  exponential: 'Exponentielle',
  uniform: 'Uniforme',
  gamma: 'Gamma',
}

export default function StatsDistributionsTab({ distributions, precision }) {
  const columns = useMemo(() => Object.keys(distributions || {}), [distributions])
  const [selected, setSelected] = useState(columns[0] || '')

  useEffect(() => {
    if (columns.length > 0 && !columns.includes(selected)) setSelected(columns[0])
  }, [columns, selected])

  if (columns.length === 0) {
    return <EmptyState>Aucune colonne numérique à analyser dans ce jeu de données.</EmptyState>
  }

  const info = distributions[selected]
  if (!info) return null

  if (!info.usable) {
    return (
      <div className="flex flex-col gap-4">
        <FieldSelect label="Colonne" value={selected} onChange={setSelected} options={columns} />
        <EmptyState>{info.message}</EmptyState>
      </div>
    )
  }

  const qq = info.qq_plot
  const line =
    qq.theoretical.length > 1
      ? {
          x: [qq.theoretical[0], qq.theoretical[qq.theoretical.length - 1]],
          y: [
            qq.intercept + qq.slope * qq.theoretical[0],
            qq.intercept + qq.slope * qq.theoretical[qq.theoretical.length - 1],
          ],
        }
      : { x: [], y: [] }

  const shapiro = info.normality?.shapiro
  const dagostino = info.normality?.dagostino
  const anderson = info.normality?.anderson

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <FieldSelect label="Colonne analysée" value={selected} onChange={setSelected} options={columns} />
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={info.is_normal ? 'green' : 'amber'}>
            {info.is_normal ? 'Compatible avec une loi normale' : 'Non normale'}
          </Badge>
          {info.detected_law ? (
            <Badge tone="blue">Loi ajustée : {LAW_LABELS[info.detected_law] || info.detected_law}</Badge>
          ) : (
            <Badge tone="slate">Aucune loi usuelle ne convient</Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Forme de la distribution</h4>
            <dl className="text-sm">
              <StatRow label="N" value={info.count} />
              <StatRow
                label="Asymétrie (skewness)"
                value={formatNumber(info.skewness, precision)}
                hint="0 = symétrique. Positif = queue étalée vers la droite, négatif = vers la gauche."
              />
              <StatRow
                label="Kurtosis (excès)"
                value={formatNumber(info.kurtosis, precision)}
                hint="Excès de kurtosis de Fisher : 0 pour une loi normale. Positif = queues épaisses."
              />
            </dl>
            <p className="rounded-md bg-slate-50 p-2 text-sm text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
              {info.skewness_interpretation}. {info.kurtosis_interpretation}.
            </p>
          </Panel>

          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Tests de normalité</h4>
            <dl className="text-sm">
              {shapiro && (
                <StatRow
                  label="Shapiro-Wilk"
                  value={`W = ${formatNumber(shapiro.statistic, precision)} · p = ${formatPValue(shapiro.p_value)}`}
                  hint="Test de référence pour la normalité. H₀ : l'échantillon suit une loi normale."
                />
              )}
              {dagostino && (
                <StatRow
                  label="D'Agostino-Pearson"
                  value={`K² = ${formatNumber(dagostino.statistic, precision)} · p = ${formatPValue(dagostino.p_value)}`}
                  hint="Combine asymétrie et kurtosis. Nécessite au moins 20 observations."
                />
              )}
              {anderson && (
                <StatRow
                  label="Anderson-Darling"
                  value={`A² = ${formatNumber(anderson.statistic, precision)} (seuil 5 % : ${formatNumber(
                    anderson.critical_value_5pct,
                    precision,
                  )}) → ${anderson.normal_at_5pct ? 'normale' : 'rejetée'}`}
                  hint="Plus sensible que Shapiro dans les queues de distribution."
                />
              )}
            </dl>
            <p className="rounded-md bg-slate-50 p-2 text-sm text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
              {info.normality?.interpretation}
              {shapiro?.sampled && ` (test calculé sur un échantillon de ${shapiro.n_used} valeurs)`}
            </p>
          </Panel>

          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Ajustement de loi (goodness-of-fit)
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                    <th className="py-1 pr-4 font-medium">Loi</th>
                    <th className="py-1 pr-4 font-medium">Statistique KS</th>
                    <th className="py-1 font-medium">p-value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {info.fits.map((fit) => (
                    <tr key={fit.law} className={fit.law === info.detected_law ? 'font-semibold' : ''}>
                      <td className="py-1.5 pr-4 text-slate-700 dark:text-slate-200">
                        {LAW_LABELS[fit.law] || fit.law}
                      </td>
                      <td className="py-1.5 pr-4 tabular-nums text-slate-600 dark:text-slate-300">
                        {formatNumber(fit.ks_statistic, precision)}
                      </td>
                      <td className="py-1.5 tabular-nums text-slate-600 dark:text-slate-300">
                        {formatPValue(fit.p_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {info.fit_message && (
              <p className="text-sm text-amber-700 dark:text-amber-400">{info.fit_message}</p>
            )}
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Test de Kolmogorov-Smirnov avec paramètres estimés sur l&apos;échantillon : les p-values servent à
              classer les lois entre elles, pas à valider formellement une hypothèse.
            </p>
          </Panel>
        </div>

        <div className="flex flex-col gap-4">
          <ThemedPlot
            height={380}
            exportName={`qqplot_${selected}`}
            data={[
              {
                type: 'scattergl',
                mode: 'markers',
                x: qq.theoretical,
                y: qq.sample,
                name: 'Observations',
                marker: { color: '#4C78A8', size: 6, opacity: 0.75 },
                hovertemplate: 'quantile théorique %{x:.3f}<br>valeur observée %{y:.3f}<extra></extra>',
              },
              {
                type: 'scatter',
                mode: 'lines',
                x: line.x,
                y: line.y,
                name: 'Référence normale',
                line: { color: '#E45756', dash: 'dash' },
                hoverinfo: 'skip',
              },
            ]}
            layout={{
              title: `Q-Q plot — ${selected} vs loi normale`,
              margin: { t: 50, r: 20, b: 50, l: 60 },
              xaxis: { title: 'Quantiles théoriques (loi normale)' },
              yaxis: { title: 'Quantiles observés' },
              showlegend: true,
            }}
          />
          <p className="px-1 text-xs text-slate-500 dark:text-slate-400">
            Les points alignés sur la droite indiquent une distribution normale. Une courbure en S signale des queues
            trop épaisses ou trop fines ; un décrochage à une extrémité trahit des valeurs extrêmes.
          </p>

          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Intervalles de confiance de la moyenne
            </h4>
            <dl className="text-sm">
              <StatRow
                label="IC 95 %"
                value={`[${formatNumber(info.ci95.low, precision)} ; ${formatNumber(info.ci95.high, precision)}]`}
              />
              <StatRow
                label="IC 99 %"
                value={`[${formatNumber(info.ci99.low, precision)} ; ${formatNumber(info.ci99.high, precision)}]`}
              />
              <StatRow label="Marge d'erreur (95 %)" value={`± ${formatNumber(info.ci95.margin, precision)}`} />
            </dl>
          </Panel>
        </div>
      </div>
    </div>
  )
}
