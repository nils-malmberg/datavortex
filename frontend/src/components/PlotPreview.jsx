import Plot from 'react-plotly.js'

export default function PlotPreview({ figure, isLoading, error }) {
  if (isLoading) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-slate-200 bg-white">
        <p className="text-sm text-slate-500">Génération du graphique…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-slate-200 bg-white">
        <p className="max-w-md rounded-md bg-red-50 px-4 py-2 text-center text-sm text-red-700">
          {error}
        </p>
      </div>
    )
  }

  if (!figure) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white">
        <p className="text-sm text-slate-400">
          Configurez un graphique ci-dessus pour voir l&apos;aperçu.
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-2">
      <Plot
        data={figure.data}
        layout={{
          ...figure.layout,
          autosize: true,
          margin: { t: 50, r: 30, b: 50, l: 60 },
        }}
        useResizeHandler
        style={{ width: '100%', height: '480px' }}
        config={{ responsive: true, displaylogo: false }}
      />
    </div>
  )
}
