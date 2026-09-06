import { useEffect, useState } from 'react'
import { getPreview, mergeSessions } from '../api/client'

export default function MergeDialog({ tabs, onClose, onCreated }) {
  const [selectedIds, setSelectedIds] = useState([])
  const [mode, setMode] = useState('concat')
  const [keyColumn, setKeyColumn] = useState('')
  const [commonColumns, setCommonColumns] = useState([])
  const [isLoadingColumns, setIsLoadingColumns] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState(null)

  const toggleTab = (sessionId) => {
    setSelectedIds((prev) =>
      prev.includes(sessionId) ? prev.filter((id) => id !== sessionId) : [...prev, sessionId],
    )
  }

  useEffect(() => {
    if (mode !== 'merge' || selectedIds.length < 2) {
      setCommonColumns([])
      setKeyColumn('')
      return
    }
    let cancelled = false
    setIsLoadingColumns(true)
    Promise.all(selectedIds.map((id) => getPreview(id)))
      .then((responses) => {
        if (cancelled) return
        const columnSets = responses.map((r) => new Set(r.data.columns))
        const common = [...columnSets[0]].filter((col) => columnSets.every((set) => set.has(col)))
        setCommonColumns(common)
        setKeyColumn((prev) => (common.includes(prev) ? prev : common[0] || ''))
      })
      .catch(() => {
        if (!cancelled) setCommonColumns([])
      })
      .finally(() => {
        if (!cancelled) setIsLoadingColumns(false)
      })
    return () => {
      cancelled = true
    }
  }, [mode, selectedIds])

  const handleCreate = async () => {
    setError(null)
    if (selectedIds.length < 2) {
      setError('Sélectionnez au moins 2 fichiers.')
      return
    }
    if (mode === 'merge' && !keyColumn) {
      setError('Choisissez une colonne clé commune pour le merge.')
      return
    }
    setIsCreating(true)
    try {
      const { data } = await mergeSessions(selectedIds, mode, mode === 'merge' ? keyColumn : undefined)
      onCreated({
        sessionId: data.new_session_id,
        filename: data.filename,
        parseResult: {
          session_id: data.new_session_id,
          separator: null,
          n_rows: data.row_count,
          n_columns: data.column_count,
        },
      })
    } catch (err) {
      setError(
        err?.response?.data?.error?.message || 'Impossible de fusionner ces fichiers.',
      )
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="flex max-h-[90vh] w-full max-w-lg flex-col gap-4 overflow-y-auto rounded-xl bg-white p-6 shadow-xl dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-50">
            Fusionner des fichiers ouverts
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
          <p className="mb-2 text-sm font-medium text-slate-600 dark:text-slate-300">
            Sélectionnez les fichiers (2 ou plus)
          </p>
          <div className="flex flex-col gap-1.5">
            {tabs.map((tab) => (
              <label
                key={tab.sessionId}
                className="flex items-center gap-2 rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-200"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.includes(tab.sessionId)}
                  onChange={() => toggleTab(tab.sessionId)}
                />
                {tab.filename}
              </label>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Mode</span>
          <div className="flex gap-2">
            <button
              onClick={() => setMode('concat')}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                mode === 'concat'
                  ? 'bg-blue-600 text-white dark:bg-blue-500'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              Concatenate (lignes)
            </button>
            <button
              onClick={() => setMode('merge')}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                mode === 'merge'
                  ? 'bg-blue-600 text-white dark:bg-blue-500'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              Merge (colonnes)
            </button>
          </div>
        </div>

        {mode === 'merge' && (
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600 dark:text-slate-300">
              Colonne clé commune (jointure interne)
            </span>
            {isLoadingColumns ? (
              <span className="text-sm text-slate-400 dark:text-slate-500">Chargement des colonnes…</span>
            ) : selectedIds.length < 2 ? (
              <span className="text-sm text-slate-400 dark:text-slate-500">
                Sélectionnez au moins 2 fichiers.
              </span>
            ) : commonColumns.length === 0 ? (
              <span className="text-sm text-orange-600 dark:text-orange-400">
                Aucune colonne commune entre les fichiers sélectionnés.
              </span>
            ) : (
              <select
                value={keyColumn}
                onChange={(e) => setKeyColumn(e.target.value)}
                className="rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                {commonColumns.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            )}
          </label>
        )}

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
            onClick={handleCreate}
            disabled={isCreating || selectedIds.length < 2}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
          >
            {isCreating ? 'Fusion en cours…' : 'Create merged file'}
          </button>
        </div>
      </div>
    </div>
  )
}
