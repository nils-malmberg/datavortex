import { useEffect, useLayoutEffect, useRef, useState } from 'react'

const MENU_WIDTH = 240
const MENU_MARGIN = 8

/**
 * Menu contextuel d'une colonne (clic droit sur l'en-tête ou sur une cellule).
 * Regroupe les actions qui, sinon, obligeraient à quitter le tableau.
 */
export default function ColumnMenu({ column, position, onClose, onSort, onHide, onFilter, onStats, onCopy }) {
  const ref = useRef(null)
  const [clamped, setClamped] = useState(position)

  useEffect(() => {
    const close = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onClose()
    }
    const escape = (event) => event.key === 'Escape' && onClose()
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [onClose])

  // Empêche le menu de déborder de l'écran quand le clic droit a lieu près
  // d'un bord (colonnes de droite, bas de tableau...).
  useLayoutEffect(() => {
    const height = ref.current?.offsetHeight || 220
    const maxX = window.innerWidth - MENU_WIDTH - MENU_MARGIN
    const maxY = window.innerHeight - height - MENU_MARGIN
    setClamped({ x: Math.max(MENU_MARGIN, Math.min(position.x, maxX)), y: Math.max(MENU_MARGIN, Math.min(position.y, maxY)) })
  }, [position])

  const items = [
    { label: 'Trier ↑ (croissant)', action: () => onSort('asc') },
    { label: 'Trier ↓ (décroissant)', action: () => onSort('desc') },
    { label: 'Filtrer sur cette colonne', action: onFilter },
    { label: 'Statistiques de la colonne', action: onStats },
    { label: 'Copier le nom', action: onCopy },
    { label: 'Masquer la colonne', action: onHide, danger: true },
  ]

  return (
    <div
      ref={ref}
      style={{ top: clamped.y, left: clamped.x }}
      className="fixed z-50 w-60 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900"
    >
      <p className="truncate px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        {column}
      </p>
      {items.map((item) => (
        <button
          key={item.label}
          onClick={() => {
            item.action()
            onClose()
          }}
          className={`block w-full px-3 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800 ${
            item.danger ? 'text-red-600 dark:text-red-400' : 'text-slate-700 dark:text-slate-200'
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
