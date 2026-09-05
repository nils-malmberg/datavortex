import DataPreview from './DataPreview'
import StatsPanel from './StatsPanel'

export default function Dashboard({ parseResult, filename, onReset }) {
  const { session_id: sessionId, n_rows: nRows, n_columns: nColumns, separator } = parseResult

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-8 p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">{filename}</h2>
          <p className="text-sm text-slate-500">
            {nRows != null && nColumns != null ? `${nRows} lignes × ${nColumns} colonnes` : null}
            {separator ? ` — séparateur "${separator === '\t' ? '\\t' : separator}"` : ''}
          </p>
        </div>
        <button
          onClick={onReset}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          Nouveau fichier
        </button>
      </div>

      <DataPreview sessionId={sessionId} />
      <StatsPanel sessionId={sessionId} />
    </div>
  )
}
