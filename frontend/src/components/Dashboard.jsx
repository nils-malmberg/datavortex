import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { exportCsv, getRows } from '../api/client'
import { extractFilename } from '../api/download'
import DataPreview from './DataPreview'
import ReportBuilder from './ReportBuilder'
import CommandPalette from './ui/CommandPalette'
import ShortcutsHelp from './ui/ShortcutsHelp'
import useToast from './ui/ToastProvider'
import useDarkMode from '../hooks/useDarkMode'
import useKeyboardShortcuts from '../hooks/useKeyboardShortcuts'
import useSaveFile from '../hooks/useSaveFile'
import { BUTTON_CLASS, Loading, PRIMARY_BUTTON_CLASS } from './ui/common'

/*
 * Les panneaux lourds sont chargés à la demande : Plotly et scikit-learn côté
 * client pèsent plusieurs mégaoctets, inutiles tant que l'utilisateur reste
 * sur le tableau de données.
 */
const StatsPanel = lazy(() => import('./StatsPanel'))
const PlotBuilder = lazy(() => import('./PlotBuilder'))
const FilterBuilder = lazy(() => import('./FilterBuilder'))
const ColumnsPanel = lazy(() => import('./ColumnsPanel'))
const GroupByAnalysis = lazy(() => import('./GroupByAnalysis'))
const PivotTableBuilder = lazy(() => import('./PivotTableBuilder'))
const DataProfile = lazy(() => import('./DataProfile'))
const StatisticalTests = lazy(() => import('./StatisticalTests'))
const MLAnalysis = lazy(() => import('./MLAnalysis'))
const ExportData = lazy(() => import('./ExportData'))

const TABS = [
  { value: 'stats', label: 'Stats' },
  { value: 'plots', label: 'Visualisations' },
  { value: 'filters', label: 'Filtres' },
  { value: 'columns', label: 'Colonnes' },
  { value: 'groupby', label: 'Groupby' },
  { value: 'pivot', label: 'Pivot' },
  { value: 'profile', label: 'Profil' },
  { value: 'tests', label: 'Tests stats' },
  { value: 'ml', label: 'Machine Learning' },
  { value: 'export', label: 'Export' },
]

const LAYOUT_KEY = 'datavortex_layout'
const MIN_PREVIEW_HEIGHT = 160
const MAX_PREVIEW_HEIGHT = 900

function readLayout() {
  try {
    return JSON.parse(window.localStorage.getItem(LAYOUT_KEY) || '{}')
  } catch {
    return {}
  }
}

