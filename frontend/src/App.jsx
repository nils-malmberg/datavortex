import { Suspense, lazy, useEffect, useState } from 'react'
import TabManager from './components/TabManager'
import ThemeToggle from './components/ThemeToggle'
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts'

// Chargé à la demande : contenu volumineux (60+ sujets), inutile tant que
// personne n'a ouvert l'aide.
const HelpPanel = lazy(() => import('./components/HelpPanel'))

export default function App() {
  const [isHelpOpen, setIsHelpOpen] = useState(false)

  // `datavortex --help-browser` ouvre directement l'appli sur ?help=1 :
  // même contenu d'aide que F1, pas de fichier statique séparé à maintenir.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('help') === '1') {
      setIsHelpOpen(true)
    }
  }, [])

  useKeyboardShortcuts({
    f1: () => setIsHelpOpen(true),
    'mod+h': () => setIsHelpOpen(true),
  })

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4 dark:border-slate-800 dark:bg-slate-900">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">DataVortex</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Uploadez, explorez et analysez vos données
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsHelpOpen(true)}
            title="Ouvrir l'aide (F1)"
            aria-label="Aide"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 text-sm font-semibold text-slate-500 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            ?
          </button>
          <ThemeToggle />
        </div>
      </header>

      <main>
        <TabManager />
      </main>

      {isHelpOpen && (
        <Suspense fallback={null}>
          <HelpPanel open={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
        </Suspense>
      )}
    </div>
  )
}
