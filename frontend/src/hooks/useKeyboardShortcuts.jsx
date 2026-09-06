import { useEffect } from 'react'

/**
 * Raccourcis clavier globaux.
 *
 * Les raccourcis sont ignorés pendant la saisie dans un champ, sauf ceux qui
 * doivent rester disponibles partout (palette de commandes, aide) : sinon
 * taper « ? » dans une recherche ouvrirait l'aide au lieu d'écrire.
 */
const ALWAYS_ACTIVE = new Set(['mod+k', 'escape', 'f1', 'mod+h'])

function isTypingTarget(target) {
  if (!target) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

function describe(event) {
  const parts = []
  if (event.ctrlKey || event.metaKey) parts.push('mod')
  if (event.shiftKey) parts.push('shift')
  if (event.altKey) parts.push('alt')
  parts.push(event.key.toLowerCase())
  return parts.join('+')
}

export default function useKeyboardShortcuts(bindings) {
  useEffect(() => {
    const onKeyDown = (event) => {
      const combination = describe(event)
      const handler = bindings[combination]
      if (!handler) return
      if (isTypingTarget(event.target) && !ALWAYS_ACTIVE.has(combination)) return
      event.preventDefault()
      handler(event)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [bindings])
}

/** Liste lisible des raccourcis, pour l'écran d'aide. */
export const SHORTCUT_HELP = [
  { keys: 'Ctrl + K', description: 'Ouvrir la palette de commandes' },
  { keys: 'Ctrl + F', description: 'Rechercher dans le tableau de données' },
  { keys: 'Ctrl + S', description: 'Exporter les données en CSV' },
  { keys: 'Ctrl + E', description: 'Ouvrir le générateur de rapport PDF' },
  { keys: 'Ctrl + D', description: 'Basculer entre thème clair et sombre' },
  { keys: '1 … 9', description: "Aller directement à l'onglet correspondant" },
  { keys: '?', description: 'Afficher les raccourcis clavier' },
  { keys: 'F1', description: "Ouvrir l'aide complète" },
  { keys: 'Ctrl + H', description: "Ouvrir l'aide complète" },
  { keys: 'Échap', description: 'Fermer la fenêtre ouverte' },
]
