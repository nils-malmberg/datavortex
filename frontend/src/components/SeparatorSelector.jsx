import { useMemo, useState } from 'react'
import { parseFile } from '../api/client'

const SEPARATOR_LABELS = {
  ',': 'Virgule ( , )',
  ';': 'Point-virgule ( ; )',
  '\t': 'Tabulation ( \\t )',
  '|': 'Pipe ( | )',
}

const COMPRESSION_LABELS = {
  gzip: 'gzip',
  bzip2: 'bzip2',
  zip: 'zip',
  snappy: 'snappy',
  zstd: 'zstd',
}

function formatMb(mb) {
  if (mb == null) return null
  return mb < 1 ? `${Math.round(mb * 1024)} Ko` : `${mb.toFixed(1)} Mo`
}

// Exemples proposés en mode regex : les cas qui motivent la fonctionnalité.
const REGEX_EXAMPLES = [
  { pattern: '\\s+', label: 'espaces multiples' },
  { pattern: '[,;]', label: 'virgule ou point-virgule' },
  { pattern: '\\s*,\\s*', label: 'virgule avec espaces autour' },
  { pattern: '\\t+', label: 'tabulations multiples' },
]

/**
 * Motif valide pour le découpage, ou `null` avec la raison.
 *
 * Le navigateur et Python n'ont pas exactement la même syntaxe regex, mais
 * pour un séparateur de colonnes — classes de caractères, quantificateurs,
 * échappements — les deux s'accordent : la validation ici épargne un
 * aller-retour serveur, celui-ci restant l'arbitre final.
 */
export function regexProblem(pattern) {
  if (!pattern) return 'Saisissez un motif.'
  let compiled
  try {
    compiled = new RegExp(pattern)
  } catch (err) {
    return `Expression régulière invalide : ${err.message.replace(/^Invalid regular expression: /, '')}`
  }
  if (compiled.test('')) return 'Le motif ne doit pas pouvoir correspondre à une chaîne vide.'
  return null
}

function splitPreviewLine(line, separator, isRegex) {
  if (!separator) return [line]
  if (isRegex) {
    return regexProblem(separator) ? [line] : line.split(new RegExp(separator))
  }
  return line.split(separator)
}

