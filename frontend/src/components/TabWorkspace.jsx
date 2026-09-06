import UploadZone from './UploadZone'
import SeparatorSelector from './SeparatorSelector'
import Dashboard from './Dashboard'

// Rend l'étape courante (upload -> séparateur -> dashboard) d'un onglet donné.
// La clé sur Dashboard force un remontage complet à chaque changement de
// session (changement d'onglet ou nouveau fichier), pour repartir d'un état
// propre plutôt que de faire fuir de l'état entre deux fichiers différents.
export default function TabWorkspace({
  tab,
  onUploaded,
  onParsed,
  onReset,
  mergeableTabs,
  onOpenMergeDialog,
}) {
  if (tab.step === 'upload') {
    return (
      <UploadZone
        onUploaded={onUploaded}
        mergeableTabs={mergeableTabs}
        onOpenMergeDialog={onOpenMergeDialog}
      />
    )
  }

  if (tab.step === 'separator' && tab.uploadData) {
    return (
      <SeparatorSelector uploadData={tab.uploadData} onParsed={onParsed} onCancel={onReset} />
    )
  }

  if (tab.step === 'dashboard' && tab.parseResult) {
    return (
      <Dashboard
        key={tab.sessionId}
        parseResult={tab.parseResult}
        filename={tab.filename}
        onReset={onReset}
      />
    )
  }

  return null
}
