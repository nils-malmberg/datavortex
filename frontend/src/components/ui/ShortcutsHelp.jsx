import { SHORTCUT_HELP } from '../../hooks/useKeyboardShortcuts'

/** Fenêtre d'aide listant les raccourcis clavier disponibles. */
export default function ShortcutsHelp({ open, onClose }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">Raccourcis clavier</h3>
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="rounded px-2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-100"
          >
            ✕
          </button>
        </div>
        <ul className="flex flex-col gap-1.5">
          {SHORTCUT_HELP.map((item) => (
            <li key={item.keys} className="flex items-center justify-between gap-4 text-sm">
              <span className="text-slate-600 dark:text-slate-300">{item.description}</span>
              <kbd className="shrink-0 rounded border border-slate-300 bg-slate-50 px-2 py-0.5 font-mono text-xs text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
                {item.keys}
              </kbd>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
