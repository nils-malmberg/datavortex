import { useState } from 'react'
import { generateReportPdf } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'

const DEFAULT_SECTIONS = [
  'Page de couverture',
  'Résumé exécutif (avec score de qualité)',
  'Statistiques numériques et catégorielles',
  'Corrélations et p-values',
  'Données manquantes',
  'Qualité des données (5 dimensions)',
  'Suggestions de nettoyage',
]

const OPTIONAL_KIND_LABELS = {
  '1d': 'Graphique', '2d': 'Graphique', '3d': 'Graphique', advanced: 'Graphique',
  ml: 'Modèle ML', groupby: 'GroupBy', pivot: 'Pivot',
}

/**
 * Générateur de rapport PDF (refonte Phase 8.1).
 *
 * Philosophie : les statistiques détaillées sont toujours incluses (calculées
 * côté serveur à partir des mêmes fonctions que les onglets Stats/Profil) —
 * l'utilisateur ne choisit que les sections coûteuses à générer (graphiques,
 * modèles ML, GroupBy, Pivot), ajoutées au fil de l'exploration via
 * « + Ajouter au rapport » sur chaque onglet concerné.
 */
export default function ReportBuilder({ sessionId, savedPlots, onRemovePlot, onClose }) {
  const saveFile = useSaveFile()
  const [selectedPlotIds, setSelectedPlotIds] = useState(savedPlots.map((p) => p.id))
  const [includeDataPreview, setIncludeDataPreview] = useState(false)
  const [pageFormat, setPageFormat] = useState('A4')
  const [orientation, setOrientation] = useState('portrait')
  const [resizePlotsToFit, setResizePlotsToFit] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState(null)

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
        sections: includeDataPreview ? ['preview'] : [],
        plots: plotsPayload,
        pageFormat,
        orientation,
        resizePlotsToFit,
      })
      const filename = extractFilename(response.headers['content-disposition'], 'rapport.pdf')
      await saveFile(response.data, filename)
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
          <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-400">
            <span aria-hidden="true">✅</span> Inclus par défaut
          </p>
          <ul className="flex flex-col gap-1 rounded-md border border-emerald-200 bg-emerald-50/60 px-3 py-2 text-sm text-slate-600 dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-slate-300">
            {DEFAULT_SECTIONS.map((label) => (
              <li key={label} className="flex items-center gap-2">
                <input type="checkbox" checked disabled className="accent-emerald-600" />
                {label}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">☐ Sections optionnelles</p>
          <label className="mb-2 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
            <input type="checkbox" checked={includeDataPreview} onChange={(e) => setIncludeDataPreview(e.target.checked)} />
            Aperçu des données (15 premières lignes)
          </label>

          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            Graphiques / modèles / analyses ajoutés depuis les onglets
          </p>
          {savedPlots.length === 0 ? (
            <p className="text-sm text-slate-400 dark:text-slate-500">
              Aucun élément enregistré. Depuis Visualisations, Machine Learning, Groupby ou Pivot, cliquez sur
              « + Ajouter au rapport ».
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
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                      {OPTIONAL_KIND_LABELS[p.kind] || p.kind}
                    </span>
                    {p.label}
                  </label>
                  <button
                    onClick={() => onRemovePlot(p.id)}
                    className="text-slate-400 hover:text-red-600 dark:hover:text-red-400"
                    aria-label="Retirer cet élément"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

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
          Adapter les graphiques à la page
          <span className="text-xs text-slate-400 dark:text-slate-500">
            (graphiques et heatmaps toujours contenus dans les marges, taille plus compacte)
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
            disabled={isGenerating}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
          >
            {isGenerating ? 'Génération…' : 'Générer le PDF'}
          </button>
        </div>
      </div>
    </div>
  )
}
