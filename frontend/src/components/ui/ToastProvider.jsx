import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

/**
 * Notifications éphémères.
 *
 * Les messages de succès disparaissent seuls ; les erreurs restent affichées
 * jusqu'à fermeture, car elles demandent une décision de l'utilisateur et ne
 * doivent pas s'évanouir avant d'avoir été lues.
 */
const ToastContext = createContext(null)

const DEFAULT_DURATIONS = { success: 3000, info: 4000, warning: 6000, error: 0 }

const TONES = {
  success: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200',
  info: 'border-blue-300 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950/60 dark:text-blue-200',
  warning: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-200',
  error: 'border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200',
}

const ICONS = { success: '✓', info: 'i', warning: '!', error: '✕' }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const notify = useCallback(
    (message, { type = 'info', title, duration } = {}) => {
      const id = crypto.randomUUID()
      setToasts((prev) => [...prev.slice(-4), { id, message, type, title }])
      const delay = duration ?? DEFAULT_DURATIONS[type]
      if (delay > 0) {
        timers.current.set(id, setTimeout(() => dismiss(id), delay))
      }
      return id
    },
    [dismiss],
  )

  const value = useMemo(
    () => ({
      notify,
      dismiss,
      success: (message, options) => notify(message, { ...options, type: 'success' }),
      error: (message, options) => notify(message, { ...options, type: 'error' }),
      warning: (message, options) => notify(message, { ...options, type: 'warning' }),
      info: (message, options) => notify(message, { ...options, type: 'info' }),
    }),
    [notify, dismiss],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-14 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border p-3 shadow-lg ${TONES[toast.type]}`}
          >
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/60 text-xs font-bold dark:bg-black/30">
              {ICONS[toast.type]}
            </span>
            <span className="min-w-0 flex-1 text-sm">
              {toast.title && <span className="block font-semibold">{toast.title}</span>}
              <span className="block break-words">{toast.message}</span>
            </span>
            <button
              onClick={() => dismiss(toast.id)}
              aria-label="Fermer la notification"
              className="shrink-0 rounded px-1 text-sm opacity-60 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export default function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast doit être utilisé à l’intérieur de <ToastProvider>.')
  return context
}
