import { useState } from 'react'
import { exportPlot } from '../api/client'
import { extractFilename, triggerBlobDownload } from '../api/download'

const FORMATS = [
  { value: 'png', label: 'PNG' },
  { value: 'svg', label: 'SVG' },
  { value: 'html', label: 'HTML interactif' },
]

export default function ExportPlot({ sessionId, kind, params, disabled }) {
  const [downloadingFormat, setDownloadingFormat] = useState(null)
  const [error, setError] = useState(null)

  const handleExport = async (format) => {
    setError(null)
    setDownloadingFormat(format)
    try {
      const response = await exportPlot(sessionId, kind, params, format)
      const filename = extractFilename(
        response.headers['content-disposition'],
        `plot.${format}`,
      )
      triggerBlobDownload(response.data, filename)
    } catch (err) {
      setError(
        "Impossible d'exporter le graphique dans ce format pour le moment.",
      )
    } finally {
      setDownloadingFormat(null)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {FORMATS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => handleExport(value)}
            disabled={disabled || downloadingFormat !== null}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {downloadingFormat === value ? 'Export…' : `Télécharger ${label}`}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}
    </div>
  )
}
