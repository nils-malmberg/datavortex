import { useState } from 'react'
import DataPreview from './DataPreview'
import StatsPanel from './StatsPanel'
import PlotBuilder from './PlotBuilder'

const TABS = [
  { value: 'stats', label: 'Stats' },
  { value: 'plots', label: 'Visualisations' },
]

export default function Dashboard({ parseResult, filename, onReset }) {
  const { session_id: sessionId, n_rows: nRows, n_columns: nColumns, separator } = parseResult
  const [activeTab, setActiveTab] = useState('stats')

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

      <div className="flex flex-col gap-4">
        <div className="flex gap-2 border-b border-slate-200">
          {TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.value
                  ? 'border-blue-600 text-blue-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'stats' && <StatsPanel sessionId={sessionId} />}
        {activeTab === 'plots' && <PlotBuilder sessionId={sessionId} />}
      </div>
    </div>
  )
}
