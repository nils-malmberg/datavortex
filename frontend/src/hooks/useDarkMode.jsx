import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const STORAGE_KEY = 'datavortex_theme'
const DarkModeContext = createContext(null)

function getInitialTheme() {
  // Le script inline dans index.html a déjà posé la classe "dark" sur <html>
  // avant le montage React (pour éviter un flash) : on part de cet état.
  if (typeof document !== 'undefined') {
    return document.documentElement.classList.contains('dark')
  }
  return false
}

export function DarkModeProvider({ children }) {
  const [isDark, setIsDark] = useState(getInitialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
    try {
      window.localStorage.setItem(STORAGE_KEY, isDark ? 'dark' : 'light')
    } catch {
      // stockage indisponible : le choix ne persistera pas entre sessions.
    }
  }, [isDark])

  const toggle = useCallback(() => setIsDark((prev) => !prev), [])

  return <DarkModeContext.Provider value={[isDark, toggle]}>{children}</DarkModeContext.Provider>
}

export default function useDarkMode() {
  const ctx = useContext(DarkModeContext)
  if (!ctx) {
    throw new Error('useDarkMode doit être utilisé à l\'intérieur de <DarkModeProvider>.')
  }
  return ctx
}
