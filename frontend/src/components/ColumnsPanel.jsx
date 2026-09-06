import { useCallback, useEffect, useMemo, useState } from 'react'
import { columnOperation, listColumns, transformColumn } from '../api/client'
import ColumnCreator from './ColumnCreator'
import ColumnTransformPanel from './columns/ColumnTransformPanel'
import {
  BUTTON_CLASS,
  Badge,
  ErrorBox,
  INPUT_CLASS,
  InfoTip,
  Loading,
  PRIMARY_BUTTON_CLASS,
  Panel,
  Segmented,
} from './ui/common'

const TABS = [
  { value: 'manage', label: 'Gérer les colonnes' },
  { value: 'transform', label: 'Transformer' },
  { value: 'formula', label: 'Colonne calculée' },
]

const TYPE_TONES = { integer: 'blue', float: 'blue', boolean: 'purple', datetime: 'amber', string: 'slate' }

const COLOR_TAGS = [
  { value: '', label: 'aucune', className: '' },
  { value: 'blue', label: 'bleu', className: 'bg-blue-500' },
  { value: 'green', label: 'vert', className: 'bg-emerald-500' },
  { value: 'amber', label: 'orange', className: 'bg-amber-500' },
  { value: 'red', label: 'rouge', className: 'bg-red-500' },
  { value: 'purple', label: 'violet', className: 'bg-purple-500' },
]

const TAG_STORAGE_KEY = 'datavortex_column_tags'

