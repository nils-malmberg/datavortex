import { useEffect, useMemo, useState } from 'react'
import { ALL_TOPICS, HELP_SECTIONS, findTopic } from '../help/helpContent'
import HelpSearch from './help/HelpSearch'
import HelpTopicView from './help/HelpTopicView'

/**
 * Panneau d'aide intégrée (F1 / Ctrl+H / bouton « ? » du header).
 *
 * Navigation à deux niveaux (sections repliables + sujets) sur desktop ;
 * un simple menu déroulant remplace la barre latérale sous md, pour rester
 * utilisable en plein écran sur mobile sans double défilement imbriqué.
 */
export default function HelpPanel({ open, onClose, initialTopicId }) {
  const [selectedId, setSelectedId] = useState(initialTopicId || ALL_TOPICS[0].id)
  const [openSections, setOpenSections] = useState(() => new Set([HELP_SECTIONS[0].id]))

  useEffect(() => {
    if (open && initialTopicId) {
      setSelectedId(initialTopicId)
      const section = HELP_SECTIONS.find((s) => s.topics.some((t) => t.id === initialTopicId))
      if (section) setOpenSections((prev) => new Set(prev).add(section.id))
    }
  }, [open, initialTopicId])

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  const selectedTopic = useMemo(() => findTopic(selectedId), [selectedId])

  const navigate = (id) => {
    setSelectedId(id)
    const section = HELP_SECTIONS.find((s) => s.topics.some((t) => t.id === id))
    if (section) setOpenSections((prev) => new Set(prev).add(section.id))
  }

  const toggleSection = (id) => {
    setOpenSections((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-2 sm:p-6" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Aide et documentation"
        className="flex h-full w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900 sm:h-[85vh]"
      >
        <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Aide &amp; documentation</h2>
          <button
            onClick={onClose}
            aria-label="Fermer l'aide"
            className="rounded px-2 py-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-100"
          >
            ✕
          </button>
        </div>

        <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800">
          <HelpSearch onSelect={navigate} />
        </div>

        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          {/* Barre latérale : accordéon par section, visible à partir de md. */}
          <nav
            aria-label="Sujets d'aide"
            className="hidden w-64 shrink-0 overflow-y-auto border-r border-slate-200 p-2 dark:border-slate-800 md:block"
          >
            {HELP_SECTIONS.map((section) => (
              <div key={section.id} className="mb-1">
                <button
                  onClick={() => toggleSection(section.id)}
                  className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  {section.title}
                  <span>{openSections.has(section.id) ? '▾' : '▸'}</span>
                </button>
                {openSections.has(section.id) && (
                  <ul className="mt-0.5 flex flex-col">
                    {section.topics.map((topic) => (
                      <li key={topic.id}>
                        <button
                          onClick={() => navigate(topic.id)}
                          aria-current={selectedId === topic.id}
                          className={`w-full rounded px-3 py-1.5 text-left text-sm ${
                            selectedId === topic.id
                              ? 'bg-blue-600 text-white dark:bg-blue-500'
                              : 'text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800'
                          }`}
                        >
                          {topic.title}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </nav>

          {/* Sélecteur mobile : remplace la barre latérale sous md. */}
          <div className="border-b border-slate-200 p-2 dark:border-slate-800 md:hidden">
            <select
              value={selectedId}
              onChange={(e) => navigate(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-2 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
            >
              {HELP_SECTIONS.map((section) => (
                <optgroup key={section.id} label={section.title}>
                  {section.topics.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.title}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
            <HelpTopicView topic={selectedTopic} onNavigate={navigate} />
          </div>
        </div>

        <p className="border-t border-slate-200 px-4 py-2 text-xs text-slate-400 dark:border-slate-700 dark:text-slate-500">
          F1 ou Ctrl+H pour rouvrir cette aide · Échap pour fermer
        </p>
      </div>
    </div>
  )
}
