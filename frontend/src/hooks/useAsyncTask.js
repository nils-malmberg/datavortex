import { useCallback, useEffect, useRef, useState } from 'react'
import { cancelTask, getTask } from '../api/client'

// Le premier sondage est rapproché — la plupart des calculs aboutissent en
// quelques centaines de millisecondes — puis l'intervalle s'allonge pour ne pas
// marteler le serveur pendant une agrégation longue.
const INITIAL_INTERVAL_MS = 250
const MAX_INTERVAL_MS = 3000
const BACKOFF_FACTOR = 1.4

/**
 * Suivi d'une opération exécutée en arrière-plan par le serveur (Phase 9).
 *
 * Le composant appelle `start(promise)` avec la requête qui crée la tâche, puis
 * ce hook interroge la route de statut jusqu'au verdict. L'interface reste
 * réactive pendant tout le calcul.
 *
 * Deux précautions qui font la différence en usage réel :
 * - le sondage s'arrête si le composant est démonté (changement d'onglet en
 *   cours de calcul), sinon il continue indéfiniment et écrit dans un état qui
 *   n'existe plus ;
 * - une tâche plus ancienne dont la réponse arrive en retard est ignorée, sinon
 *   deux calculs lancés coup sur coup peuvent s'écraser l'un l'autre.
 */
export default function useAsyncTask() {
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [elapsedMs, setElapsedMs] = useState(0)

  const currentTaskRef = useRef(null)
  const mountedRef = useRef(true)
  const timerRef = useRef(null)
  const startedAtRef = useRef(0)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const start = useCallback(
    async (createTask) => {
      stopPolling()
      setStatus('running')
      setResult(null)
      setError(null)
      setElapsedMs(0)
      startedAtRef.current = Date.now()

      let taskId
      try {
        const { data } = await createTask()
        taskId = data.task_id
      } catch (err) {
        if (!mountedRef.current) return
        // Erreur immédiate : session inconnue, requête invalide. Le serveur les
        // rejette avant de créer la tâche, précisément pour qu'on puisse les
        // afficher tout de suite plutôt qu'après un premier sondage.
        setError(err?.response?.data?.error?.message || 'Impossible de lancer le calcul.')
        setStatus('error')
        return
      }

      currentTaskRef.current = taskId
      let interval = INITIAL_INTERVAL_MS

      const poll = async () => {
        if (!mountedRef.current || currentTaskRef.current !== taskId) return

        let data
        try {
          ({ data } = await getTask(taskId))
        } catch (err) {
          if (!mountedRef.current || currentTaskRef.current !== taskId) return
          setError(err?.response?.data?.error?.message || 'Le suivi du calcul a été interrompu.')
          setStatus('error')
          return
        }

        if (!mountedRef.current || currentTaskRef.current !== taskId) return
        setElapsedMs(Date.now() - startedAtRef.current)

        if (data.status === 'done') {
          setResult(data.data)
          setStatus('done')
        } else if (data.status === 'error') {
          setError(data.error?.message || 'Le calcul a échoué.')
          setStatus('error')
        } else if (data.status === 'cancelled') {
          setStatus('cancelled')
        } else {
          interval = Math.min(interval * BACKOFF_FACTOR, MAX_INTERVAL_MS)
          timerRef.current = setTimeout(poll, interval)
        }
      }

      timerRef.current = setTimeout(poll, INITIAL_INTERVAL_MS)
    },
    [stopPolling],
  )

  const abort = useCallback(async () => {
    const taskId = currentTaskRef.current
    stopPolling()
    currentTaskRef.current = null
    setStatus('cancelled')
    if (taskId) {
      // Le calcul déjà lancé n'est pas interrompu côté serveur, mais son
      // résultat est écarté et la tâche libère sa place dans le registre.
      try {
        await cancelTask(taskId)
      } catch {
        // L'abandon est un confort : son échec ne doit rien changer pour l'utilisateur.
      }
    }
  }, [stopPolling])

  const reset = useCallback(() => {
    stopPolling()
    currentTaskRef.current = null
    setStatus('idle')
    setResult(null)
    setError(null)
    setElapsedMs(0)
  }, [stopPolling])

  return { status, result, error, elapsedMs, start, abort, reset, isRunning: status === 'running' }
}
