import { useEffect, useMemo, useRef, useState } from 'react'
import { applyAdvancedFilter, getPreview } from '../api/client'
import FilterNodeView from './filter/FilterNode'
import useToast from './ui/ToastProvider'
import {
  BUTTON_CLASS,
  Badge,
  ErrorBox,
  INPUT_CLASS,
  Loading,
  PRIMARY_BUTTON_CLASS,
  Panel,
  Segmented,
  Toggle,
} from './ui/common'
import {
  buildFilterPayload,
  countConditions,
  describeFilter,
  newCondition,
  newGroup,
  reassignIds,
} from './filter/filterCatalog'

const PRESET_KEY = 'datavortex_filter_presets'
const HISTORY_LIMIT = 10

const PREVIEW_MODES = [
  { value: 'all', label: 'Tout', hint: 'Aperçu du jeu complet, lignes retenues et écartées distinguées.' },
  { value: 'kept', label: 'Retenues' },
  { value: 'removed', label: 'Écartées' },
]

function readPresets() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PRESET_KEY) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writePresets(presets) {
  try {
    window.localStorage.setItem(PRESET_KEY, JSON.stringify(presets))
  } catch {
    // Stockage indisponible : les presets ne survivront pas au rechargement.
  }
}

function formatCell(value) {
  if (value === null || value === undefined) {
    return <span className="italic text-slate-400 dark:text-slate-500">null</span>
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

/**
 * Constructeur de filtres (refonte Phase 8).
 *
 * Les conditions forment un arbre : chaque sous-groupe se comporte comme une
 * parenthèse. Le panneau d'indicateurs montre en continu ce que le filtre
 * conserve, et l'aperçu marque les lignes écartées avant de valider.
 */
export default function FilterBuilder({ sessionId, onFilterApplied }) {
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})
  const [root, setRoot] = useState(null)
  const [invert, setInvert] = useState(false)
  const [previewMode, setPreviewMode] = useState('all')

  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const toast = useToast()

  const [presets, setPresets] = useState(readPresets)
  const [presetName, setPresetName] = useState('')
  const [history, setHistory] = useState([])
  const [showPanel, setShowPanel] = useState(false)
  const hasRestored = useRef(false)

  const storageKey = `datavortex_filter_${sessionId}`

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      if (hasRestored.current) return
      hasRestored.current = true
      try {
        const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null')
        if (saved?.root) {
          setRoot(reassignIds(saved.root))
          setInvert(Boolean(saved.invert))
        }
      } catch {
        // Filtre sauvegardé illisible : on repart d'une sélection vide.
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const payload = useMemo(() => buildFilterPayload(root, columnTypes), [root, columnTypes])
  const payloadKey = JSON.stringify(payload)

  useEffect(() => {
    if (columns.length === 0) return undefined
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({ root, invert }))
    } catch {
      // Sans stockage, le filtre est simplement perdu au changement d'onglet.
    }

    setIsLoading(true)
    setError(null)
    const timer = setTimeout(async () => {
      try {
        const { data } = await applyAdvancedFilter(sessionId, { filter: payload, invert, previewMode })
        setResult(data)
        onFilterApplied?.()
        if (payload) {
          setHistory((prev) => {
            const label = describeFilter(payload)
            const withoutDuplicate = prev.filter((h) => h.label !== label)
            return [{ label, filter: payload, invert, at: Date.now() }, ...withoutDuplicate].slice(0, HISTORY_LIMIT)
          })
        }
      } catch (err) {
        setError(err?.response?.data?.error?.message || "Impossible d'appliquer ce filtre.")
      } finally {
        setIsLoading(false)
      }
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payloadKey, invert, previewMode, sessionId, columns.length])

  // Indexé par l'id de la condition, pas par sa position : une condition
  // incomplète est absente de la requête et décalerait tous les chemins.
  const insights = useMemo(() => {
    const map = {}
    for (const item of result?.per_condition || []) {
      if (item.id) map[item.id] = item
    }
    return map
  }, [result])

  const addCondition = () => {
    if (columns.length === 0) return
    setRoot((prev) =>
      prev
        ? { ...prev, conditions: [...prev.conditions, newCondition(columns[0])] }
        : newGroup(columns[0]),
    )
  }

  const addGroup = () => {
    if (columns.length === 0) return
    setRoot((prev) => {
      const base = prev || { ...newGroup(columns[0]), conditions: [] }
      return { ...base, conditions: [...base.conditions, newGroup(columns[0])] }
    })
  }

  const resetAll = () => {
    setRoot(null)
    setInvert(false)
  }

  const savePreset = () => {
    if (!presetName.trim() || !payload) return
    const next = [...presets, { id: crypto.randomUUID(), name: presetName.trim(), root, invert }]
    setPresets(next)
    writePresets(next)
    setPresetName('')
    toast.success(`Filtre « ${presetName.trim()} » enregistré.`)
  }

  const loadPreset = (preset) => {
    const missing = []
    const check = (node) => {
      if (!node) return
      if (node.type === 'condition') {
        if (!columns.includes(node.column)) missing.push(node.column)
      } else {
        node.conditions?.forEach(check)
      }
    }
    check(preset.root)
    setRoot(reassignIds(preset.root))
    setInvert(Boolean(preset.invert))
    if (missing.length > 0) {
      toast.warning(`Filtre chargé, mais ces colonnes sont absentes : ${[...new Set(missing)].join(', ')}.`)
    } else {
      toast.success(`Filtre « ${preset.name} » chargé.`)
    }
  }

  const deletePreset = (id) => {
    const next = presets.filter((p) => p.id !== id)
    setPresets(next)
    writePresets(next)
  }

  if (columns.length === 0) return <Loading>Chargement des colonnes…</Loading>

  const conditionCount = countConditions(root)

  return (
    <div className="flex flex-col gap-4">
      {/* Indicateurs */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
        {result ? (
          <>
            <div className="flex min-w-[14rem] flex-1 flex-col gap-1">
              <div className="flex items-baseline justify-between text-sm">
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  {result.total_rows} / {result.total_rows_unfiltered} lignes conservées
                </span>
                <span className="tabular-nums text-slate-500 dark:text-slate-400">{result.kept_pct} %</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                <div
                  className={`h-full rounded-full transition-all ${
                    result.kept_pct > 50 ? 'bg-emerald-500' : result.kept_pct > 10 ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${result.kept_pct}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {result.removed_rows} ligne(s) écartée(s) · {result.n_columns_affected} colonne(s) concernée(s)
                {result.columns_affected.length > 0 && ` : ${result.columns_affected.join(', ')}`}
              </span>
            </div>
            <Toggle
              label="Mode exclusion"
              checked={invert}
              onChange={setInvert}
              hint="Inverse la sélection : conserve exactement les lignes que le filtre écarterait."
            />
            {invert && <Badge tone="amber">sélection inversée</Badge>}
            {isLoading && <span className="text-sm text-slate-400 dark:text-slate-500">Application…</span>}
          </>
        ) : (
          <span className="text-sm text-slate-500 dark:text-slate-400">Aucun filtre actif.</span>
        )}
      </div>

      {error && <ErrorBox>{error}</ErrorBox>}

      {/* Conditions */}
      {root ? (
        <FilterNodeView
          node={root}
          columns={columns}
          columnTypes={columnTypes}
          insights={insights}
          onChange={setRoot}
          onRemove={resetAll}
        />
      ) : (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
          Aucune condition. Ajoutez-en une pour commencer à filtrer.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button onClick={addCondition} className={BUTTON_CLASS}>
          + Condition
        </button>
        <button onClick={addGroup} className={BUTTON_CLASS}>
          + Sous-groupe ( … )
        </button>
        <button onClick={resetAll} disabled={!root} className={BUTTON_CLASS}>
          Tout réinitialiser
        </button>
        <button onClick={() => setInvert((v) => !v)} disabled={!payload} className={BUTTON_CLASS}>
          Inverser la sélection
        </button>
        <button onClick={() => setShowPanel((v) => !v)} className={showPanel ? PRIMARY_BUTTON_CLASS : BUTTON_CLASS}>
          Filtres enregistrés
        </button>
        {conditionCount > 0 && <Badge tone="blue">{conditionCount} condition(s)</Badge>}
      </div>

      {showPanel && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel className="flex flex-col gap-3">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Filtres enregistrés</h4>
            <div className="flex gap-2">
              <input
                className={`${INPUT_CLASS} flex-1`}
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && savePreset()}
                placeholder="Nom du filtre (ex. « setosa uniquement »)"
              />
              <button onClick={savePreset} disabled={!presetName.trim() || !payload} className={PRIMARY_BUTTON_CLASS}>
                Enregistrer
              </button>
            </div>
            {presets.length === 0 ? (
              <p className="text-sm text-slate-400 dark:text-slate-500">Aucun filtre enregistré.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {presets.map((preset) => (
                  <li
                    key={preset.id}
                    className="flex items-center gap-2 rounded-md border border-slate-200 px-2 py-1.5 dark:border-slate-700"
                  >
                    <span className="flex-1 truncate text-sm text-slate-700 dark:text-slate-200">{preset.name}</span>
                    <button onClick={() => loadPreset(preset)} className={BUTTON_CLASS}>
                      Charger
                    </button>
                    <button
                      onClick={() => deletePreset(preset.id)}
                      className="rounded px-1.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40"
                      aria-label={`Supprimer ${preset.name}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Historique récent ({history.length}/{HISTORY_LIMIT})
            </h4>
            {history.length === 0 ? (
              <p className="text-sm text-slate-400 dark:text-slate-500">
                Les filtres appliqués apparaîtront ici pour être rejoués.
              </p>
            ) : (
              <ul className="flex flex-col gap-1">
                {history.map((entry, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm">
                    <span className="flex-1 truncate text-slate-600 dark:text-slate-300" title={entry.label}>
                      {entry.label}
                    </span>
                    <button
                      onClick={() => loadPreset({ name: entry.label, root: entry.filter, invert: entry.invert })}
                      className={BUTTON_CLASS}
                    >
                      Rejouer
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      )}

      {/* Aperçu marqué */}
      {result && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Aperçu</h4>
            <Segmented options={PREVIEW_MODES} value={previewMode} onChange={setPreviewMode} size="sm" />
          </div>
          {previewMode === 'all' && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Les lignes grisées et barrées seraient écartées par le filtre courant.
            </p>
          )}
          <div className="max-h-80 overflow-auto rounded-lg border border-slate-200 dark:border-slate-800">
            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
              <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800">
                <tr>
                  {result.columns.map((col) => (
                    <th
                      key={col}
                      className={`whitespace-nowrap px-3 py-2 text-left font-semibold ${
                        result.columns_affected.includes(col)
                          ? 'text-blue-700 dark:text-blue-300'
                          : 'text-slate-700 dark:text-slate-200'
                      }`}
                      title={result.columns_affected.includes(col) ? 'Colonne utilisée par le filtre' : undefined}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
                {result.rows.map((row, i) => {
                  const matched = result.row_matches ? result.row_matches[i] : true
                  return (
                    <tr
                      key={i}
                      className={
                        matched
                          ? 'hover:bg-slate-50 dark:hover:bg-slate-800'
                          : 'bg-red-50/60 text-slate-400 line-through dark:bg-red-950/20 dark:text-slate-600'
                      }
                    >
                      {result.columns.map((col) => (
                        <td key={col} className="whitespace-nowrap px-3 py-1.5">
                          {formatCell(row[col])}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {result.shown_rows} ligne(s) affichée(s)
            {previewMode === 'all' && ` sur ${result.total_rows_unfiltered} au total`}
          </p>
        </div>
      )}
    </div>
  )
}
