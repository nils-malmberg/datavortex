import { useState } from 'react'
import { generateReportPdf } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'
import useToast from './ui/ToastProvider'
import { BUTTON_CLASS, ErrorBox, PRIMARY_BUTTON_CLASS, Segmented } from './ui/common'
import MultiSeriesEditor from './plot/MultiSeriesEditor'

const LAYOUT_OPTIONS = [
  { value: 'grid', label: 'Grille' },
  { value: '1col', label: '1 colonne' },
  { value: '2col', label: '2 colonnes' },
]

const LAYOUT_CLASSES = {
  grid: 'grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(360px,1fr))]',
  '1col': 'grid gap-5 grid-cols-1',
  '2col': 'grid gap-5 grid-cols-1 md:grid-cols-2',
}

let nextGraphId = 1
function makeGraph() {
  const id = `graph_${nextGraphId}`
  const title = `Graphique ${nextGraphId}`
  nextGraphId += 1
  return { id, title, config: null }
}

function isGraphExportable(graph) {
  const config = graph.config
  return Boolean(config?.xAxis) && Boolean(config?.series?.length) && config.series.every((s) => s.yColumn)
}

function GraphCard({ graph, sessionId, refreshKey, onTitleChange, onConfigChange, onRemove, canRemove }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <input
          type="text"
          value={graph.title}
          onChange={(e) => onTitleChange(e.target.value)}
          className="min-w-0 flex-1 rounded-md border border-transparent bg-transparent px-1 py-0.5 text-sm font-semibold text-slate-700 hover:border-slate-300 focus:border-slate-300 focus:outline-none dark:text-slate-200 dark:hover:border-slate-700"
        />
        <button
          onClick={onRemove}
          disabled={!canRemove}
          title="Supprimer ce graphique"
          className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30 dark:hover:bg-red-950/40"
        >
          🗑
        </button>
      </div>
      <MultiSeriesEditor sessionId={sessionId} refreshKey={refreshKey} onConfigChange={onConfigChange} />
    </div>
  )
}

/**
 * Tableau de bord multi-graphiques (Phase 10) : plusieurs graphiques
 * multi-séries indépendants, organisés selon la disposition choisie, exportés
 * ensemble en un seul PDF (une page par graphique, via le même moteur de
 * rapport que l'onglet Rapport — kind "multi-series").
 */
export default function MultiGraphDashboard({ sessionId, refreshKey }) {
  const [graphs, setGraphs] = useState(() => [makeGraph()])
  const [layout, setLayout] = useState('grid')
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState(null)
  const saveFile = useSaveFile()
  const toast = useToast()

  const addGraph = () => setGraphs((prev) => [...prev, makeGraph()])
  const removeGraph = (id) => setGraphs((prev) => (prev.length > 1 ? prev.filter((g) => g.id !== id) : prev))
  const updateGraphTitle = (id, title) =>
    setGraphs((prev) => prev.map((g) => (g.id === id ? { ...g, title } : g)))
  const updateGraphConfig = (id, config) =>
    setGraphs((prev) => prev.map((g) => (g.id === id ? { ...g, config } : g)))

  const exportableGraphs = graphs.filter(isGraphExportable)

  const handleExportAll = async () => {
    if (exportableGraphs.length === 0) return
    setIsExporting(true)
    setError(null)
    try {
      const plots = exportableGraphs.map((graph) => ({
        kind: 'multi-series',
        title: graph.title,
        params: {
          title: graph.config.title || undefined,
          x_axis: graph.config.xAxis,
          series: graph.config.series.map((s) => ({
            y_column: s.yColumn,
            y_axis: s.yAxis,
            plot_type: s.plotType,
            name: s.name || undefined,
            color: s.color || undefined,
          })),
        },
      }))
      const response = await generateReportPdf(sessionId, { sections: ['plots'], plots })
      const filename = extractFilename(response.headers['content-disposition'], 'graphiques.pdf')
      await saveFile(response.data, filename)
      toast.success(`${exportableGraphs.length} graphique(s) exporté(s) en PDF.`)
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Impossible d'exporter les graphiques en PDF.")
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented options={LAYOUT_OPTIONS} value={layout} onChange={setLayout} ariaLabel="Disposition des graphiques" />
        <button onClick={addGraph} className={BUTTON_CLASS}>
          + Ajouter un graphique
        </button>
        <button
          onClick={handleExportAll}
          disabled={isExporting || exportableGraphs.length === 0}
          className={`${PRIMARY_BUTTON_CLASS} ml-auto`}
        >
          {isExporting ? 'Export en cours…' : `📊 Exporter tout en PDF (${exportableGraphs.length})`}
        </button>
      </div>

      <ErrorBox>{error}</ErrorBox>

      <div className={LAYOUT_CLASSES[layout]}>
        {graphs.map((graph) => (
          <GraphCard
            key={graph.id}
            graph={graph}
            sessionId={sessionId}
            refreshKey={refreshKey}
            canRemove={graphs.length > 1}
            onTitleChange={(title) => updateGraphTitle(graph.id, title)}
            onConfigChange={(config) => updateGraphConfig(graph.id, config)}
            onRemove={() => removeGraph(graph.id)}
          />
        ))}
      </div>
    </div>
  )
}
