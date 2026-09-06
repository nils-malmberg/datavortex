import { useState } from 'react'
import { exportModel, exportModelMetadata, exportTrainingScript } from '../../api/client'
import { extractFilename } from '../../api/download'
import useSaveFile from '../../hooks/useSaveFile'
import useToast from '../ui/ToastProvider'
import { BUTTON_CLASS } from '../ui/common'

const SKLEARN_FORMATS = [
  { value: 'joblib', label: 'joblib' },
  { value: 'pickle', label: 'pickle' },
  { value: 'json', label: 'JSON' },
  { value: 'onnx', label: 'ONNX' },
]

const NEURAL_FORMATS = [{ value: 'tflite', label: 'TFLite' }]

/**
 * Menu d'export d'un modèle entraîné (Phase 8.1) : poids/config dans le
 * format choisi, métadonnées de reproductibilité (JSON), et notebook de
 * ré-entraînement — chacun passe par le dialogue d'enregistrement natif.
 */
export default function ModelExportMenu({ sessionId, modelId, task }) {
  const saveFile = useSaveFile()
  const toast = useToast()
  const [busy, setBusy] = useState(null)

  if (!modelId) return null

  const formats = task === 'neural_network' ? NEURAL_FORMATS : SKLEARN_FORMATS

  const handleExportModel = async (format) => {
    setBusy(format)
    try {
      const response = await exportModel(sessionId, modelId, format)
      const filename = extractFilename(response.headers['content-disposition'], `modele.${format}`)
      await saveFile(response.data, filename)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || `Export ${format} impossible pour ce modèle.`)
    } finally {
      setBusy(null)
    }
  }

  const handleExportMetadata = async () => {
    setBusy('metadata')
    try {
      const { data } = await exportModelMetadata(sessionId, modelId)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      await saveFile(blob, `metadonnees_modele_${modelId.slice(0, 8)}.json`)
    } catch {
      toast.error("Impossible d'exporter les métadonnées.")
    } finally {
      setBusy(null)
    }
  }

  const handleExportScript = async () => {
    setBusy('script')
    try {
      const response = await exportTrainingScript(sessionId, modelId)
      const filename = extractFilename(response.headers['content-disposition'], 'reproduction.ipynb')
      await saveFile(response.data, filename)
    } catch {
      toast.error("Impossible d'exporter le notebook de reproduction.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/60">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        Exporter le modèle
      </span>
      {formats.map(({ value, label }) => (
        <button
          key={value}
          onClick={() => handleExportModel(value)}
          disabled={busy !== null}
          className={BUTTON_CLASS}
          title={`Télécharger le modèle au format ${label}`}
        >
          {busy === value ? '…' : label}
        </button>
      ))}
      <button onClick={handleExportMetadata} disabled={busy !== null} className={BUTTON_CLASS}>
        {busy === 'metadata' ? '…' : 'Métadonnées'}
      </button>
      <button onClick={handleExportScript} disabled={busy !== null} className={BUTTON_CLASS}>
        {busy === 'script' ? '…' : 'Notebook de reproduction'}
      </button>
    </div>
  )
}