export default function SeparatorSelector({ uploadData, onParsed, onCancel }) {
  const {
    session_id: sessionId,
    filename,
    detected_separator: detectedSeparator,
    available_separators: availableSeparators,
    raw_preview: rawPreview,
    file_info: fileInfo,
  } = uploadData

  // Phase 10 : le fichier reçu est décompressé côté serveur avant d'arriver
  // ici — cette bannière est purement informative sur ce qui a été détecté.
  const compressionLabel = fileInfo?.compression ? COMPRESSION_LABELS[fileInfo.compression] : null

  const [separator, setSeparator] = useState(detectedSeparator || ',')
  const [customSeparator, setCustomSeparator] = useState('')
  const [regexPattern, setRegexPattern] = useState('\\s+')
  // 'preset' : un des séparateurs proposés ; 'custom' : une courte chaîne
  // littérale ; 'regex' : un motif (Phase 10.2).
  const [mode, setMode] = useState('preset')
  const [isParsing, setIsParsing] = useState(false)
  const [error, setError] = useState(null)

  const useCustom = mode === 'custom'
  const isRegex = mode === 'regex'
  const effectiveSeparator = isRegex ? regexPattern : useCustom ? customSeparator : separator
  const regexError = isRegex ? regexProblem(regexPattern) : null

  const previewRows = useMemo(
    () => (rawPreview || []).map((line) => splitPreviewLine(line, effectiveSeparator, isRegex)),
    [rawPreview, effectiveSeparator, isRegex],
  )
  const maxCols = Math.max(1, ...previewRows.map((r) => r.length))

  const handleConfirm = async () => {
    if (!effectiveSeparator) {
      setError('Veuillez indiquer un séparateur.')
      return
    }
    if (regexError) {
      setError(regexError)
      return
    }
    setIsParsing(true)
    setError(null)
    try {
      const { data } = await parseFile(sessionId, effectiveSeparator, isRegex ? 'regex' : 'preset')
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
        <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-50">
          Séparateur détecté pour « {filename} »
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Confirmez le séparateur détecté automatiquement ou choisissez-en un
          autre avant de parser le fichier.
        </p>
      </div>

      {compressionLabel && (
        <p className="rounded-md bg-slate-100 px-4 py-2 text-sm text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          📦 Compression <span className="font-medium">{compressionLabel}</span> détectée —{' '}
          {formatMb(fileInfo.size_mb)} reçus
          {fileInfo.uncompressed_size_mb != null && (
            <> · {formatMb(fileInfo.uncompressed_size_mb)} une fois décompressé</>
          )}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        {(availableSeparators || []).map((sep) => (
          <label
            key={sep}
            className={`cursor-pointer rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
              mode === 'preset' && separator === sep
                ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
                : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500'
            }`}
          >
            <input
              type="radio"
              name="separator"
              className="hidden"
              checked={mode === 'preset' && separator === sep}
              onChange={() => {
                setSeparator(sep)
                setMode('preset')
              }}
            />
            {SEPARATOR_LABELS[sep] || sep}
            {sep === detectedSeparator && (
              <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700 dark:bg-green-900/40 dark:text-green-300">
                détecté
              </span>
            )}
          </label>
        ))}
        <label
          className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
            useCustom
              ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
              : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500'
          }`}
        >
          <input
            type="radio"
            name="separator"
            className="hidden"
            checked={useCustom}
            onChange={() => setMode('custom')}
          />
          Autre :
          <input
            type="text"
            maxLength={3}
            value={customSeparator}
            onFocus={() => setMode('custom')}
            onChange={(e) => {
              setMode('custom')
              setCustomSeparator(e.target.value)
            }}
            placeholder="ex: :"
            className="w-12 rounded border border-slate-300 px-1 py-0.5 text-center dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
          />
        </label>
        <label
          className={`flex cursor-pointer items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
            isRegex
              ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
              : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-slate-500'
          }`}
        >
          <input type="radio" name="separator" className="hidden" checked={isRegex} onChange={() => setMode('regex')} />
          Regex (avancé)
        </label>
      </div>

      {isRegex && (
        <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600 dark:text-slate-300">Motif de séparateur</span>
            <input
              type="text"
              value={regexPattern}
              onChange={(e) => setRegexPattern(e.target.value)}
              spellCheck={false}
              aria-invalid={Boolean(regexError)}
              className={`rounded-md border px-3 py-1.5 font-mono text-sm dark:bg-slate-800 dark:text-slate-100 ${
                regexError
                  ? 'border-red-400 focus:border-red-500 dark:border-red-700'
                  : 'border-slate-300 focus:border-blue-500 dark:border-slate-600'
              }`}
            />
          </label>
          <p className={`text-xs ${regexError ? 'text-red-600 dark:text-red-400' : 'text-green-700 dark:text-green-400'}`}>
            {regexError ? `✗ ${regexError}` : '✓ Motif valide'}
          </p>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            Exemples :
            {REGEX_EXAMPLES.map((example) => (
              <button
                key={example.pattern}
                type="button"
                onClick={() => setRegexPattern(example.pattern)}
                title={example.label}
                className="rounded border border-slate-300 bg-slate-50 px-1.5 py-0.5 font-mono text-slate-700 hover:border-blue-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
              >
                {example.pattern}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Un motif force le moteur d&apos;analyse le plus lent (Python) : sur un gros fichier, préférez un
            séparateur simple quand c&apos;est possible.
          </p>
        </div>
      )}

      {previewRows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
          <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
            <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
              {previewRows.map((cells, i) => (
                <tr
                  key={i}
                  className={i === 0 ? 'bg-slate-50 font-semibold dark:bg-slate-800' : ''}
                >
                  {Array.from({ length: maxCols }).map((_, j) => (
                    <td
                      key={j}
                      className="whitespace-nowrap px-3 py-1.5 text-slate-700 dark:text-slate-200"
                    >
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
        <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleConfirm}
          disabled={isParsing || Boolean(regexError)}
          className="rounded-lg bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
        >
          {isParsing ? 'Analyse en cours…' : 'Valider et parser'}
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            className="rounded-lg border border-slate-300 px-5 py-2 font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Choisir un autre fichier
          </button>
        )}
      </div>
    </div>
  )
}