function readTags() {
  try {
    return JSON.parse(window.localStorage.getItem(TAG_STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

/**
 * Gestion des colonnes (refonte Phase 8).
 *
 * Trois volets : réorganiser et nettoyer la structure, dériver de nouvelles
 * colonnes par transformation, et créer une colonne par formule (déjà présent
 * depuis la Phase 3, conservé ici).
 */
export default function ColumnsPanel({ sessionId, onColumnsChanged }) {
  const [tab, setTab] = useState('manage')
  const [state, setState] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [selected, setSelected] = useState([])
  const [renaming, setRenaming] = useState(null)
  const [renameValue, setRenameValue] = useState('')
  const [dragIndex, setDragIndex] = useState(null)
  const [hidden, setHidden] = useState([])
  const [tags, setTags] = useState(readTags)
  const [filter, setFilter] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await listColumns(sessionId)
      setState(data)
      setError(null)
    } catch (err) {
      setError(err?.response?.data?.error?.message || 'Impossible de charger les colonnes.')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    refresh()
  }, [refresh])

  const flash = (message) => {
    setNotice(message)
    setTimeout(() => setNotice(null), 3000)
  }

  // Mémoïsé pour que le filtrage ci-dessous ne se recalcule pas à chaque rendu.
  const items = useMemo(() => state?.items || [], [state])
  const visibleItems = useMemo(
    () => items.filter((item) => item.name.toLowerCase().includes(filter.trim().toLowerCase())),
    [items, filter],
  )
  const columnNames = items.map((i) => i.name)
  const numericColumns = items.filter((i) => i.is_numeric).map((i) => i.name)

  const runOperation = async (payload, successMessage) => {
    try {
      const { data } = await columnOperation(sessionId, payload)
      setState((prev) => ({ ...prev, ...data }))
      await refresh()
      onColumnsChanged?.()
      setSelected([])
      flash(data.filter_dropped ? `${successMessage} Le filtre actif portait sur une colonne modifiée : il a été levé.` : successMessage)
    } catch (err) {
      setError(err?.response?.data?.error?.message || "L'opération a échoué.")
    }
  }

  const handleTransform = async (payload) => {
    const { data } = await transformColumn(sessionId, payload)
    await refresh()
    onColumnsChanged?.()
    return data
  }

  const toggleSelect = (name) =>
    setSelected((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]))

  const toggleHidden = (name) =>
    setHidden((prev) => (prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]))

  const setTag = (name, color) => {
    const next = { ...tags, [name]: color }
    if (!color) delete next[name]
    setTags(next)
    try {
      window.localStorage.setItem(TAG_STORAGE_KEY, JSON.stringify(next))
    } catch {
      // Les étiquettes de couleur sont un confort local : leur perte est sans effet.
    }
  }

  const moveColumn = (from, to) => {
    if (from === to || from == null || to == null) return
    const order = [...columnNames]
    const [moved] = order.splice(from, 1)
    order.splice(to, 0, moved)
    runOperation({ op: 'reorder', order }, `Colonne « ${moved} » déplacée.`)
  }

  if (loading && !state) return <Loading>Chargement des colonnes…</Loading>
  if (error && !state) return <ErrorBox>{error}</ErrorBox>
  if (!state) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented options={TABS} value={tab} onChange={setTab} ariaLabel="Section des colonnes" />
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {state.n_columns} colonne(s) · {state.n_rows} ligne(s)
        </p>
      </div>

      {error && <ErrorBox>{error}</ErrorBox>}
      {notice && (
        <p className="rounded-md bg-blue-50 px-3 py-2 text-sm text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
          {notice}
        </p>
      )}

      {tab === 'manage' && (
        <Panel className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filtrer par nom"
              className={`${INPUT_CLASS} w-56`}
            />
            <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
              <InfoTip text="Glissez la poignée ⠿ pour réordonner. L'ordre est appliqué au jeu de données lui-même." />
              Glisser-déposer pour réordonner
            </span>
            {selected.length > 0 && (
              <span className="ml-auto flex flex-wrap items-center gap-2">
                <Badge tone="blue">{selected.length} sélectionnée(s)</Badge>
                <button
                  onClick={() =>
                    runOperation({ op: 'delete', columns: selected }, `${selected.length} colonne(s) supprimée(s).`)
                  }
                  className="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 dark:border-red-800 dark:bg-slate-900 dark:hover:bg-red-950/40"
                >
                  Supprimer la sélection
                </button>
                <button onClick={() => setSelected([])} className={BUTTON_CLASS}>
                  Désélectionner
                </button>
              </span>
            )}
          </div>

          <ul className="flex flex-col gap-1">
            {visibleItems.map((item) => {
              const index = columnNames.indexOf(item.name)
              const isHidden = hidden.includes(item.name)
              const tag = tags[item.name]
              return (
                <li
                  key={item.name}
                  draggable
                  onDragStart={() => setDragIndex(index)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => {
                    moveColumn(dragIndex, index)
                    setDragIndex(null)
                  }}
                  onDragEnd={() => setDragIndex(null)}
                  className={`flex flex-wrap items-center gap-2 rounded-md border p-2 transition-colors ${
                    selected.includes(item.name)
                      ? 'border-blue-400 bg-blue-50 dark:border-blue-600 dark:bg-blue-950/30'
                      : 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900'
                  } ${isHidden ? 'opacity-50' : ''}`}
                >
                  <span className="cursor-grab select-none px-1 text-slate-400 active:cursor-grabbing" title="Glisser pour réordonner">
                    ⠿
                  </span>
                  <input
                    type="checkbox"
                    checked={selected.includes(item.name)}
                    onChange={() => toggleSelect(item.name)}
                    aria-label={`Sélectionner ${item.name}`}
                    className="accent-blue-600"
                  />
                  {tag && (
                    <span
                      className={`h-3 w-3 rounded-full ${COLOR_TAGS.find((c) => c.value === tag)?.className}`}
                      title={`Étiquette ${tag}`}
                    />
                  )}

                  {renaming === item.name ? (
                    <span className="flex items-center gap-1">
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            runOperation(
                              { op: 'rename', columns: [item.name], newName: renameValue },
                              `Colonne renommée en « ${renameValue} ».`,
                            )
                            setRenaming(null)
                          }
                          if (e.key === 'Escape') setRenaming(null)
                        }}
                        className={`${INPUT_CLASS} w-44`}
                      />
                      <button
                        onClick={() => {
                          runOperation(
                            { op: 'rename', columns: [item.name], newName: renameValue },
                            `Colonne renommée en « ${renameValue} ».`,
                          )
                          setRenaming(null)
                        }}
                        className={PRIMARY_BUTTON_CLASS}
                      >
                        OK
                      </button>
                      <button onClick={() => setRenaming(null)} className={BUTTON_CLASS}>
                        Annuler
                      </button>
                    </span>
                  ) : (
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium text-slate-800 dark:text-slate-100" title={item.name}>
                          {item.name}
                        </span>
                        <Badge tone={TYPE_TONES[item.type] || 'slate'}>{item.type}</Badge>
                        {item.missing > 0 && <Badge tone="amber">{item.missing_pct} % manquant</Badge>}
                        <Badge tone="slate">{item.unique} distinctes</Badge>
                      </span>
                      <span className="block truncate text-xs text-slate-400 dark:text-slate-500">
                        ex. {item.sample.join(' · ') || '—'}
                      </span>
                    </span>
                  )}

                  <span className="ml-auto flex flex-wrap items-center gap-1">
                    <select
                      value={tag || ''}
                      onChange={(e) => setTag(item.name, e.target.value)}
                      aria-label={`Étiquette de couleur pour ${item.name}`}
                      className="rounded-md border border-slate-300 bg-white px-1.5 py-1 text-xs dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
                    >
                      {COLOR_TAGS.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => {
                        setRenaming(item.name)
                        setRenameValue(item.name)
                      }}
                      className={BUTTON_CLASS}
                    >
                      Renommer
                    </button>
                    <button
                      onClick={() =>
                        runOperation({ op: 'duplicate', columns: [item.name] }, `Colonne « ${item.name} » dupliquée.`)
                      }
                      className={BUTTON_CLASS}
                    >
                      Dupliquer
                    </button>
                    <button onClick={() => toggleHidden(item.name)} className={BUTTON_CLASS}>
                      {isHidden ? 'Afficher' : 'Masquer'}
                    </button>
                    <button
                      onClick={() =>
                        runOperation({ op: 'delete', columns: [item.name] }, `Colonne « ${item.name} » supprimée.`)
                      }
                      className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-red-950/40"
                    >
                      Supprimer
                    </button>
                  </span>
                </li>
              )
            })}
          </ul>
          {hidden.length > 0 && (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {hidden.length} colonne(s) masquée(s) dans cette liste. Le masquage est un confort d&apos;affichage :
              les données restent intactes et disponibles dans les autres onglets.
            </p>
          )}
        </Panel>
      )}

      {tab === 'transform' && (
        <ColumnTransformPanel columns={columnNames} numericColumns={numericColumns} onApply={handleTransform} />
      )}

      {tab === 'formula' && (
        <ColumnCreator
          sessionId={sessionId}
          onColumnCreated={() => {
            refresh()
            onColumnsChanged?.()
          }}
        />
      )}
    </div>
  )
}
