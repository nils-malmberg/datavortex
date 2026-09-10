import { useEffect, useState } from 'react'
import { estimateCsvExport, exportCsvStream, getPreview } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'

const SEPARATORS = [
  { value: ',', label: 'Virgule ( , )' },
  { value: ';', label: 'Point-virgule ( ; )' },
  { value: '\t', label: 'Tabulation ( \\t )' },
  { value: '|', label: 'Pipe ( | )' },
]

const ENCODINGS = [
  { value: 'utf-8', label: 'UTF-8' },
  { value: 'latin-1', label: 'Latin-1 (ISO-8859-1)' },
]

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return null
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} Mo`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} Go`
}

export default function ExportData({ sessionId, refreshKey }) {
  const saveFile = useSaveFile()
  const [separator, setSeparator] = useState(',')
  const [encoding, setEncoding] = useState('utf-8')
  const [includeFilterComment, setIncludeFilterComment] = useState(true)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)
  const [info, setInfo] = useState(null)
  const [estimatedBytes, setEstimatedBytes] = useState(null)
  const [receivedBytes, setReceivedBytes] = useState(0)

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setInfo({
        filtered: data.filtered,
        totalRows: data.total_rows,
        totalRowsUnfiltered: data.total_rows_unfiltered,
      })
    })
    // Volume approximatif de l'export : annoncer « ~120 Mo » avant de lancer un
    // téléchargement lourd évite d'attendre sans savoir ce qui se passe.
    estimateCsvExport(sessionId)
      .then(({ data }) => setEstimatedBytes(data.estimated_bytes))
      .catch(() => setEstimatedBytes(null))
  }, [sessionId, refreshKey])

  const { filtered, totalRows, totalRowsUnfiltered } = info || {}

  const handleExport = async () => {
    setError(null)
    setSuccessMessage(null)
    setReceivedBytes(0)
    setIsExporting(true)
    try {
      // Export en flux (Phase 9) : le serveur émet le CSV par tranches au lieu
      // de le construire entièrement en mémoire avant d'envoyer le premier octet.
      const response = await exportCsvStream(sessionId, {
        separator,
        encoding,
        includeFilterComment,
        onProgress: setReceivedBytes,
      })
      const filename = extractFilename(response.headers['content-disposition'], 'data.csv')
      await saveFile(response.data, filename)
      setSuccessMessage(`Fichier "${filename}" téléchargé.`)
    } catch (err) {
      // La réponse est un blob (responseType), y compris quand c'est une
      // erreur : le message JSON doit être lu depuis le blob, pas depuis data.
      let message = "Impossible d'exporter les données pour le moment."
      try {
        message = JSON.parse(await err.response.data.text())?.error?.message || message
      } catch {
        message = err?.response?.data?.error?.message || message
      }
      setError(message)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {info ? (
            <>
              Exporte les données actuellement affichées
              {filtered ? (
                <>
                  {' '}
                  — <span className="font-medium text-blue-700 dark:text-blue-400">{totalRows}</span> ligne(s)
                  filtrée(s) sur {totalRowsUnfiltered}
                </>
              ) : (
                <> — {totalRows} ligne(s) au total</>
              )}
              , colonnes calculées incluses.
              {estimatedBytes ? <> Volume approximatif : {formatBytes(estimatedBytes)}.</> : null}
            </>
          ) : (
            'Chargement des informations…'
          )}
        </p>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Séparateur</span>
          <select
            value={separator}
            onChange={(e) => setSeparator(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          >
            {SEPARATORS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Encoding</span>
          <select
            value={encoding}
            onChange={(e) => setEncoding(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          >
            {ENCODINGS.map((enc) => (
              <option key={enc.value} value={enc.value}>
                {enc.label}
              </option>
            ))}
          </select>
        </label>

        {filtered && (
          <label className="flex items-center gap-2 self-end pb-1.5 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={includeFilterComment}
              onChange={(e) => setIncludeFilterComment(e.target.checked)}
            />
            Inclure le filtre en commentaire dans le CSV
          </label>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
        >
          {isExporting ? 'Export en cours…' : 'Télécharger CSV'}
        </button>
        {isExporting && receivedBytes > 0 && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {formatBytes(receivedBytes)} reçus
            {estimatedBytes ? ` sur ~${formatBytes(estimatedBytes)}` : ''}
          </p>
        )}
        {successMessage && <p className="text-sm text-green-700 dark:text-green-400">{successMessage}</p>}
      </div>

      {error && <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{error}</p>}
    </div>
  )
}
