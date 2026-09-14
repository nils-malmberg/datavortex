import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getPreview, plotAdvanced, plotMultiSeries, plotSubplots } from '../api/client'
import ThemedPlot, { capturePlotThumbnail } from './ui/ThemedPlot'
import ExportPlot from './ExportPlot'
import PlotSidebar from './plot/PlotSidebar'
import PlotStylePanel from './plot/PlotStylePanel'
import PlotGallery from './plot/PlotGallery'
import MultiSeriesEditor, { makeSeries } from './plot/MultiSeriesEditor'
import SubplotsEditor, { makeSubplot } from './plot/SubplotsEditor'
import useToast from './ui/ToastProvider'
import { BUTTON_CLASS, Badge, ErrorBox, Loading, PRIMARY_BUTTON_CLASS } from './ui/common'
import {
  DEFAULT_SPEC,
  LAYOUT_MODES,
  buildMultiSeriesPayload,
  buildPayload,
  buildSubplotsPayload,
  describeSpec,
  isSpecComplete,
  plotConfig,
} from './plot/plotCatalog'

const NUMERIC_TYPES = ['integer', 'float']
const CATEGORICAL_TYPES = ['string', 'boolean']
const PRESET_STORAGE_KEY = 'datavortex_plot_presets'
const MAX_HISTORY = 40