export default function Dashboard({ parseResult, filename, onReset, onInfoChange }) {
  const { session_id: sessionId, n_rows: nRows, n_columns: nColumns, separator } = parseResult
  const saved = readLayout()

  const [activeTab, setActiveTab] = useState('stats')
  const [dataVersion, setDataVersion] = useState(0)
  const [savedPlots, setSavedPlots] = useState([])
  const [isReportOpen, setIsReportOpen] = useState(false)
  const [isPaletteOpen, setIsPaletteOpen] = useState(false)
  const [isHelpOpen, setIsHelpOpen] = useState(false)
  const [previewCollapsed, setPreviewCollapsed] = useState(Boolean(saved.previewCollapsed))
  const [previewHeight, setPreviewHeight] = useState(saved.previewHeight || 460)
  const [tabOrder, setTabOrder] = useState(() => {
    const order = Array.isArray(saved.tabOrder) ? saved.tabOrder : []
    const known = TABS.map((t) => t.value)
    // Un onglet ajouté par une mise à jour doit apparaître même s'il est absent
    // de l'ordre enregistré par une version précédente.
    return [...order.filter((v) => known.includes(v)), ...known.filter((v) => !order.includes(v))]
  })
  const [dragTab, setDragTab] = useState(null)

  const toast = useToast()
  const saveFile = useSaveFile()
  const [isDark, toggleDark] = useDarkMode()
  const resizing = useRef(false)

  const bumpDataVersion = useCallback(() => setDataVersion((v) => v + 1), [])
  const handleAddPlotToReport = (plot) => {
    setSavedPlots((prev) => [...prev, plot])
    toast.success('Graphique ajouté au rapport.')
  }
  const handleRemovePlotFromReport = (id) => setSavedPlots((prev) => prev.filter((p) => p.id !== id))

  // --- Persistance de la disposition ---------------------------------------
  useEffect(() => {
    try {
      window.localStorage.setItem(
        LAYOUT_KEY,
        JSON.stringify({ previewCollapsed, previewHeight, tabOrder }),
      )
    } catch {
      // Disposition non persistée : sans effet sur le fonctionnement.
    }
  }, [previewCollapsed, previewHeight, tabOrder])

  // --- Redimensionnement de l'aperçu ---------------------------------------
  useEffect(() => {
    const onMove = (event) => {
      if (!resizing.current) return
      const next = event.clientY - resizing.current.top
      setPreviewHeight(Math.max(MIN_PREVIEW_HEIGHT, Math.min(MAX_PREVIEW_HEIGHT, next)))
    }
    const onUp = () => {
      resizing.current = false
      document.body.style.userSelect = ''
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [])

  // --- Informations pour la barre d'état -----------------------------------
  useEffect(() => {
    let cancelled = false
    // Une seule ligne suffit : on ne veut que les compteurs et l'empreinte mémoire.
    getRows(sessionId, { limit: 1 })
      .then(({ data }) => {
        if (cancelled) return
        onInfoChange?.({
          filename,
          rows: data.total_rows,
          rowsUnfiltered: data.total_rows_unfiltered,
          columns: data.columns.length,
          filtered: data.filtered,
          memory: data.memory_usage_bytes,
        })
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [sessionId, dataVersion, filename, onInfoChange])

  const handleExportCsv = useCallback(async () => {
    try {
      const response = await exportCsv(sessionId)
      const name = extractFilename(response.headers['content-disposition'], 'data.csv')
      await saveFile(response.data, name)
    } catch {
      toast.error("L'export CSV a échoué.")
    }
  }, [sessionId, toast, saveFile])

  const orderedTabs = useMemo(
    () => tabOrder.map((value) => TABS.find((t) => t.value === value)).filter(Boolean),
    [tabOrder],
  )

  const commands = useMemo(
    () => [
      ...orderedTabs.map((tab, index) => ({
        id: `tab-${tab.value}`,
        label: `Aller à « ${tab.label} »`,
        group: 'Navigation',
        shortcut: index < 9 ? String(index + 1) : undefined,
        action: () => setActiveTab(tab.value),
      })),
      {
        id: 'report',
        label: 'Générer un rapport PDF',
        group: 'Actions',
        shortcut: 'Ctrl+E',
        action: () => setIsReportOpen(true),
      },
      { id: 'csv', label: 'Exporter les données en CSV', group: 'Actions', shortcut: 'Ctrl+S', action: handleExportCsv },
      {
        id: 'theme',
        label: isDark ? 'Passer en thème clair' : 'Passer en thème sombre',
        group: 'Affichage',
        shortcut: 'Ctrl+D',
        action: toggleDark,
      },
      {
        id: 'preview',
        label: previewCollapsed ? "Afficher l'aperçu des données" : "Replier l'aperçu des données",
        group: 'Affichage',
        action: () => setPreviewCollapsed((v) => !v),
      },
      { id: 'help', label: 'Afficher les raccourcis clavier', group: 'Aide', shortcut: '?', action: () => setIsHelpOpen(true) },
      { id: 'reset', label: 'Charger un autre fichier', group: 'Actions', action: onReset },
    ],
    [orderedTabs, handleExportCsv, isDark, toggleDark, previewCollapsed, onReset],
  )

  const shortcuts = useMemo(() => {
    const bindings = {
      'mod+k': () => setIsPaletteOpen((v) => !v),
      'mod+s': handleExportCsv,
      'mod+e': () => setIsReportOpen(true),
      'mod+d': toggleDark,
      '?': () => setIsHelpOpen(true),
      escape: () => {
        setIsPaletteOpen(false)
        setIsHelpOpen(false)
        setIsReportOpen(false)
      },
    }
    orderedTabs.slice(0, 9).forEach((tab, index) => {
      bindings[String(index + 1)] = () => setActiveTab(tab.value)
    })
    return bindings
  }, [handleExportCsv, toggleDark, orderedTabs])

  useKeyboardShortcuts(shortcuts)

  const moveTab = (from, to) => {
    if (from === to || from == null || to == null) return
    const next = [...tabOrder]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    setTabOrder(next)
  }

  const panelProps = { sessionId, refreshKey: dataVersion }

  return (
    <div className="mx-auto flex w-full min-w-0 max-w-[1680px] flex-col gap-6 p-3 pb-12 sm:p-5 sm:pb-12 xl:p-8 xl:pb-14">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold text-slate-800 dark:text-slate-50 sm:text-xl">{filename}</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {nRows != null && nColumns != null ? `${nRows} lignes × ${nColumns} colonnes` : null}
            {separator ? ` — séparateur "${separator === '\t' ? '\\t' : separator}"` : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setIsPaletteOpen(true)}
            className={BUTTON_CLASS}
            title="Palette de commandes (Ctrl+K)"
          >
            <span className="hidden sm:inline">Commandes </span>
            <kbd className="font-mono text-xs">⌘K</kbd>
          </button>
          <button onClick={() => setIsReportOpen(true)} className={PRIMARY_BUTTON_CLASS}>
            Rapport PDF
          </button>
          <button onClick={onReset} className={BUTTON_CLASS}>
            Nouveau fichier
          </button>
        </div>
      </div>

      <div className="flex flex-col">
        <button
          onClick={() => setPreviewCollapsed((v) => !v)}
          className="self-start rounded px-1 text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
        >
          {previewCollapsed ? '▶ Afficher l’aperçu des données' : '▼ Replier l’aperçu des données'}
        </button>
        {!previewCollapsed && (
          <>
            <div style={{ height: previewHeight }} className="overflow-hidden">
              <DataPreview
                sessionId={sessionId}
                refreshKey={dataVersion}
                onRequestFilter={() => setActiveTab('filters')}
              />
            </div>
            <div
              onMouseDown={(event) => {
                resizing.current = { top: event.currentTarget.getBoundingClientRect().top - previewHeight }
                document.body.style.userSelect = 'none'
              }}
              role="separator"
              aria-orientation="horizontal"
              title="Glisser pour redimensionner l’aperçu"
              className="mx-auto mt-1 h-2 w-24 cursor-row-resize rounded-full bg-slate-200 transition-colors hover:bg-blue-400 dark:bg-slate-700 dark:hover:bg-blue-500"
            />
          </>
        )}
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-800">
          {orderedTabs.map((tab, index) => (
            <button
              key={tab.value}
              draggable
              onDragStart={() => setDragTab(index)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => {
                moveTab(dragTab, index)
                setDragTab(null)
              }}
              onDragEnd={() => setDragTab(null)}
              onClick={() => setActiveTab(tab.value)}
              title={index < 9 ? `Raccourci : ${index + 1}` : undefined}
              className={`-mb-px shrink-0 cursor-pointer whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.value
                  ? 'border-blue-600 text-blue-700 dark:border-blue-400 dark:text-blue-300'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <Suspense fallback={<Loading>Chargement du panneau…</Loading>}>
          {activeTab === 'stats' && <StatsPanel {...panelProps} />}
          {activeTab === 'plots' && <PlotBuilder {...panelProps} onAddToReport={handleAddPlotToReport} />}
          {activeTab === 'filters' && (
            <FilterBuilder sessionId={sessionId} onFilterApplied={bumpDataVersion} />
          )}
          {activeTab === 'columns' && (
            <ColumnsPanel sessionId={sessionId} onColumnsChanged={bumpDataVersion} />
          )}
          {activeTab === 'groupby' && <GroupByAnalysis {...panelProps} />}
          {activeTab === 'pivot' && <PivotTableBuilder {...panelProps} />}
          {activeTab === 'profile' && <DataProfile {...panelProps} />}
          {activeTab === 'tests' && <StatisticalTests {...panelProps} />}
          {activeTab === 'ml' && <MLAnalysis {...panelProps} onAddToReport={handleAddPlotToReport} />}
          {activeTab === 'export' && <ExportData {...panelProps} />}
        </Suspense>
      </div>

      {isReportOpen && (
        <ReportBuilder
          sessionId={sessionId}
          savedPlots={savedPlots}
          onRemovePlot={handleRemovePlotFromReport}
          onClose={() => setIsReportOpen(false)}
        />
      )}
      <CommandPalette open={isPaletteOpen} onClose={() => setIsPaletteOpen(false)} commands={commands} />
      <ShortcutsHelp open={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  )
}
