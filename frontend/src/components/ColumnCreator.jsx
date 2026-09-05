import { useEffect, useRef, useState } from 'react'
import { createColumn, getPreview } from '../api/client'

const FUNCTION_REFERENCE = [
  { group: 'Arithmétique', items: ['+  -  *  /  %  **'] },
  { group: 'Comparaison', items: ['==  !=  >  <  >=  <='] },
  { group: 'Logique', items: ['and  or  not'] },
  { group: 'Math', items: ['abs()', 'round(v, n)', 'sqrt()', 'pow(a, b)', 'log()', 'log10()', 'exp()', 'sin() cos() tan()', 'ceil() floor()', 'min() max()'] },
  { group: 'Texte', items: ['upper()', 'lower()', 'strip()', 'len()', 'concat(a, b, ...)', 'replace(s, old, new)', 'substring(s, start, end)'] },
  { group: 'Conditionnel', items: ["if(condition, si_vrai, si_faux)"] },
]

export default function ColumnCreator({ sessionId, onColumnCreated }) {
  const [columns, setColumns] = useState([])
  const [name, setName] = useState('')
  const [formula, setFormula] = useState('')
  const [overwrite, setOverwrite] = useState(false)
  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => setColumns(data.columns))
  }, [sessionId])

  const insertAtCursor = (text) => {
    const el = textareaRef.current
    if (!el) {
      setFormula((f) => f + text)
      return
    }
    const start = el.selectionStart ?? formula.length
    const end = el.selectionEnd ?? formula.length
    const next = formula.slice(0, start) + text + formula.slice(end)
    setFormula(next)
    requestAnimationFrame(() => {
      el.focus()
      const pos = start + text.length
      el.selectionStart = el.selectionEnd = pos
    })
  }

  useEffect(() => {
    setSuccessMessage(null)
    if (!formula.trim()) {
      setPreview(null)
      setPreviewError(null)
      return
    }
    setPreviewError(null)
    const timer = setTimeout(async () => {
      try {
        const { data } = await createColumn(sessionId, {
          name: name.trim() || '__preview__',
          formula,
          previewOnly: true,
          previewRows: 10,
        })
        setPreview(data)
      } catch (err) {
        setPreviewError(
          err?.response?.data?.error?.message || 'Formule invalide.',
        )
        setPreview(null)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formula, sessionId])

  const handleCreate = async () => {
    if (!name.trim() || !formula.trim()) return
    setIsSaving(true)
    setSaveError(null)
    setSuccessMessage(null)
    try {
      const { data } = await createColumn(sessionId, { name: name.trim(), formula, overwrite })
      setSuccessMessage(
        data.error_count > 0
          ? `Colonne "${data.name}" ajoutée (${data.error_count} valeur(s) n'ont pas pu être calculées).`
          : `Colonne "${data.name}" ajoutée avec succès.`,
      )
      setColumns(data.columns)
      setName('')
      setFormula('')
      setPreview(null)
      onColumnCreated?.()
    } catch (err) {
      setSaveError(
        err?.response?.data?.error?.message ||
          'Impossible de créer cette colonne.',
      )
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {columns.map((col) => (
          <button
            key={col}
            onClick={() => insertAtCursor(`{${col}}`)}
            className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {col}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <label className="flex flex-1 flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Nom de la nouvelle colonne</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ex: total_price"
            className="rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
          />
        </label>
        <label className="flex items-center gap-2 self-end pb-1.5 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
          Remplacer si la colonne existe déjà
        </label>
      </div>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-slate-600 dark:text-slate-300">Formule</span>
        <textarea
          ref={textareaRef}
          value={formula}
          onChange={(e) => setFormula(e.target.value)}
          placeholder='ex: {price} * {quantity}   ou   if({age} > 18, "adulte", "mineur")'
          rows={3}
          className="rounded-md border border-slate-300 px-3 py-2 font-mono text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
        />
      </label>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
        <p className="mb-1.5 font-medium text-slate-700 dark:text-slate-200">Fonctions et opérateurs disponibles</p>
        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {FUNCTION_REFERENCE.map(({ group, items }) => (
            <div key={group}>
              <span className="font-medium">{group} : </span>
              <span className="font-mono">{items.join('  ·  ')}</span>
            </div>
          ))}
        </div>
      </div>

      {previewError && (
        <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{previewError}</p>
      )}

      {preview && !previewError && (
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
          <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
            <thead className="bg-slate-100 dark:bg-slate-800">
              <tr>
                <th className="px-3 py-1.5 text-left font-semibold text-slate-700 dark:text-slate-200">
                  Aperçu du résultat ({preview.preview.length} premières lignes)
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
              {preview.preview.map((val, i) => (
                <tr key={i}>
                  <td className="px-3 py-1 text-slate-700 dark:text-slate-200">
                    {val === null ? <span className="italic text-slate-400 dark:text-slate-500">null</span> : String(val)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {preview.error_count > 0 && (
            <p className="border-t border-slate-200 bg-orange-50 px-3 py-1.5 text-xs text-orange-700 dark:border-slate-800 dark:bg-orange-950/40 dark:text-orange-300">
              {preview.error_count} valeur(s) sur cet aperçu n&apos;ont pas pu être calculées.
            </p>
          )}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleCreate}
          disabled={!name.trim() || !formula.trim() || isSaving || !!previewError}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
        >
          {isSaving ? 'Ajout en cours…' : 'Ajouter la colonne'}
        </button>
        {successMessage && <p className="text-sm text-green-700 dark:text-green-400">{successMessage}</p>}
      </div>

      {saveError && <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">{saveError}</p>}
    </div>
  )
}
