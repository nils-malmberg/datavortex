import { useState } from 'react'
import { BUTTON_CLASS, Badge, INPUT_CLASS, PRIMARY_BUTTON_CLASS, Panel } from '../ui/common'

/**
 * Gestion des graphiques : presets réutilisables (persistés) et galerie des
 * figures produites pendant la session (miniatures cliquables).
 */
export default function PlotGallery({
  presets,
  onSavePreset,
  onLoadPreset,
  onDeletePreset,
  gallery,
  onOpenGalleryItem,
  onRemoveGalleryItem,
  onCaptureCurrent,
  canCapture,
}) {
  const [presetName, setPresetName] = useState('')

  const save = () => {
    if (!presetName.trim()) return
    onSavePreset(presetName.trim())
    setPresetName('')
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Panel className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Presets de graphique</h4>
          <Badge tone="slate">{presets.length} enregistré(s)</Badge>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Un preset conserve la configuration complète (type, colonnes, tendance, style). Il reste disponible d&apos;une
          session à l&apos;autre et s&apos;applique à n&apos;importe quel fichier ayant les mêmes colonnes.
        </p>
        <div className="flex gap-2">
          <input
            className={`${INPUT_CLASS} flex-1`}
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && save()}
            placeholder="Nom du preset (ex. « scatter + tendance »)"
          />
          <button onClick={save} disabled={!presetName.trim()} className={PRIMARY_BUTTON_CLASS}>
            Créer le preset
          </button>
        </div>
        {presets.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">Aucun preset enregistré pour l&apos;instant.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {presets.map((preset) => (
              <li
                key={preset.id}
                className="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 dark:border-slate-700"
              >
                <span className="flex-1 truncate text-sm text-slate-700 dark:text-slate-200" title={preset.name}>
                  {preset.name}
                </span>
                <span className="hidden text-xs text-slate-400 dark:text-slate-500 sm:inline">
                  {preset.spec.plot_type}
                </span>
                <button onClick={() => onLoadPreset(preset)} className={BUTTON_CLASS}>
                  Charger
                </button>
                <button
                  onClick={() => onDeletePreset(preset.id)}
                  className="rounded px-1.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40"
                  aria-label={`Supprimer le preset ${preset.name}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Galerie</h4>
          <button onClick={onCaptureCurrent} disabled={!canCapture} className={BUTTON_CLASS}>
            + Ajouter le graphique courant
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Miniatures des graphiques capturés pendant cette session. Cliquez sur l&apos;une d&apos;elles pour recharger
          sa configuration exacte.
        </p>
        {gallery.length === 0 ? (
          <p className="text-sm text-slate-400 dark:text-slate-500">
            La galerie est vide : capturez un graphique pour le retrouver ici.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {gallery.map((item) => (
              <div key={item.id} className="group relative overflow-hidden rounded-md border border-slate-200 dark:border-slate-700">
                <button onClick={() => onOpenGalleryItem(item)} className="block w-full" title={item.label}>
                  <img src={item.thumbnail} alt={item.label} className="h-24 w-full bg-white object-cover" />
                  <span className="block truncate px-1.5 py-1 text-left text-[11px] text-slate-600 dark:text-slate-300">
                    {item.label}
                  </span>
                </button>
                <button
                  onClick={() => onRemoveGalleryItem(item.id)}
                  className="absolute right-1 top-1 rounded bg-white/90 px-1 text-xs text-red-600 opacity-0 transition-opacity group-hover:opacity-100 dark:bg-slate-900/90"
                  aria-label="Retirer de la galerie"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
