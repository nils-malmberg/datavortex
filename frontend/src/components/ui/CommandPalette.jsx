import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * Palette de commandes (Ctrl+K) : accès direct à n'importe quel onglet ou
 * action sans quitter le clavier. Devient le moyen le plus rapide de naviguer
 * dès que le tableau de bord compte une dizaine d'onglets.
 */
function score(query, text) {
  const needle = query.toLowerCase()
  const haystack = text.toLowerCase()
  if (!needle) return 1
  const index = haystack.indexOf(needle)
  if (index === 0) return 3
  if (index > 0) return 2
  // Correspondance par initiales : « td » retrouve « Tableau de données ».
  let cursor = 0
  for (const char of needle) {
    cursor = haystack.indexOf(char, cursor)
    if (cursor === -1) return 0
    cursor += 1
  }
  return 1
}

export default function CommandPalette({ open, onClose, commands }) {
  const [query, setQuery] = useState('')
  const [highlighted, setHighlighted] = useState(0)
  const inputRef = useRef(null)

  const matches = useMemo(() => {
    return commands
      .map((command) => ({ command, rank: score(query, `${command.label} ${command.group || ''}`) }))
      .filter(({ rank }) => rank > 0)
      .sort((a, b) => b.rank - a.rank)
      .map(({ command }) => command)
  }, [commands, query])

  useEffect(() => {
    if (open) {
      setQuery('')
      setHighlighted(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  useEffect(() => {
    setHighlighted(0)
  }, [query])

  if (!open) return null

  const run = (command) => {
    onClose()
    command.action()
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setHighlighted((h) => Math.min(h + 1, matches.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlighted((h) => Math.max(h - 1, 0))
    } else if (event.key === 'Enter' && matches[highlighted]) {
      event.preventDefault()
      run(matches[highlighted])
    } else if (event.key === 'Escape') {
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 p-4 pt-24" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Rechercher un onglet ou une action…"
          className="w-full border-b border-slate-200 bg-transparent px-4 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 dark:border-slate-700 dark:text-slate-100"
        />
        <ul className="max-h-80 overflow-y-auto py-1">
          {matches.length === 0 && (
            <li className="px-4 py-3 text-sm text-slate-400 dark:text-slate-500">Aucune commande ne correspond.</li>
          )}
          {matches.map((command, index) => (
            <li key={command.id}>
              <button
                onMouseEnter={() => setHighlighted(index)}
                onClick={() => run(command)}
                className={`flex w-full items-center gap-3 px-4 py-2 text-left text-sm ${
                  index === highlighted
                    ? 'bg-blue-600 text-white dark:bg-blue-500'
                    : 'text-slate-700 dark:text-slate-200'
                }`}
              >
                <span className="flex-1 truncate">{command.label}</span>
                {command.group && (
                  <span className={`text-xs ${index === highlighted ? 'opacity-80' : 'text-slate-400 dark:text-slate-500'}`}>
                    {command.group}
                  </span>
                )}
                {command.shortcut && (
                  <kbd
                    className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
                      index === highlighted
                        ? 'border-white/40'
                        : 'border-slate-300 text-slate-500 dark:border-slate-600 dark:text-slate-400'
                    }`}
                  >
                    {command.shortcut}
                  </kbd>
                )}
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-slate-200 px-4 py-2 text-xs text-slate-400 dark:border-slate-700 dark:text-slate-500">
          ↑ ↓ pour naviguer · Entrée pour ouvrir · Échap pour fermer
        </p>
      </div>
    </div>
  )
}
