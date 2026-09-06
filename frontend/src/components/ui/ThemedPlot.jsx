import { useCallback, useRef } from 'react'
import Plot from 'react-plotly.js'
// Même instance de module que celle utilisée par react-plotly.js : l'import
// direct donne accès à downloadImage sans embarquer une seconde copie de la
// bibliothèque dans le bundle.
import Plotly from 'plotly.js/dist/plotly'
import useDarkMode from '../../hooks/useDarkMode'

/**
 * Figure Plotly construite côté client, thématisée avec le mode sombre global.
 *
 * `PlotPreview` reste dédié aux figures renvoyées par le backend ; ce composant
 * sert aux visualisations calculées dans le navigateur (heatmaps de corrélation,
 * Q-Q plots, cartes de valeurs manquantes…) et expose un export image direct.
 */
export default function ThemedPlot({
  data,
  layout = {},
  height = 420,
  exportName = 'graphique',
  onGraphDiv,
  config = {},
  // Quand la figure impose son propre thème (choix explicite de l'utilisateur),
  // on n'écrase pas ses couleurs avec celles de l'interface.
  useFigureTheme = false,
}) {
  const [isDark] = useDarkMode()
  const graphDiv = useRef(null)

  const handleInit = useCallback(
    (_figure, gd) => {
      graphDiv.current = gd
      onGraphDiv?.(gd)
    },
    [onGraphDiv],
  )

  const themedLayout = useFigureTheme
    ? { ...layout, autosize: true }
    : {
        ...layout,
        autosize: true,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: isDark ? '#0f172a' : '#f8fafc',
        font: { color: isDark ? '#e2e8f0' : '#1e293b', ...(layout.font || {}) },
        xaxis: { gridcolor: isDark ? '#1e293b' : '#e2e8f0', ...(layout.xaxis || {}) },
        yaxis: { gridcolor: isDark ? '#1e293b' : '#e2e8f0', ...(layout.yaxis || {}) },
        legend: { bgcolor: 'rgba(0,0,0,0)', ...(layout.legend || {}) },
      }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
      <Plot
        data={data}
        layout={themedLayout}
        onInitialized={handleInit}
        onUpdate={handleInit}
        useResizeHandler
        style={{ width: '100%', height: `${height}px` }}
        config={{
          responsive: true,
          displaylogo: false,
          toImageButtonOptions: { format: 'png', filename: exportName, scale: 2 },
          ...config,
        }}
      />
    </div>
  )
}

/** Télécharge une figure déjà rendue, dans le format demandé. */
export function downloadPlot(graphDiv, { format = 'png', filename = 'graphique', width = 1200, height = 800 } = {}) {
  if (!graphDiv) return Promise.reject(new Error('Figure non initialisée.'))
  return Plotly.downloadImage(graphDiv, { format, filename, width, height, scale: 2 })
}

/** Capture une miniature PNG (data URL) de la figure rendue. */
export function capturePlotThumbnail(graphDiv, { width = 480, height = 320 } = {}) {
  if (!graphDiv) return Promise.reject(new Error('Figure non initialisée.'))
  return Plotly.toImage(graphDiv, { format: 'png', width, height })
}
