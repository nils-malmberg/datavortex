import { useState } from 'react'
import {
  BUTTON_CLASS,
  Badge,
  FieldSelect,
  INPUT_CLASS,
  InfoTip,
  NumberField,
  Segmented,
  SliderField,
  Toggle,
  formatNumber,
} from '../ui/common'
import { COLORBLIND_MODES, LEGEND_POSITIONS, PALETTES, plotConfig } from './plotCatalog'

/**
 * Colonne de droite, repliable : tout ce qui relève de la mise en forme et de
 * l'analyse superposée (tendance, repères statistiques, palette, annotations).
 */
function Section({ title, children, hint, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-slate-200 last:border-b-0 dark:border-slate-800">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
      >
        <span className={`text-[10px] transition-transform ${open ? 'rotate-90' : ''}`}>▶</span>
        {title}
        {hint && <InfoTip text={hint} />}
      </button>
      {open && <div className="flex flex-col gap-3 px-3 pb-3">{children}</div>}
    </div>
  )
}

const TREND_TYPES = [
  { value: 'none', label: 'Aucune' },
  { value: 'linear', label: 'Linéaire' },
  { value: 'polynomial', label: 'Polynomiale' },
  { value: 'lowess', label: 'LOWESS' },
]

const CONFIDENCE_LEVELS = [
  { value: 'none', label: 'Aucune' },
  { value: '95', label: '95 %' },
  { value: '99', label: '99 %' },
]

const PERCENTILE_PRESETS = [5, 10, 25, 75, 90, 95]

