import PlotPreview from '../PlotPreview'
import ResultTable from '../ui/ResultTable'
import { Badge, InfoTip, Panel, StatCard, formatNumber, formatPValue } from '../ui/common'

/**
 * Rendu commun d'un résultat de test : décision, taille d'effet, tableaux
 * spécifiques à la famille, et visualisation.
 *
 * La taille d'effet est affichée aussi visiblement que la p-value : sur un
 * grand échantillon, un écart sans portée pratique devient « significatif ».
 */
export default function TestResult({ result, precision }) {
  const { decision, effect_size: effect } = result

  return (
    <div className="flex flex-col gap-4">
      <Panel className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="font-semibold text-slate-800 dark:text-slate-100">{result.test_name}</h4>
          {decision.significant === true && <Badge tone="green">résultat significatif</Badge>}
          {decision.significant === false && <Badge tone="slate">non significatif</Badge>}
          {decision.significant === null && <Badge tone="amber">pas de p-value</Badge>}
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          <span className="font-medium">Hypothèse nulle testée :</span> {result.null_hypothesis}.
        </p>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            label="Statistique"
            value={formatNumber(result.test_statistic, precision)}
            sub={
              Array.isArray(result.degrees_of_freedom)
                ? `ddl = ${result.degrees_of_freedom.join(' ; ')}`
                : result.degrees_of_freedom != null
                  ? `ddl = ${formatNumber(result.degrees_of_freedom, 2)}`
                  : undefined
            }
          />
          <StatCard
            label="p-value"
            value={formatPValue(result.p_value)}
            sub={`seuil α = ${result.alpha}`}
            tone={decision.significant ? 'green' : 'slate'}
          />
          {effect && (
            <StatCard
              label={effect.name}
              value={formatNumber(effect.value, precision)}
              sub={`effet ${effect.magnitude}`}
              tone="blue"
            />
          )}
          {effect?.corrected_value != null && (
            <StatCard label="Valeur corrigée" value={formatNumber(effect.corrected_value, precision)} />
          )}
          {result.n_pairs != null && <StatCard label="Paires analysées" value={result.n_pairs} />}
          {result.n != null && <StatCard label="Observations" value={result.n} />}
        </div>

        <p
          className={`rounded-md p-3 text-sm ${
            decision.significant
              ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300'
              : 'bg-slate-50 text-slate-700 dark:bg-slate-800/60 dark:text-slate-300'
          }`}
        >
          {decision.text}
        </p>

        {effect && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            <span className="font-medium">{effect.name}</span> : {effect.definition}
          </p>
        )}

        {result.caution && (
          <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
            {result.caution}
          </p>
        )}
        {result.normality_note && (
          <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
            {result.normality_note}
          </p>
        )}
        {result.caveat && (
          <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
            {result.caveat}
          </p>
        )}
        {result.assumption_note && (
          <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
            {result.assumption_note}
          </p>
        )}
        {result.note && (
          <p className="rounded-md bg-slate-50 p-2 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
            {result.note}
          </p>
        )}
        {result.interaction_note && (
          <p className="rounded-md bg-blue-50 p-2 text-xs text-blue-800 dark:bg-blue-950/30 dark:text-blue-300">
            {result.interaction_note}
          </p>
        )}
      </Panel>

      {result.samples && (
        <Panel className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Échantillons comparés</h4>
          <ResultTable
            columns={['label', 'n', 'mean', 'median', 'std']}
            rows={result.samples}
            highlightColumns={['label']}
            precision={precision}
            maxHeight="200px"
          />
        </Panel>
      )}

      {result.table && (
        <Panel className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Tableau d&apos;analyse de variance</h4>
          <ResultTable
            columns={['source', 'ss', 'df', 'ms', 'f', 'p_value']}
            rows={result.table}
            highlightColumns={['source']}
            precision={precision}
            maxHeight="240px"
          />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            SS : somme des carrés · df : degrés de liberté · MS : carré moyen (SS / df) · F : rapport du carré
            moyen de la source sur celui de la résiduelle.
          </p>
        </Panel>
      )}

      {result.homogeneity && (
        <Panel className="flex flex-col gap-1">
          <h4 className="flex items-center gap-1 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Homogénéité des variances
            <InfoTip text="L'ANOVA suppose que les groupes ont des variances comparables." />
            <Badge tone={result.homogeneity.homogeneous ? 'green' : 'amber'}>
              Levene p = {formatPValue(result.homogeneity.p_value)}
            </Badge>
          </h4>
          <p className="text-sm text-slate-600 dark:text-slate-300">{result.homogeneity.note}</p>
        </Panel>
      )}

      {result.groups && (
        <Panel className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Statistiques par groupe</h4>
          <ResultTable
            columns={['label', 'n', 'mean', 'std']}
            rows={result.groups}
            highlightColumns={['label']}
            precision={precision}
            maxHeight="240px"
          />
        </Panel>
      )}

      {result.post_hoc && (
        <Panel className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Comparaisons deux à deux ({result.post_hoc.method})
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400">{result.post_hoc.description}</p>
          <ResultTable
            columns={['group_a', 'group_b', 'difference', 'p_value', 'ci_low', 'ci_high', 'significant']}
            rows={result.post_hoc.comparisons.map((c) => ({ ...c, significant: c.significant ? 'oui' : 'non' }))}
            highlightColumns={['group_a', 'group_b']}
            precision={precision}
            maxHeight="300px"
          />
        </Panel>
      )}

      {result.contingency && (
        <Panel className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Effectifs observés et théoriques
          </h4>
          <ResultTable
            columns={['modalité', ...result.contingency.columns]}
            rows={result.contingency.rows.map((label, i) => ({
              modalité: label,
              ...Object.fromEntries(
                result.contingency.columns.map((col, j) => [
                  col,
                  `${result.contingency.observed[i][j]} (attendu ${result.contingency.expected[i][j]})`,
                ]),
              ),
            }))}
            highlightColumns={['modalité']}
            precision={0}
            maxHeight="280px"
          />
        </Panel>
      )}

      {result.confidence_interval && (
        <Panel className="flex flex-col gap-1">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Intervalle de confiance à {Math.round(result.confidence_interval.level * 100)} %
          </h4>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {result.confidence_interval.low === null
              ? '—'
              : `[${formatNumber(result.confidence_interval.low, precision)} ; ${formatNumber(
                  result.confidence_interval.high,
                  precision,
                )}]`}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{result.confidence_interval.note}</p>
        </Panel>
      )}

      {result.critical_values && (
        <Panel className="flex flex-col gap-2">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Valeurs critiques</h4>
          <ResultTable
            columns={['significance_level', 'critical_value', 'rejected']}
            rows={result.critical_values.map((c) => ({ ...c, rejected: c.rejected ? 'rejeté' : 'non rejeté' }))}
            precision={precision}
            maxHeight="200px"
          />
        </Panel>
      )}

      {result.figure && <PlotPreview figure={result.figure} />}
    </div>
  )
}
