import Plot from 'react-plotly.js'
import useDarkMode from '../hooks/useDarkMode'

export default function PlotPreview({ figure, isLoading, error }) {
  const [isDark] = useDarkMode()

  if (isLoading) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-500 dark:text-slate-400">Génération du graphique…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <p className="max-w-md rounded-md bg-red-50 px-4 py-2 text-center text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      </div>
    )
  }

  if (!figure) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white dark:border-slate-700 dark:bg-slate-900">
        <p className="text-sm text-slate-400 dark:text-slate-500">
          Configurez un graphique ci-dessus pour voir l&apos;aperçu.
        </p>
      </div>
    )
  }

  const layout = {
    ...figure.layout,
    autosize: true,
    margin: { t: 50, r: 30, b: 50, l: 60 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: isDark ? '#0f172a' : '#e2e8f0',
    font: { color: isDark ? '#e2e8f0' : '#1e293b' },
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
      <Plot
        data={figure.data}
        layout={layout}
        useResizeHandler
        style={{ width: '100%', height: '480px' }}
        config={{ responsive: true, displaylogo: false }}
      />
    </div>
  )
}
