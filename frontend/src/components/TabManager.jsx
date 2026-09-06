import { useEffect, useState } from 'react'
import { deleteSession, getPreview } from '../api/client'
import TabWorkspace from './TabWorkspace'
import MergeDialog from './MergeDialog'
import StatusBar from './ui/StatusBar'
import ShortcutsHelp from './ui/ShortcutsHelp'

const STORAGE_KEY = 'datavortex_tabs'

function makeClientId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `tab_${Date.now()}_${Math.random().toString(36).slice(2)}`
}

function makeUploadTab() {
  return {
    clientId: makeClientId(),
    sessionId: null,
    filename: null,
    step: 'upload',
    uploadData: null,
    parseResult: null,
  }
}

function persistTabs(tabs) {
  try {
    const toSave = tabs
      .filter((t) => t.step === 'dashboard' && t.sessionId)
      .map((t) => ({
        clientId: t.clientId,
        sessionId: t.sessionId,
        filename: t.filename,
        separator: t.parseResult?.separator ?? null,
        nRows: t.parseResult?.n_rows ?? null,
        nColumns: t.parseResult?.n_columns ?? null,
      }))
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch {
    // localStorage indisponible : les onglets ne survivront pas à un rafraîchissement.
  }
}

export default function TabManager() {
  const [tabs, setTabs] = useState([])
  const [activeTabId, setActiveTabId] = useState(null)
  const [isRestoring, setIsRestoring] = useState(true)
  const [isMergeDialogOpen, setIsMergeDialogOpen] = useState(false)
  // Informations affichées en barre d'état, remontées par l'onglet actif.
  const [statusInfo, setStatusInfo] = useState(null)
  const [isHelpOpen, setIsHelpOpen] = useState(false)

  // Restaure les onglets sauvegardés au montage, en validant que chaque
  // session existe toujours côté backend (elle a pu expirer après 1h, ou le
  // serveur a pu redémarrer depuis).
  useEffect(() => {
    let cancelled = false

    async function restore() {
      let saved = []
      try {
        const raw = window.localStorage.getItem(STORAGE_KEY)
        if (raw) saved = JSON.parse(raw)
      } catch {
        saved = []
      }

      const restored = []
      for (const t of Array.isArray(saved) ? saved : []) {
        if (!t?.sessionId) continue
        try {
          const { data } = await getPreview(t.sessionId)
          restored.push({
            clientId: t.clientId || makeClientId(),
            sessionId: t.sessionId,
            filename: t.filename || null,
            step: 'dashboard',
            uploadData: null,
            parseResult: {
              session_id: t.sessionId,
              separator: t.separator ?? null,
              n_rows: t.nRows ?? data.total_rows,
              n_columns: t.nColumns ?? data.total_columns,
            },
          })
        } catch {
          // Session expirée ou backend redémarré : cet onglet ne peut pas être restauré.
        }
      }

      if (cancelled) return
      if (restored.length > 0) {
        setTabs(restored)
        setActiveTabId(restored[0].clientId)
      } else {
        const fresh = makeUploadTab()
        setTabs([fresh])
        setActiveTabId(fresh.clientId)
      }
      setIsRestoring(false)
    }

    restore()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (isRestoring) return
    persistTabs(tabs)
  }, [tabs, isRestoring])

  const activeTab = tabs.find((t) => t.clientId === activeTabId) || null

  const updateTab = (clientId, patch) => {
    setTabs((prev) => prev.map((t) => (t.clientId === clientId ? { ...t, ...patch } : t)))
  }

  const addTab = () => {
    const fresh = makeUploadTab()
    setTabs((prev) => [...prev, fresh])
    setActiveTabId(fresh.clientId)
  }

  const closeTab = (clientId) => {
    const closedTab = tabs.find((t) => t.clientId === clientId)
    if (closedTab?.sessionId) {
      deleteSession(closedTab.sessionId).catch(() => {})
    }

    const closedIndex = tabs.findIndex((t) => t.clientId === clientId)
    const remaining = tabs.filter((t) => t.clientId !== clientId)

    if (remaining.length === 0) {
      const fresh = makeUploadTab()
      setTabs([fresh])
      setActiveTabId(fresh.clientId)
      return
    }

    setStatusInfo(null)
    setTabs(remaining)
    if (activeTabId === clientId) {
      const fallback = remaining[closedIndex] || remaining[closedIndex - 1] || remaining[0]
      setActiveTabId(fallback.clientId)
    }
  }

  const handleUploaded = (clientId, data) => {
    if (data.already_parsed) {
      updateTab(clientId, {
        sessionId: data.session_id,
        filename: data.filename,
        step: 'dashboard',
        uploadData: data,
        parseResult: { session_id: data.session_id, separator: null, n_rows: null, n_columns: null },
      })
    } else {
      updateTab(clientId, {
        sessionId: data.session_id,
        filename: data.filename,
        step: 'separator',
        uploadData: data,
      })
    }
  }

  const handleParsed = (clientId, result) => {
    updateTab(clientId, { step: 'dashboard', parseResult: result })
  }

  const handleResetTab = (clientId) => {
    const tab = tabs.find((t) => t.clientId === clientId)
    if (tab?.sessionId) {
      deleteSession(tab.sessionId).catch(() => {})
    }
    updateTab(clientId, {
      sessionId: null,
      filename: null,
      step: 'upload',
      uploadData: null,
      parseResult: null,
    })
  }

  const mergeableTabs = tabs
    .filter((t) => t.step === 'dashboard' && t.sessionId)
    .map((t) => ({ sessionId: t.sessionId, filename: t.filename }))

  const handleMergeCreated = (result) => {
    if (activeTab) {
      updateTab(activeTab.clientId, {
        sessionId: result.sessionId,
        filename: result.filename,
        step: 'dashboard',
        uploadData: null,
        parseResult: result.parseResult,
      })
    }
    setIsMergeDialogOpen(false)
  }

  if (isRestoring) {
    return <p className="p-8 text-sm text-slate-500 dark:text-slate-400">Chargement…</p>
  }

  return (
    <div className="flex min-w-0 flex-col">
      <div className="flex items-center gap-1 overflow-x-auto border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900">
        {tabs.map((tab, i) => (
          <div
            key={tab.clientId}
            onClick={() => setActiveTabId(tab.clientId)}
            className={`group flex shrink-0 cursor-pointer items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab.clientId === activeTabId
                ? 'border-blue-600 text-blue-700 dark:border-blue-400 dark:text-blue-300'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
            }`}
          >
            <span className="max-w-[10rem] truncate">{tab.filename || `Fichier ${i + 1}`}</span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                closeTab(tab.clientId)
              }}
              className="rounded p-0.5 text-slate-400 opacity-0 hover:bg-slate-200 hover:text-slate-700 group-hover:opacity-100 dark:hover:bg-slate-700 dark:hover:text-slate-200"
              aria-label={`Fermer l'onglet ${tab.filename || `Fichier ${i + 1}`}`}
            >
              ✕
            </button>
          </div>
        ))}
        <button
          onClick={addTab}
          className="ml-1 shrink-0 rounded-md px-3 py-1.5 text-lg font-medium leading-none text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          aria-label="Nouvel onglet"
          title="Nouvel onglet"
        >
          +
        </button>
      </div>

      {activeTab && (
        <TabWorkspace
          tab={activeTab}
          onUploaded={(data) => handleUploaded(activeTab.clientId, data)}
          onParsed={(result) => handleParsed(activeTab.clientId, result)}
          onReset={() => handleResetTab(activeTab.clientId)}
          mergeableTabs={mergeableTabs}
          onOpenMergeDialog={() => setIsMergeDialogOpen(true)}
          onInfoChange={setStatusInfo}
        />
      )}

      {isMergeDialogOpen && (
        <MergeDialog
          tabs={mergeableTabs}
          onClose={() => setIsMergeDialogOpen(false)}
          onCreated={handleMergeCreated}
        />
      )}

      <StatusBar
        info={activeTab?.step === 'dashboard' ? statusInfo : null}
        openTabs={tabs.length}
        onShowShortcuts={() => setIsHelpOpen(true)}
      />
      <ShortcutsHelp open={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </div>
  )
}
