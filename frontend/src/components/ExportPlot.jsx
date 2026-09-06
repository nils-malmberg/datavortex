import { useEffect, useRef, useState } from 'react'
import { exportPlot } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'

const FORMATS = [
  { value: 'png', label: 'PNG' },
  { value: 'svg', label: 'SVG' },
  { value: 'html', label: 'HTML interactif' },
]

export default function ExportPlot({ sessionId, kind, params, disabled, compact, width, height }) {
  const saveFile = useSaveFile()
  const [downloadingFormat, setDownloadingFormat] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  // Referme le menu au clic extérieur, comme n'importe quel menu contextuel.
  useEffect(() => {
    if (!open) return undefined
    const close = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const handleExport = async (format) => {
    setError(null)
    setDownloadingFormat(format)
    try {
      const response = await exportPlot(sessionId, kind, params, format, { width, height })
      const filename = extractFilename(
        response.headers['content-disposition'],
        `plot.${format}`,
      )
      await saveFile(response.data, filename)
    } catch (err) {
      setError(
        "Impossible d'exporter le graphique dans ce format pour le moment.",
      )
    } finally {
      setDownloadingFormat(null)
      setOpen(false)
    }
  }

  if (compact) {
    return (
      <div ref={menuRef} className="relative">
        <button
          onClick={() => setOpen((v) => !v)}
          disabled={disabled || downloadingFormat !== null}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {downloadingFormat ? 'Export…' : 'Exporter \u25BE'}
        </button>
        {open && (
          <div className="absolute bottom-full left-0 z-20 mb-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
            {FORMATS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => handleExport(value)}
                className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                {label}
              </button>
            ))}
            {error && <p className="px-3 py-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
          </div>
        )}
      </div>
    )
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
