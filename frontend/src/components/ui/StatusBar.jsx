import { Badge } from './common'

/**
 * Barre d'état permanente : ce qui est chargé, ce qui est filtré, ce que ça
 * coûte en mémoire. Reste visible quel que soit l'onglet consulté.
 */
function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(2)} Mo`
}

export default function StatusBar({ info, openTabs, onShowShortcuts }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-30 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-200 bg-white/95 px-4 py-1.5 text-xs text-slate-600 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95 dark:text-slate-300">
      {info ? (
        <>
          <span className="truncate font-medium text-slate-700 dark:text-slate-200" title={info.filename}>
            {info.filename}
          </span>
          <span className="tabular-nums">
            {info.rows?.toLocaleString('fr-FR')} lignes × {info.columns} colonnes
          </span>
          {info.filtered && (
            <Badge tone="blue">
              filtré : {info.rows?.toLocaleString('fr-FR')} / {info.rowsUnfiltered?.toLocaleString('fr-FR')}
            </Badge>
          )}
          <span className="tabular-nums" title="Empreinte mémoire du jeu de données côté serveur">
            {formatBytes(info.memory)}
          </span>
        </>
      ) : (
        <span className="text-slate-400 dark:text-slate-500">Aucun fichier chargé</span>
      )}
      <span className="ml-auto flex items-center gap-3">
        <span title="Fichiers ouverts simultanément">{openTabs} onglet(s)</span>
        <button
          onClick={onShowShortcuts}
          className="rounded px-1.5 py-0.5 hover:bg-slate-100 dark:hover:bg-slate-800"
          title="Afficher les raccourcis clavier"
        >
          <kbd className="font-mono">?</kbd> raccourcis
        </button>
      </span>
    </div>
  )
}
