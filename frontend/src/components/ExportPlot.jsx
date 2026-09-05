import { useState } from 'react'
import { exportPlot } from '../api/client'

const FORMATS = [
  { value: 'png', label: 'PNG' },
  { value: 'svg', label: 'SVG' },
  { value: 'html', label: 'HTML interactif' },
]

function extractFilename(contentDisposition, fallback) {
  const match = /filename="?([^"]+)"?/.exec(contentDisposition || '')
  return match ? match[1] : fallback
}

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
      const url = window.URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
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
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            {downloadingFormat === value ? 'Export…' : `Télécharger ${label}`}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
    </div>
  )
}
