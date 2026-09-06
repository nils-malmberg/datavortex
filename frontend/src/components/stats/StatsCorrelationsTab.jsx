import { useMemo, useRef, useState } from 'react'
import ThemedPlot, { downloadPlot } from '../ui/ThemedPlot'
import {
  BUTTON_CLASS,
  Badge,
  EmptyState,
  Panel,
  SliderField,
  Toggle,
  formatNumber,
  formatPValue,
} from '../ui/common'

/**
 * Onglet "Correlations" : heatmap interactive r + p-value.
 *
 * Le seuil masque les corrélations faibles (elles noient les signaux forts dans
 * un dégradé uniforme), et le clustering hiérarchique regroupe les variables
 * qui varient ensemble pour faire apparaître les blocs de la matrice.
 */
export default function StatsCorrelationsTab({ correlations, precision, onChangeMethod, method }) {
  const [threshold, setThreshold] = useState(0)
  const [hideDiagonal, setHideDiagonal] = useState(false)
  const [useClustering, setUseClustering] = useState(true)
  const graphDiv = useRef(null)

  const { columns, matrix, p_values: pValues, n_pairs: nPairs, clustered_order: clusteredOrder } = correlations

  const order = useMemo(
    () => (useClustering && clusteredOrder?.length === columns.length ? clusteredOrder : columns),
    [useClustering, clusteredOrder, columns],
  )

  const figure = useMemo(() => {
    if (columns.length < 2) return null
    const idx = order.map((c) => columns.indexOf(c))

    const z = []
    const labels = []
    const hover = []
    for (const i of idx) {
      const zRow = []
      const labelRow = []
      const hoverRow = []
      for (const j of idx) {
        const r = matrix[i][j]
        const p = pValues[i][j]
        const isDiagonal = i === j
        const belowThreshold = r !== null && Math.abs(r) < threshold
        // On vide la cellule (null = trou dans la heatmap) plutôt que de retirer
        // la ligne/colonne : la structure de la matrice reste lisible.
        const masked = (isDiagonal && hideDiagonal) || belowThreshold
        zRow.push(masked ? null : r)
        labelRow.push(masked || r === null ? '' : formatNumber(r, Math.min(precision, 2)))
        hoverRow.push(
          isDiagonal
            ? `${columns[i]}<br>corrélation avec elle-même`
            : `<b>${columns[i]} ↔ ${columns[j]}</b><br>` +
              `r = ${formatNumber(r, precision)}<br>` +
              `p = ${formatPValue(p)}${p !== null && p < 0.05 ? ' (significatif)' : ''}<br>` +
              `n = ${nPairs?.[i]?.[j] ?? '—'} paires`,
        )
      }
      z.push(zRow)
      labels.push(labelRow)
      hover.push(hoverRow)
    }

    return {
      data: [
        {
          type: 'heatmap',
          z,
          x: order,
          y: order,
          // `text` porte l'annotation affichée dans la cellule, `customdata`
          // le détail au survol (r, p-value, effectif) : deux usages distincts.
          text: labels,
          texttemplate: '%{text}',
          textfont: { size: 10 },
          customdata: hover,
          hovertemplate: '%{customdata}<extra></extra>',
          colorscale: 'RdBu',
          reversescale: true,
          zmin: -1,
          zmax: 1,
          zmid: 0,
          hoverongaps: false,
          colorbar: { title: `r (${method})`, thickness: 14 },
        },
      ],
      layout: {
        margin: { t: 20, r: 20, b: 110, l: 110 },
        xaxis: { tickangle: -45, automargin: true, gridcolor: 'rgba(0,0,0,0)' },
        yaxis: { automargin: true, autorange: 'reversed', gridcolor: 'rgba(0,0,0,0)' },
      },
    }
  }, [columns, matrix, pValues, nPairs, order, threshold, hideDiagonal, precision, method])

  if (columns.length < 2) {
    return (
      <EmptyState>
        {correlations.message || 'Au moins 2 colonnes numériques sont nécessaires pour analyser les corrélations.'}
      </EmptyState>
    )
  }

  const size = Math.max(420, Math.min(760, 120 + columns.length * 42))

  return (
    <div className="flex flex-col gap-4">
      <Panel className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Méthode</span>
          <select
            value={method}
            onChange={(e) => onChangeMethod(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          >
            <option value="pearson">Pearson (linéaire)</option>
            <option value="spearman">Spearman (rangs, monotone)</option>
            <option value="kendall">Kendall (tau, robuste)</option>
          </select>
        </label>

        <SliderField
          label="Seuil |r|"
          value={threshold}
          onChange={setThreshold}
          min={0}
          max={0.95}
          step={0.05}
          format={(v) => (v === 0 ? 'aucun' : `≥ ${v.toFixed(2)}`)}
          hint="Masque les corrélations plus faibles que le seuil pour ne garder que les liaisons marquées."
        />

        <Toggle label="Masquer la diagonale" checked={hideDiagonal} onChange={setHideDiagonal} />
        <Toggle
          label="Clustering hiérarchique"
          checked={useClustering}
          onChange={setUseClustering}
          hint="Réordonne les colonnes pour regrouper les variables corrélées entre elles (distance = 1 − |r|)."
        />

        <button
          onClick={() => downloadPlot(graphDiv.current, { filename: 'heatmap_correlations' })}
          className={`${BUTTON_CLASS} ml-auto`}
        >
          Exporter la heatmap (PNG)
        </button>
      </Panel>

      <ThemedPlot
        data={figure.data}
        layout={figure.layout}
        height={size}
        exportName="heatmap_correlations"
        onGraphDiv={(gd) => {
          graphDiv.current = gd
        }}
      />

      <Panel className="flex flex-col gap-2">
        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Corrélations les plus fortes</h4>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-400 dark:text-slate-500">
                <th className="py-1 pr-4 font-medium">Paire</th>
                <th className="py-1 pr-4 font-medium">r</th>
                <th className="py-1 pr-4 font-medium">p-value</th>
                <th className="py-1 font-medium">Significativité (α = 5 %)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {correlations.strongest?.map((pair) => (
                <tr key={`${pair.x}-${pair.y}`}>
                  <td className="py-1.5 pr-4 text-slate-700 dark:text-slate-200">
                    {pair.x} ↔ {pair.y}
                  </td>
                  <td className="py-1.5 pr-4 font-medium tabular-nums text-slate-800 dark:text-slate-100">
                    {formatNumber(pair.r, precision)}
                  </td>
                  <td className="py-1.5 pr-4 tabular-nums text-slate-600 dark:text-slate-300">
                    {formatPValue(pair.p_value)}
                  </td>
                  <td className="py-1.5">
                    {pair.significant ? (
                      <Badge tone="green">significative</Badge>
                    ) : (
                      <Badge tone="slate">non significative</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          La p-value teste H₀ : « la corrélation est nulle dans la population ». Une corrélation forte sur peu de
          points peut rester non significative — et l&apos;inverse est vrai sur de grands échantillons.
        </p>
      </Panel>
    </div>
  )
}
