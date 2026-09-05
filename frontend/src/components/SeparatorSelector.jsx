import { useMemo, useState } from 'react'
import { parseFile } from '../api/client'

const SEPARATOR_LABELS = {
  ',': 'Virgule ( , )',
  ';': 'Point-virgule ( ; )',
  '\t': 'Tabulation ( \\t )',
  '|': 'Pipe ( | )',
}

function splitPreviewLine(line, separator) {
  if (!separator) return [line]
  return line.split(separator)
}

export default function SeparatorSelector({ uploadData, onParsed, onCancel }) {
  const {
    session_id: sessionId,
    filename,
    detected_separator: detectedSeparator,
    available_separators: availableSeparators,
    raw_preview: rawPreview,
  } = uploadData

  const [separator, setSeparator] = useState(detectedSeparator || ',')
  const [customSeparator, setCustomSeparator] = useState('')
  const [useCustom, setUseCustom] = useState(false)
  const [isParsing, setIsParsing] = useState(false)
  const [error, setError] = useState(null)

  const effectiveSeparator = useCustom ? customSeparator : separator

  const previewRows = useMemo(
    () => (rawPreview || []).map((line) => splitPreviewLine(line, effectiveSeparator)),
    [rawPreview, effectiveSeparator],
  )
  const maxCols = Math.max(1, ...previewRows.map((r) => r.length))

  const handleConfirm = async () => {
    if (!effectiveSeparator) {
      setError('Veuillez indiquer un séparateur.')
      return
    }
    setIsParsing(true)
    setError(null)
    try {
      const { data } = await parseFile(sessionId, effectiveSeparator)
      onParsed(data)
    } catch (err) {
      const message =
        err?.response?.data?.error?.message ||
        'Impossible de parser le fichier avec ce séparateur.'
      setError(message)
    } finally {
      setIsParsing(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-8">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">
          Séparateur détecté pour « {filename} »
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Confirmez le séparateur détecté automatiquement ou choisissez-en un
          autre avant de parser le fichier.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        {(availableSeparators || []).map((sep) => (
          <label
            key={sep}
            className={`cursor-pointer rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
              !useCustom && separator === sep
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
            }`}
          >
            <input
              type="radio"
              name="separator"
              className="hidden"
              checked={!useCustom && separator === sep}
              onChange={() => {
                setSeparator(sep)
                setUseCustom(false)
              }}
            />
            {SEPARATOR_LABELS[sep] || sep}
            {sep === detectedSeparator && (
              <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                détecté
              </span>
            )}
          </label>
        ))}
        <label
          className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
            useCustom
              ? 'border-blue-500 bg-blue-50 text-blue-700'
              : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
          }`}
        >
          <input
            type="radio"
            name="separator"
            className="hidden"
            checked={useCustom}
            onChange={() => setUseCustom(true)}
          />
          Autre :
          <input
            type="text"
            maxLength={3}
            value={customSeparator}
            onFocus={() => setUseCustom(true)}
            onChange={(e) => {
              setUseCustom(true)
              setCustomSeparator(e.target.value)
            }}
            placeholder="ex: :"
            className="w-12 rounded border border-slate-300 px-1 py-0.5 text-center"
          />
        </label>
      </div>

      {previewRows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <tbody className="divide-y divide-slate-100 bg-white">
              {previewRows.map((cells, i) => (
                <tr key={i} className={i === 0 ? 'bg-slate-50 font-semibold' : ''}>
                  {Array.from({ length: maxCols }).map((_, j) => (
                    <td key={j} className="whitespace-nowrap px-3 py-1.5 text-slate-700">
                      {cells[j] ?? ''}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {error && (
        <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700">{error}</p>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleConfirm}
          disabled={isParsing}
          className="rounded-lg bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isParsing ? 'Analyse en cours…' : 'Valider et parser'}
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="rounded-lg border border-slate-300 px-5 py-2 font-medium text-slate-600 hover:bg-slate-50"
          >
            Choisir un autre fichier
          </button>
        )}
      </div>
    </div>
  )
}
