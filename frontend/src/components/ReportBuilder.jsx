import { useState } from 'react'
import { generateReportPdf } from '../api/client'
import { extractFilename, triggerBlobDownload } from '../api/download'

const SECTIONS = [
  { value: 'summary', label: 'Résumé exécutif' },
  { value: 'stats', label: 'Statistiques' },
  { value: 'preview', label: 'Aperçu des données' },
  { value: 'plots', label: 'Graphiques' },
  { value: 'correlations', label: 'Corrélations' },
  { value: 'metadata', label: 'Métadonnées' },
]

export default function ReportBuilder({ sessionId, savedPlots, onRemovePlot, onClose }) {
  const [selectedSections, setSelectedSections] = useState(SECTIONS.map((s) => s.value))
  const [selectedPlotIds, setSelectedPlotIds] = useState(savedPlots.map((p) => p.id))
  const [pageFormat, setPageFormat] = useState('A4')
  const [orientation, setOrientation] = useState('portrait')
  const [resizePlotsToFit, setResizePlotsToFit] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState(null)

  const toggleSection = (value) => {
    setSelectedSections((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value],
    )
  }

  const togglePlot = (id) => {
    setSelectedPlotIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]))
  }

  const handleGenerate = async () => {
    setIsGenerating(true)
    setError(null)
    try {
      const plotsPayload = savedPlots
        .filter((p) => selectedPlotIds.includes(p.id))
        .map((p) => ({ kind: p.kind, params: p.params, title: p.label }))
      const response = await generateReportPdf(sessionId, {
        sections: selectedSections,
        plots: plotsPayload,
        pageFormat,
        orientation,
        resizePlotsToFit,
      })
      const filename = extractFilename(response.headers['content-disposition'], 'rapport.pdf')
      triggerBlobDownload(response.data, filename)
      onClose()
    } catch (err) {
      setError(
        err?.response?.data?.error?.message || 'Impossible de générer le rapport PDF.',
      )
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-lg flex-col gap-4 overflow-y-auto rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-50">
            Générer un rapport PDF
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            aria-label="Fermer"
          >
            ✕
          </button>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">
            Sections à inclure
          </p>
          <div className="grid grid-cols-2 gap-2">
            {SECTIONS.map((s) => (
              <label
                key={s.value}
                className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200"
              >
                <input
                  type="checkbox"
                  checked={selectedSections.includes(s.value)}
                  onChange={() => toggleSection(s.value)}
                />
                {s.label}
              </label>
            ))}
          </div>
        </div>

        {selectedSections.includes('plots') && (
          <div>
            <p className="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">
              Graphiques à inclure
            </p>
            {savedPlots.length === 0 ? (
              <p className="text-sm text-slate-400 dark:text-slate-500">
                Aucun graphique enregistré. Depuis l&apos;onglet Visualisations, générez un
                graphique puis cliquez sur « Ajouter au rapport ».
              </p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {savedPlots.map((p) => (
                  <div
                    key={p.id}
                    className="flex items-center justify-between gap-2 rounded-md border border-slate-200 px-2.5 py-1.5 text-sm dark:border-slate-700"
                  >
                    <label className="flex flex-1 items-center gap-2 text-slate-700 dark:text-slate-200">
                      <input
                        type="checkbox"
                        checked={selectedPlotIds.includes(p.id)}
                        onChange={() => togglePlot(p.id)}
                      />
                      {p.label}
                    </label>
                    <button
                      onClick={() => onRemovePlot(p.id)}
                      className="text-slate-400 hover:text-red-600 dark:hover:text-red-400"
                      aria-label="Retirer ce graphique"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600 dark:text-slate-300">Format de page</span>
            <select
              value={pageFormat}
              onChange={(e) => setPageFormat(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="A4">A4</option>
              <option value="Letter">Letter</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600 dark:text-slate-300">Orientation</span>
            <select
              value={orientation}
              onChange={(e) => setOrientation(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="portrait">Portrait</option>
              <option value="landscape">Paysage</option>
            </select>
          </label>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
          <input
            type="checkbox"
            checked={resizePlotsToFit}
            onChange={(e) => setResizePlotsToFit(e.target.checked)}
          />
          Resize plots to fit page
          <span className="text-xs text-slate-400 dark:text-slate-500">
            (graphiques et heatmap toujours contenus dans les marges, taille plus compacte)
          </span>
        </label>

        {error && (
          <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Annuler
          </button>
          <button
            onClick={handleGenerate}
            disabled={isGenerating || selectedSections.length === 0}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
          >
            {isGenerating ? 'Génération…' : 'Generate PDF'}
          </button>
        </div>
      </div>
    </div>
  )
}
