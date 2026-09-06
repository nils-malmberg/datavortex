import { useCallback } from 'react'
import useToast from '../components/ui/ToastProvider'
import { triggerBlobDownload } from '../api/download'

const LAST_DIR_HINT_KEY = 'datavortex_last_save_kind'

function extensionOf(filename) {
  const idx = filename.lastIndexOf('.')
  return idx > 0 ? filename.slice(idx + 1).toLowerCase() : ''
}

/**
 * Enregistrement de fichier « intelligent » (Phase 8.1).
 *
 * Sur Chrome/Edge, `showSaveFilePicker` ouvre le VRAI sélecteur natif du
 * système d'exploitation : l'utilisateur choisit dossier + nom, exactement
 * comme dans n'importe quelle application de bureau. Aucun serveur ne peut
 * voir ni influencer ce choix (sandbox du navigateur) — c'est plus fiable et
 * plus sûr qu'une route backend qui écrirait un fichier à un chemin fourni
 * par le client (ouvrirait une faille d'écriture arbitraire côté serveur).
 * Sur les navigateurs sans cette API (Firefox, Safari), on retombe sur le
 * téléchargement classique du navigateur vers son dossier de téléchargements.
 */
export default function useSaveFile() {
  const toast = useToast()

  return useCallback(
    async (blob, suggestedName) => {
      const ext = extensionOf(suggestedName)
      if (typeof window.showSaveFilePicker === 'function') {
        try {
          const handle = await window.showSaveFilePicker({
            suggestedName,
            types: ext
              ? [{ description: `Fichier .${ext}`, accept: { [blob.type || 'application/octet-stream']: [`.${ext}`] } }]
              : undefined,
          })
          const writable = await handle.createWritable()
          await writable.write(blob)
          await writable.close()
          try {
            localStorage.setItem(LAST_DIR_HINT_KEY, ext)
          } catch {
            // stockage indisponible : sans conséquence, purement indicatif
          }
          toast.success(`Fichier enregistré : ${handle.name}`)
          return { status: 'saved', path: handle.name }
        } catch (err) {
          if (err?.name === 'AbortError') {
            return { status: 'cancelled' }
          }
          // API présente mais indisponible pour une autre raison (permission,
          // contexte non sécurisé...) : on se rabat sur le téléchargement.
        }
      }
      triggerBlobDownload(blob, suggestedName)
      toast.success(`Fichier téléchargé : ${suggestedName}`)
      return { status: 'saved', path: suggestedName }
    },
    [toast],
  )
}
