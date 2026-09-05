import TabManager from './components/TabManager'
import ThemeToggle from './components/ThemeToggle'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4 dark:border-slate-800 dark:bg-slate-900">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">DataVortex</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Uploadez, explorez et analysez vos données
          </p>
        </div>
        <ThemeToggle />
      </header>

      <main>
        <TabManager />
      </main>
    </div>
  )
}