export default function PlotStylePanel({ spec, onChange, trendStats, collapsed, onToggleCollapsed }) {
  const config = plotConfig(spec.plot_type)
  const setStyle = (patch) => onChange({ ...spec, style: { ...spec.style, ...patch } })
  const setTrend = (patch) => onChange({ ...spec, trend: { ...spec.trend, ...patch } })
  const setOverlays = (patch) => onChange({ ...spec, overlays: { ...spec.overlays, ...patch } })

  const [noteText, setNoteText] = useState('')
  const [noteX, setNoteX] = useState('')
  const [noteY, setNoteY] = useState('')

  const addAnnotation = () => {
    if (!noteText.trim() || noteX === '' || noteY === '') return
    setStyle({
      annotations: [...spec.style.annotations, { text: noteText.trim(), x: Number(noteX), y: Number(noteY), arrow: true, size: 12 }],
    })
    setNoteText('')
    setNoteX('')
    setNoteY('')
  }

  if (collapsed) {
    return (
      <button
        onClick={onToggleCollapsed}
        className="flex shrink-0 items-center gap-1 self-start rounded-lg border border-slate-300 bg-white px-2 py-3 text-xs font-medium text-slate-500 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800"
        title="Afficher les options avancées"
      >
        <span className="[writing-mode:vertical-rl]">Options avancées</span>
      </button>
    )
  }

  return (
    <aside className="w-full shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:w-72">
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-800">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
          Options avancées
        </h4>
        <button
          onClick={onToggleCollapsed}
          className="rounded px-1.5 text-sm text-slate-400 hover:text-slate-700 dark:hover:text-slate-100"
          title="Replier le panneau"
        >
          ✕
        </button>
      </div>

      <Section title="Courbe de tendance" defaultOpen hint="Ajuste un modèle sur (X, Y) et affiche son incertitude.">
        {!config.trend ? (
          <p className="text-xs text-slate-400 dark:text-slate-500">
            Indisponible pour ce type de graphique. Compatible avec scatter, line, bubble et joint plot.
          </p>
        ) : (
          <>
            <Segmented options={TREND_TYPES} value={spec.trend.type} onChange={(v) => setTrend({ type: v })} size="sm" />
            {spec.trend.type === 'polynomial' && (
              <SliderField
                label="Degré"
                value={spec.trend.degree}
                onChange={(v) => setTrend({ degree: v })}
                min={2}
                max={10}
                hint="Un degré élevé colle aux données mais généralise mal (surapprentissage)."
              />
            )}
            {spec.trend.type === 'lowess' && (
              <SliderField
                label="Fenêtre"
                value={spec.trend.frac}
                onChange={(v) => setTrend({ frac: v })}
                min={0.05}
                max={1}
                step={0.05}
                format={(v) => `${Math.round(v * 100)} %`}
                hint="Proportion de points utilisée pour chaque ajustement local. Plus large = plus lisse."
              />
            )}
            {spec.trend.type !== 'none' && (
              <>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="font-medium text-slate-600 dark:text-slate-300">Bande de confiance</span>
                  <Segmented
                    options={CONFIDENCE_LEVELS}
                    value={spec.trend.confidence}
                    onChange={(v) => setTrend({ confidence: v })}
                    size="sm"
                  />
                </label>
                <Toggle
                  label="Afficher l'équation"
                  checked={spec.trend.show_equation}
                  onChange={(v) => setTrend({ show_equation: v })}
                />
              </>
            )}
            {trendStats && (
              <div className="rounded-md bg-slate-50 p-2 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                {trendStats.equation && <p className="break-words font-medium">{trendStats.equation}</p>}
                <p>
                  R² = {formatNumber(trendStats.r2, 4)}
                  {trendStats.adjusted_r2 !== null && ` · R² ajusté = ${formatNumber(trendStats.adjusted_r2, 4)}`}
                </p>
                <p>
                  RMSE = {formatNumber(trendStats.rmse, 4)} · n = {trendStats.n}
                </p>
                {trendStats.type === 'lowess' && (
                  <p className="mt-1 text-slate-400 dark:text-slate-500">
                    LOWESS n&apos;a pas d&apos;équation : c&apos;est un lissage local, pas un modèle paramétrique.
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </Section>

      <Section title="Repères statistiques" hint="Superpose moyenne, médiane, écarts-types et percentiles.">
        <Toggle label="Moyenne" checked={spec.overlays.mean} onChange={(v) => setOverlays({ mean: v })} />
        <Toggle label="Médiane" checked={spec.overlays.median} onChange={(v) => setOverlays({ median: v })} />
        <Toggle label="Bandes ±σ" checked={spec.overlays.std} onChange={(v) => setOverlays({ std: v })} />
        {spec.overlays.std && (
          <SliderField
            label="Nombre de σ"
            value={spec.overlays.std_sigmas}
            onChange={(v) => setOverlays({ std_sigmas: v })}
            min={1}
            max={3}
          />
        )}
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Percentiles</span>
          <div className="flex flex-wrap gap-1">
            {PERCENTILE_PRESETS.map((p) => {
              const active = spec.overlays.percentiles.includes(p)
              return (
                <button
                  key={p}
                  onClick={() =>
                    setOverlays({
                      percentiles: active
                        ? spec.overlays.percentiles.filter((v) => v !== p)
                        : [...spec.overlays.percentiles, p].sort((a, b) => a - b),
                    })
                  }
                  className={`rounded-md border px-2 py-0.5 text-xs font-medium ${
                    active
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
                      : 'border-slate-300 text-slate-600 dark:border-slate-600 dark:text-slate-300'
                  }`}
                >
                  P{p}
                </button>
              )
            })}
          </div>
        </div>
      </Section>

      <Section title="Couleurs" hint="Palette et rendu pour les daltonismes les plus fréquents.">
        <FieldSelect label="Palette" value={spec.style.palette} onChange={(v) => setStyle({ palette: v })} options={PALETTES} />
        <FieldSelect
          label="Vision des couleurs"
          value={spec.style.colorblind_mode}
          onChange={(v) => setStyle({ colorblind_mode: v })}
          options={COLORBLIND_MODES}
          hint="« Palette sûre » applique Okabe-Ito. Les modes « Simuler » montrent la figure telle qu'elle est perçue."
        />
        {spec.style.colorblind_mode.startsWith('simul') === false && spec.style.colorblind_mode !== 'none' &&
          spec.style.colorblind_mode !== 'safe' && (
            <Badge tone="amber">Aperçu de perception — les couleurs affichées sont transformées</Badge>
          )}
      </Section>

      <Section title="Axes et légende">
        <div className="flex gap-2">
          <FieldSelect
            label="Échelle X"
            value={spec.style.x_scale}
            onChange={(v) => setStyle({ x_scale: v })}
            options={[{ value: 'linear', label: 'Linéaire' }, { value: 'log', label: 'Log' }]}
          />
          <FieldSelect
            label="Échelle Y"
            value={spec.style.y_scale}
            onChange={(v) => setStyle({ y_scale: v })}
            options={[{ value: 'linear', label: 'Linéaire' }, { value: 'log', label: 'Log' }]}
          />
        </div>
        <FieldSelect
          label="Position de la légende"
          value={spec.style.legend_position}
          onChange={(v) => setStyle({ legend_position: v })}
          options={LEGEND_POSITIONS}
        />
        <Toggle label="Grille" checked={spec.style.grid} onChange={(v) => setStyle({ grid: v })} />
        <FieldSelect
          label="Thème de la figure"
          value={spec.style.theme}
          onChange={(v) => setStyle({ theme: v })}
          options={[
            { value: 'auto', label: 'Suivre l’interface' },
            { value: 'light', label: 'Clair' },
            { value: 'dark', label: 'Sombre' },
          ]}
        />
      </Section>

      <Section title="Textes">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Titre</span>
          <input
            className={INPUT_CLASS}
            value={spec.style.title}
            onChange={(e) => setStyle({ title: e.target.value })}
            placeholder="Titre automatique"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Sous-titre</span>
          <input
            className={INPUT_CLASS}
            value={spec.style.subtitle}
            onChange={(e) => setStyle({ subtitle: e.target.value })}
            placeholder="Optionnel"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Légende axe X</span>
          <input className={INPUT_CLASS} value={spec.style.x_label} onChange={(e) => setStyle({ x_label: e.target.value })} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Légende axe Y</span>
          <input className={INPUT_CLASS} value={spec.style.y_label} onChange={(e) => setStyle({ y_label: e.target.value })} />
        </label>
      </Section>

      <Section title="Annotations" hint="Ajoute un commentaire fléché à des coordonnées précises du graphique.">
        <input
          className={INPUT_CLASS}
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          placeholder="Texte de l'annotation"
        />
        <div className="flex gap-2">
          <NumberField label="X" value={noteX} onChange={setNoteX} step="any" />
          <NumberField label="Y" value={noteY} onChange={setNoteY} step="any" />
        </div>
        <button onClick={addAnnotation} disabled={!noteText.trim() || noteX === '' || noteY === ''} className={BUTTON_CLASS}>
          Ajouter l&apos;annotation
        </button>
        {spec.style.annotations.map((note, i) => (
          <div key={i} className="flex items-center gap-2 rounded-md bg-slate-50 px-2 py-1 text-xs dark:bg-slate-800/60">
            <span className="flex-1 truncate text-slate-600 dark:text-slate-300">
              {note.text} ({note.x}, {note.y})
            </span>
            <button
              onClick={() => setStyle({ annotations: spec.style.annotations.filter((_, j) => j !== i) })}
              className="text-red-500 hover:text-red-700"
              aria-label="Supprimer l'annotation"
            >
              ✕
            </button>
          </div>
        ))}
      </Section>

      <Section title="Dimensions d'export" hint="Utilisé lors de l'export PNG/SVG : la taille du fichier produit.">
        <div className="flex gap-2">
          <NumberField label="Largeur" value={spec.style.width} onChange={(v) => setStyle({ width: v })} min={200} max={4000} suffix="px" />
          <NumberField label="Hauteur" value={spec.style.height} onChange={(v) => setStyle({ height: v })} min={200} max={4000} suffix="px" />
        </div>
        <FieldSelect
          label="DPI"
          value={String(spec.style.dpi)}
          onChange={(v) => setStyle({ dpi: Number(v) })}
          options={[
            { value: '72', label: '72 (écran)' },
            { value: '100', label: '100 (standard)' },
            { value: '300', label: '300 (impression)' },
          ]}
        />
        <p className="text-xs text-slate-400 dark:text-slate-500">
          À {spec.style.dpi} DPI, l&apos;image exportée fera {Math.round((spec.style.width * spec.style.dpi) / 100)} ×{' '}
          {Math.round((spec.style.height * spec.style.dpi) / 100)} px, soit{' '}
          {(spec.style.width / 100).toFixed(1)} × {(spec.style.height / 100).toFixed(1)} pouces.
        </p>
      </Section>
    </aside>
  )
}
