import { useMemo, useState } from 'react'
import { ALL_TOPICS } from '../../help/helpContent'

function textOf(topic) {
  const bodyText = topic.body.map((b) => b.text || (b.items || []).join(' ')).join(' ')
  return `${topic.title} ${topic.sectionTitle} ${(topic.keywords || []).join(' ')} ${bodyText}`.toLowerCase()
}

/** Recherche instantanée dans tous les sujets d'aide (titre, mots-clés, contenu). */
export default function HelpSearch({ onSelect }) {
  const [query, setQuery] = useState('')

  const results = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return ALL_TOPICS.filter((topic) => textOf(topic).includes(q)).slice(0, 12)
  }, [query])

  return (
    <div className="relative">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Rechercher dans l'aide… (ex : « groupby », « export », « ridge »)"
        aria-label="Rechercher dans l'aide"
        className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
      />
      {query.trim() && (
        <div className="absolute inset-x-0 top-full z-10 mt-1 max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
          {results.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-400 dark:text-slate-500">Aucun résultat pour « {query} ».</p>
          ) : (
            <ul>
              {results.map((topic) => (
                <li key={topic.id}>
                  <button
                    onClick={() => {
                      onSelect(topic.id)
                      setQuery('')
                    }}
                    className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{topic.title}</span>
                    <span className="text-xs text-slate-400 dark:text-slate-500">{topic.sectionTitle}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
