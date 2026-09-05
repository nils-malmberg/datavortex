import { useCallback, useRef, useState } from 'react'
import { uploadFile } from '../api/client'

const ACCEPTED_EXTENSIONS = ['.csv', '.txt', '.tsv', '.xlsx', '.xls', '.json']

function isAcceptedFile(file) {
  const name = file.name.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))
}

export default function UploadZone({ onUploaded }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const handleFile = useCallback(
    async (file) => {
      setError(null)
      if (!file) return
      if (!isAcceptedFile(file)) {
        setError(
          `Format non supporté. Formats acceptés : ${ACCEPTED_EXTENSIONS.join(', ')}`,
        )
        return
      }
      setIsUploading(true)
      try {
        const { data } = await uploadFile(file)
        onUploaded(data)
      } catch (err) {
        const message =
          err?.response?.data?.error?.message ||
          "Une erreur est survenue lors de l'upload du fichier."
        setError(message)
      } finally {
        setIsUploading(false)
      }
    },
    [onUploaded],
  )

  const onDrop = useCallback(
    (event) => {
      event.preventDefault()
      setIsDragging(false)
      const file = event.dataTransfer?.files?.[0]
      handleFile(file)
    },
    [handleFile],
  )

  const onInputChange = useCallback(
    (event) => {
      const file = event.target.files?.[0]
      handleFile(file)
      event.target.value = ''
    },
    [handleFile],
  )

  return (
    <div className="flex flex-col items-center justify-center gap-4 p-8">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`w-full max-w-xl cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors ${
          isDragging
            ? 'border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/40'
            : 'border-slate-300 bg-white hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-500'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={onInputChange}
        />
        <p className="text-lg font-medium text-slate-700 dark:text-slate-200">
          {isUploading
            ? 'Envoi en cours…'
            : 'Glissez-déposez un fichier ici, ou cliquez pour parcourir'}
        </p>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          Formats supportés : CSV, TSV, Excel (.xlsx, .xls), JSON — jusqu&apos;à 100MB
        </p>
      </div>
      {error && (
        <p className="max-w-xl rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}
    </div>
  )
}
