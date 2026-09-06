import { SHORTCUT_HELP } from '../../hooks/useKeyboardShortcuts'
import { findTopic } from '../../help/helpContent'

/** Un bloc de contenu structuré (paragraphe, étapes, liste, note, code). */
function Block({ block }) {
  switch (block.kind) {
    case 'p':
      return <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{block.text}</p>
    case 'steps':
      return (
        <div>
          {block.title && (
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {block.title}
            </p>
          )}
          <ol className="list-decimal space-y-1 pl-5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            {block.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ol>
        </div>
      )
    case 'list':
      return (
        <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          {block.items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )
    case 'note':
      return (
        <p className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300">
          💡 {block.text}
        </p>
      )
    case 'code':
      return (
        <pre className="overflow-x-auto rounded-md bg-slate-100 px-3 py-2 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
          {block.text}
        </pre>
      )
    default:
      return null
  }
}

/** Corps généré dynamiquement pour les topics `dynamic: 'shortcuts'`. */
function ShortcutsBlock() {
  return (
    <ul className="flex flex-col gap-1.5">
      {SHORTCUT_HELP.map((item) => (
        <li
          key={item.keys}
          className="flex items-center justify-between gap-4 border-b border-slate-100 py-1.5 text-sm last:border-0 dark:border-slate-800"
        >
          <span className="text-slate-600 dark:text-slate-300">{item.description}</span>
          <kbd className="shrink-0 rounded border border-slate-300 bg-slate-50 px-2 py-0.5 font-mono text-xs text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {item.keys}
          </kbd>
        </li>
      ))}
    </ul>
  )
}

export default function HelpTopicView({ topic, onNavigate }) {
  if (!topic) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Sélectionnez un sujet dans le menu.</p>
  }

  const related = (topic.related || []).map(findTopic).filter(Boolean)

  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-blue-600 dark:text-blue-400">
          {topic.sectionTitle}
        </p>
        <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">{topic.title}</h3>
      </div>

      <div className="flex flex-col gap-3">
        {topic.body.map((block, i) => (
          <Block key={i} block={block} />
        ))}
        {topic.dynamic === 'shortcuts' && <ShortcutsBlock />}
      </div>

      {related.length > 0 && (
        <div className="mt-2 border-t border-slate-200 pt-3 dark:border-slate-800">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Voir aussi
          </p>
          <div className="flex flex-wrap gap-2">
            {related.map((t) => (
              <button
                key={t.id}
                onClick={() => onNavigate(t.id)}
                className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:border-blue-400 hover:text-blue-700 dark:border-slate-600 dark:text-slate-300 dark:hover:border-blue-500 dark:hover:text-blue-300"
              >
                {t.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