function loadPresets() {
  try {
    const raw = window.localStorage.getItem(PRESET_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    // Stockage indisponible ou corrompu : on repart d'une liste vide.
    return []
  }
}

function savePresets(presets) {
  try {
    window.localStorage.setItem(PRESET_STORAGE_KEY, JSON.stringify(presets))
  } catch {
    // Le preset ne survivra pas au rechargement, sans conséquence fonctionnelle.
  }
}

/**
 * Atelier de visualisation (refonte Phase 8).
 *
 * Trois zones : le choix des données à gauche, un grand aperçu au centre, et
 * les options avancées repliables à droite. L'historique des configurations
 * permet de revenir en arrière après une exploration.
 */
export default function PlotBuilder({ sessionId, refreshKey, onAddToReport }) {
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})

  const [spec, setSpecState] = useState(DEFAULT_SPEC)
  const [history, setHistory] = useState([DEFAULT_SPEC])
  const [historyIndex, setHistoryIndex] = useState(0)

  const [figure, setFigure] = useState(null)
  const [trendStats, setTrendStats] = useState(null)
  const [lastPayload, setLastPayload] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const toast = useToast()

  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [showManagement, setShowManagement] = useState(false)
  const [presets, setPresets] = useState(loadPresets)
  const [gallery, setGallery] = useState([])
  const graphDiv = useRef(null)

  const numericColumns = useMemo(
    () => columns.filter((c) => NUMERIC_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )
  const categoricalColumns = useMemo(
    () => columns.filter((c) => CATEGORICAL_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )

  // L'index courant est lu dans un setState : une ref évite de recréer setSpec.
  const historyIndexRef = useRef(0)
  useEffect(() => {
    historyIndexRef.current = historyIndex
  }, [historyIndex])

  /** Applique une nouvelle configuration et l'empile dans l'historique. */
  const setSpec = useCallback((next) => {
    setSpecState(next)
    setHistory((prev) => {
      const truncated = prev.slice(0, historyIndexRef.current + 1)
      const appended = [...truncated, next].slice(-MAX_HISTORY)
      historyIndexRef.current = appended.length - 1
      setHistoryIndex(appended.length - 1)
      return appended
    })
  }, [])

  const undo = () => {
    if (historyIndex <= 0) return
    const index = historyIndex - 1
    setHistoryIndex(index)
    historyIndexRef.current = index
    setSpecState(history[index])
  }

  const redo = () => {
    if (historyIndex >= history.length - 1) return
    const index = historyIndex + 1
    setHistoryIndex(index)
    historyIndexRef.current = index
    setSpecState(history[index])
  }

  // --- Chargement des colonnes et valeurs par défaut cohérentes -------------
  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      const numeric = data.columns.filter((c) => NUMERIC_TYPES.includes(data.column_types[c]))
      const categorical = data.columns.filter((c) => CATEGORICAL_TYPES.includes(data.column_types[c]))
      const initial = {
        ...DEFAULT_SPEC,
        x: numeric[0] || data.columns[0] || '',
        y: numeric[1] || numeric[0] || '',
        group_by: categorical[0] || '',
      }
      setSpecState(initial)
      setHistory([initial])
      setHistoryIndex(0)
      historyIndexRef.current = 0
    })
  }, [sessionId, refreshKey])

  // --- Génération du graphique (débouncée) ---------------------------------
  useEffect(() => {
    if (columns.length === 0) return
    if (!isSpecComplete(spec)) {
      setFigure(null)
      setError(null)
      return
    }
    // Un mode = une route et une charge utile ; le reste de l'atelier (aperçu,
    // export, historique, presets) ne fait aucune différence entre les trois.
    const request = {
      multi_series: () => [buildMultiSeriesPayload(spec), plotMultiSeries],
      subplots: () => [buildSubplotsPayload(spec), plotSubplots],
    }[spec.layout_mode]
    const [payload, call] = request ? request() : [buildPayload(spec), plotAdvanced]

    setIsLoading(true)
    setError(null)
    const timer = setTimeout(async () => {
      try {
        const { data } = await call(sessionId, payload)
        setFigure(data.figure)
        setTrendStats(data.trend ?? null)
        setLastPayload(payload)
      } catch (err) {
        setError(err?.response?.data?.error?.message || 'Impossible de générer ce graphique.')
        setFigure(null)
        setTrendStats(null)
      } finally {
        setIsLoading(false)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(spec), sessionId, refreshKey, columns.length])

  /** Bascule de mode, en amorçant la configuration propre au mode visé.
   *
   * Sans amorçage, arriver en multi-séries ou en grille afficherait un panneau
   * vide : l'utilisateur doit d'abord tout construire avant de voir quoi que
   * ce soit. On part donc des colonnes numériques déjà choisies pour le mode
   * simple, ce qui donne un aperçu dès le changement de mode.
   */
  const switchLayoutMode = useCallback(
    (mode) => {
      if (mode === (spec.layout_mode || 'single')) return
      const patch = { layout_mode: mode }
      if (mode === 'multi_series' && (spec.series || []).length === 0) {
        const seed = spec.y || numericColumns[0]
        patch.x = spec.x || columns[0] || ''
        patch.series = seed ? [makeSeries(seed, 0)] : []
      }
      if (mode === 'subplots' && (spec.subplots || []).length === 0) {
        const grid = spec.subplot_grid || { rows: 2, cols: 2 }
        const x = spec.x || columns[0] || ''
        patch.subplots = Array.from({ length: grid.rows * grid.cols }, (_, i) =>
          makeSubplot(i, { x, y: numericColumns[i % Math.max(1, numericColumns.length)] || '' }),
        )
      }
      setSpec({ ...spec, ...patch })
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(spec), columns, numericColumns, setSpec],
  )

  // --- Presets --------------------------------------------------------------
  const handleSavePreset = (name) => {
    const next = [...presets, { id: crypto.randomUUID(), name, spec, createdAt: Date.now() }]
    setPresets(next)
    savePresets(next)
    toast.success(`Preset « ${name} » enregistré.`)
  }

  const handleLoadPreset = (preset) => {
    const missing = ['x', 'y', 'z', 'color_by', 'size_by', 'group_by']
      .map((field) => preset.spec[field])
      .filter((value) => value && !columns.includes(value))
    setSpec({ ...DEFAULT_SPEC, ...preset.spec })
    if (missing.length > 0) {
      toast.warning(`Preset chargé, mais ces colonnes sont absentes du fichier : ${[...new Set(missing)].join(', ')}.`)
    } else {
      toast.success(`Preset « ${preset.name} » chargé.`)
    }
  }

  const handleDeletePreset = (id) => {
    const next = presets.filter((p) => p.id !== id)
    setPresets(next)
    savePresets(next)
  }

  // --- Galerie --------------------------------------------------------------
  const captureCurrent = async () => {
    try {
      const thumbnail = await capturePlotThumbnail(graphDiv.current)
      setGallery((prev) => [
        ...prev,
        { id: crypto.randomUUID(), label: describeSpec(spec), thumbnail, spec },
      ])
      toast.success('Graphique ajouté à la galerie.')
    } catch {
      toast.error('Impossible de capturer ce graphique.')
    }
  }

  // --- Partage --------------------------------------------------------------
  const shareConfig = async () => {
    const text = JSON.stringify({ datavortex_plot: spec }, null, 2)
    try {
      await navigator.clipboard.writeText(text)
      toast.success('Configuration copiée dans le presse-papier — collez-la pour la réutiliser.')
    } catch {
      toast.error("Le presse-papier n'est pas accessible dans ce contexte.")
    }
  }

  const importConfig = async () => {
    try {
      const text = await navigator.clipboard.readText()
      const parsed = JSON.parse(text)
      if (!parsed?.datavortex_plot) {
        toast.warning('Le presse-papier ne contient pas une configuration DataVortex.')
        return
      }
      setSpec({ ...DEFAULT_SPEC, ...parsed.datavortex_plot })
      toast.success('Configuration importée.')
    } catch {
      toast.error('Impossible de lire une configuration valide depuis le presse-papier.')
    }
  }

  if (columns.length === 0) return <Loading>Chargement des colonnes…</Loading>

  const layoutMode = spec.layout_mode || 'single'
  // Taille intrinsèque de la figure (grille de sous-graphiques) ; un graphique
  // simple ne déclare rien et garde l'aperçu de 520 px.
  const gridMeta = figure?.layout?.meta?.grid
  const previewHeight = figure?.layout?.height || 520
  const previewMinWidth = gridMeta?.min_width
  const styleWidth = Math.round((spec.style.width * spec.style.dpi) / 100)
  const styleHeight = Math.round((spec.style.height * spec.style.dpi) / 100)
  // L'export ne descend jamais sous la taille intrinsèque (le serveur l'impose
  // aussi) ; on affiche la valeur réelle pour ne pas mentir dans le menu.
  const exportWidth = Math.max(styleWidth, previewMinWidth || 0)
  const exportHeight = Math.max(styleHeight, figure?.layout?.height || 0)
  // `kind` attendu par /api/export/plot et /api/report/pdf pour ce mode.
  const exportKind = { multi_series: 'multi-series', subplots: 'subplots' }[layoutMode] || 'advanced'
  const config = plotConfig(spec.plot_type)
  const missingFields =
    layoutMode === 'single'
      ? config.required.filter((f) => {
          const v = spec[f]
          return v === '' || v === undefined || v === null || (Array.isArray(v) && v.length === 0)
        })
      : isSpecComplete(spec)
        ? []
        : [layoutMode === 'multi_series' ? 'un axe X et au moins une série complète' : 'les colonnes de chaque case']

  return (
    <div className="flex flex-col gap-4">
      {/* Sélecteur de disposition : les trois modes de tracé vivent dans cet
          onglet, plutôt que dans des onglets séparés qui dupliquaient les
          options et laissaient l'utilisateur chercher où créer son graphique. */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
        <span className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Disposition
        </span>
        {LAYOUT_MODES.map((mode) => (
          <button
            key={mode.value}
            onClick={() => switchLayoutMode(mode.value)}
            title={mode.hint}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              layoutMode === mode.value
                ? 'bg-blue-600 text-white dark:bg-blue-500'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-4 lg:flex-row">
        {layoutMode === 'multi_series' ? (
          <MultiSeriesEditor
            spec={spec}
            onChange={setSpec}
            columns={columns}
            numericColumns={numericColumns}
          />
        ) : layoutMode === 'subplots' ? (
          <SubplotsEditor
            spec={spec}
            onChange={setSpec}
            columns={columns}
            numericColumns={numericColumns}
          />
        ) : (
          <PlotSidebar
            spec={spec}
            onChange={setSpec}
            columns={columns}
            numericColumns={numericColumns}
            categoricalColumns={categoricalColumns}
          />
        )}

        <div className="flex min-w-0 flex-1 flex-col gap-3">
          {missingFields.length > 0 ? (
            <div className="flex h-[480px] items-center justify-center rounded-lg border border-dashed border-slate-300 dark:border-slate-700">
              <p className="text-sm text-slate-400 dark:text-slate-500">
                Renseignez {missingFields.join(', ')} pour générer le graphique.
              </p>
            </div>
          ) : error ? (
            <div className="flex h-[480px] items-center justify-center rounded-lg border border-slate-200 dark:border-slate-800">
              <ErrorBox>{error}</ErrorBox>
            </div>
          ) : !figure ? (
            <div className="flex h-[480px] items-center justify-center rounded-lg border border-slate-200 dark:border-slate-800">
              <p className="text-sm text-slate-400 dark:text-slate-500">Génération du graphique…</p>
            </div>
          ) : (
            // Une grille de sous-graphiques déclare sa hauteur (500 px par
            // ligne) et sa largeur minimale (`layout.meta.grid`) : l'aperçu les
            // respecte et défile au lieu de comprimer les cases (Phase 10.4).
            <div className="max-h-[85vh] overflow-auto">
              <ThemedPlot
                data={figure.data}
                layout={figure.layout}
                height={previewHeight}
                minWidth={previewMinWidth}
                exportName={describeSpec(spec)}
                useFigureTheme={spec.style.theme !== 'auto'}
                onGraphDiv={(gd) => {
                  graphDiv.current = gd
                }}
              />
            </div>
          )}

          {/* Barre d'outils flottante : Personnaliser | Enregistrer | Exporter | Partager */}
          <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white/95 p-2 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
            <button
              onClick={() => setPanelCollapsed((v) => !v)}
              className={panelCollapsed ? PRIMARY_BUTTON_CLASS : BUTTON_CLASS}
            >
              Personnaliser
            </button>
            <button onClick={() => setShowManagement((v) => !v)} className={showManagement ? PRIMARY_BUTTON_CLASS : BUTTON_CLASS}>
              Enregistrer
            </button>
            <ExportPlot
              sessionId={sessionId}
              kind={exportKind}
              params={lastPayload}
              disabled={!figure || isLoading}
              compact
              width={exportWidth}
              height={exportHeight}
            />
            <button onClick={shareConfig} disabled={!figure} className={BUTTON_CLASS} title="Copier la configuration du graphique">
              Partager
            </button>
            <button onClick={importConfig} className={BUTTON_CLASS} title="Appliquer une configuration copiée">
              Importer
            </button>
            {onAddToReport && (
              <button
                onClick={() =>
                  onAddToReport({
                    id: crypto.randomUUID(),
                    kind: exportKind,
                    params: lastPayload,
                    label: describeSpec(spec),
                  })
                }
                disabled={!figure || isLoading}
                className={BUTTON_CLASS}
              >
                + Rapport
              </button>
            )}

            <span className="ml-auto flex items-center gap-1">
              <button onClick={undo} disabled={historyIndex <= 0} className={BUTTON_CLASS} title="Annuler (Ctrl+Z)">
                ↶
              </button>
              <button
                onClick={redo}
                disabled={historyIndex >= history.length - 1}
                className={BUTTON_CLASS}
                title="Rétablir (Ctrl+Maj+Z)"
              >
                ↷
              </button>
              <Badge tone="slate">
                {historyIndex + 1}/{history.length}
              </Badge>
            </span>
          </div>

        </div>

        <PlotStylePanel
          spec={spec}
          onChange={setSpec}
          trendStats={trendStats}
          collapsed={panelCollapsed}
          onToggleCollapsed={() => setPanelCollapsed((v) => !v)}
        />
      </div>

      {showManagement && (
        <PlotGallery
          presets={presets}
          onSavePreset={handleSavePreset}
          onLoadPreset={handleLoadPreset}
          onDeletePreset={handleDeletePreset}
          gallery={gallery}
          onOpenGalleryItem={(item) => setSpec({ ...DEFAULT_SPEC, ...item.spec })}
          onRemoveGalleryItem={(id) => setGallery((prev) => prev.filter((g) => g.id !== id))}
          onCaptureCurrent={captureCurrent}
          canCapture={Boolean(figure) && !isLoading}
        />
      )}
    </div>
  )
}
