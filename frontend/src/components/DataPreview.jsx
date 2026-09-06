import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getRows } from '../api/client'
import ColumnMenu from './table/ColumnMenu'
import ColumnStatsPopover from './table/ColumnStatsPopover'
import {
  BUTTON_CLASS,
  Badge,
  ErrorBox,
  INPUT_CLASS,
  InfoTip,
  Loading,
  Segmented,
  SliderField,
  Toggle,
} from './ui/common'
import {
  DENSITIES,
  PAGE_SIZES,
  TYPE_ICONS,
  TYPE_TITLES,
  densityConfig,
  formatCellValue,
  isOutlier,
} from './table/tableHelpers'

const DEFAULT_COLUMN_WIDTH = 150
const OVERSCAN_ROWS = 12
const VIRTUALIZATION_THRESHOLD = 120
const ROW_NUMBER_WIDTH = 52
const SHOW_ROW_NUMBERS_KEY = 'datavortex_show_row_numbers'

/**
 * Tableau de données (refonte Phase 8).
 *
 * Le tri, la recherche, le regroupement et la pagination sont délégués au
 * backend : seule la page visible transite, ce qui rend l'affichage
 * indépendant de la taille du fichier. Au-delà de quelques centaines de lignes
 * par page, le rendu est en plus virtualisé (seules les lignes visibles
 * existent dans le DOM).
 */
export default function DataPreview({ sessionId, refreshKey, onRequestFilter }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const [offset, setOffset] = useState(0)
  const [pageSize, setPageSize] = useState(100)
  const [sortBy, setSortBy] = useState(null)
  const [sortDir, setSortDir] = useState('asc')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [groupBy, setGroupBy] = useState('')

  const [density, setDensity] = useState('normal')
  const [fontSize, setFontSize] = useState(13)
  const [frozenCount, setFrozenCount] = useState(1)
  const [hiddenColumns, setHiddenColumns] = useState([])
  const [showOptions, setShowOptions] = useState(false)
  const [highlightOutliers, setHighlightOutliers] = useState(true)
  const [showRowNumbers, setShowRowNumbers] = useState(() => {
    try {
      const saved = localStorage.getItem(SHOW_ROW_NUMBERS_KEY)
      return saved === null ? true : saved === 'true'
    } catch {
      return true
    }
  })
  const [columnWidths, setColumnWidths] = useState({})
  const [collapsedGroups, setCollapsedGroups] = useState([])

  const [menu, setMenu] = useState(null)
  const [statsColumn, setStatsColumn] = useState(null)
  const [gotoRow, setGotoRow] = useState('')

  const scrollRef = useRef(null)
  const searchRef = useRef(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [viewportHeight, setViewportHeight] = useState(420)
  const resizing = useRef(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    getRows(sessionId, { offset, limit: pageSize, sortBy, sortDir, search, groupBy })
      .then(({ data: payload }) => setData(payload))
      .catch((err) =>
        setError(err?.response?.data?.error?.message || "Impossible de charger l'aperçu des données."),
      )
      .finally(() => setLoading(false))
  }, [sessionId, offset, pageSize, sortBy, sortDir, search, groupBy])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  // Un filtre appliqué ailleurs peut réduire le jeu : on revient au début.
  useEffect(() => {
    setOffset(0)
  }, [refreshKey, sessionId, search, groupBy, pageSize])

  // Recherche débouncée : on n'interroge pas le serveur à chaque frappe.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 350)
    return () => clearTimeout(timer)
  }, [searchInput])

  // Ctrl+F cible la recherche du tableau plutôt que celle du navigateur.
  useEffect(() => {
    const onKey = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
        event.preventDefault()
        searchRef.current?.focus()
        searchRef.current?.select()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // Redimensionnement d'une colonne par glissement du séparateur d'en-tête.
  useEffect(() => {
    const onMove = (event) => {
      if (!resizing.current) return
      const { column, startX, startWidth } = resizing.current
      const width = Math.max(60, startWidth + (event.clientX - startX))
      setColumnWidths((prev) => ({ ...prev, [column]: width }))
    }
    const onUp = () => {
      resizing.current = null
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [])

  useEffect(() => {
    const element = scrollRef.current
    if (!element) return undefined
    const update = () => setViewportHeight(element.clientHeight)
    update()
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [data])

  const visibleColumns = useMemo(
    () => (data?.columns || []).filter((c) => !hiddenColumns.includes(c)),
    [data, hiddenColumns],
  )

  const widthOf = (column) => columnWidths[column] || DEFAULT_COLUMN_WIDTH

  useEffect(() => {
    try {
      localStorage.setItem(SHOW_ROW_NUMBERS_KEY, String(showRowNumbers))
    } catch {
      // stockage indisponible (mode privé...) : on ignore silencieusement
    }
  }, [showRowNumbers])

  const frozenOffsets = useMemo(() => {
    const offsets = {}
    let running = showRowNumbers ? ROW_NUMBER_WIDTH : 0
    for (let i = 0; i < Math.min(frozenCount, visibleColumns.length); i += 1) {
      offsets[visibleColumns[i]] = running
      running += widthOf(visibleColumns[i])
    }
    return offsets
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleColumns, frozenCount, columnWidths, showRowNumbers])

  const { rowHeight, padding } = densityConfig(density)

  // Lignes réellement affichées : les groupes repliés sont retirés.
  const displayRows = useMemo(() => {
    if (!data) return []
    const rows = data.rows.map((row, i) => ({ row, index: i, key: data.row_indices[i] }))
    if (!groupBy || collapsedGroups.length === 0) return rows
    return rows.filter((item) => !collapsedGroups.includes(String(item.row[groupBy])))
  }, [data, groupBy, collapsedGroups])

  const virtualized = displayRows.length > VIRTUALIZATION_THRESHOLD
  const startIndex = virtualized ? Math.max(0, Math.floor(scrollTop / rowHeight) - OVERSCAN_ROWS) : 0
  const endIndex = virtualized
    ? Math.min(displayRows.length, Math.ceil((scrollTop + viewportHeight) / rowHeight) + OVERSCAN_ROWS)
    : displayRows.length
  const renderedRows = displayRows.slice(startIndex, endIndex)

  const handleSort = (column, direction) => {
    if (direction) {
      setSortBy(column)
      setSortDir(direction)
    } else if (sortBy === column) {
      // Cycle : croissant → décroissant → tri annulé.
      if (sortDir === 'asc') setSortDir('desc')
      else setSortBy(null)
    } else {
      setSortBy(column)
      setSortDir('asc')
    }
    setOffset(0)
  }

  const jumpToRow = () => {
    const target = Number(gotoRow)
    if (!Number.isFinite(target) || target < 1) return
    const page = Math.floor((target - 1) / pageSize) * pageSize
    setOffset(Math.min(page, Math.max(0, (data?.matched_rows || 1) - 1)))
    // Positionne aussi le défilement sur la ligne dans la page chargée.
    const within = (target - 1) % pageSize
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: within * rowHeight }))
  }

  if (loading && !data) return <Loading>Chargement de l&apos;aperçu…</Loading>
  if (error) return <ErrorBox>{error}</ErrorBox>
  if (!data) return null

  const total = data.matched_rows
  const from = total === 0 ? 0 : data.offset + 1
  const to = data.offset + data.shown_rows
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.floor(data.offset / pageSize) + 1

  let previousGroup = null

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-slate-800 dark:text-slate-50">
          Aperçu des données
          {data.filtered && (
            <Badge tone="blue">
              filtré : {data.total_rows}/{data.total_rows_unfiltered}
            </Badge>
          )}
          {search && <Badge tone="amber">{total} résultat(s) pour « {search} »</Badge>}
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={searchRef}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Rechercher dans le tableau (Ctrl+F)"
            className={`${INPUT_CLASS} w-64`}
          />
          <button onClick={() => setShowOptions((v) => !v)} className={BUTTON_CLASS}>
            Affichage
          </button>
        </div>
      </div>

      {showOptions && (
        <div className="flex flex-wrap items-end gap-x-6 gap-y-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600 dark:text-slate-300">Densité</span>
            <Segmented options={DENSITIES} value={density} onChange={setDensity} size="sm" />
          </label>
          <SliderField
            label="Taille du texte"
            value={fontSize}
            onChange={setFontSize}
            min={10}
            max={20}
            format={(v) => `${v} px`}
          />
          <SliderField
            label="Colonnes figées"
            value={frozenCount}
            onChange={setFrozenCount}
            min={0}
            max={Math.min(4, visibleColumns.length)}
            hint="Les premières colonnes restent visibles pendant le défilement horizontal."
          />
          <label className="flex flex-col gap-1 text-sm">
            <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
              Regrouper par
              <InfoTip text="Trie sur la colonne pour rendre les groupes contigus, avec un en-tête repliable par groupe." />
            </span>
            <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)} className={INPUT_CLASS}>
              <option value="">— aucun —</option>
              {data.columns.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <Toggle
            label="Signaler les valeurs atypiques"
            checked={highlightOutliers}
            onChange={setHighlightOutliers}
            hint="Colore en orange les valeurs hors des bornes de Tukey (Q1 − 1,5·IQR ; Q3 + 1,5·IQR)."
          />
          <Toggle
            label="Numéros de ligne"
            checked={showRowNumbers}
            onChange={setShowRowNumbers}
            hint="Affiche l'indice d'origine de chaque ligne (conservé même après un filtre)."
          />
          {hiddenColumns.length > 0 && (
            <button onClick={() => setHiddenColumns([])} className={BUTTON_CLASS}>
              Réafficher {hiddenColumns.length} colonne(s)
            </button>
          )}
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
        className="relative max-h-[460px] overflow-auto rounded-lg border border-slate-200 dark:border-slate-800"
        style={{ fontSize: `${fontSize}px` }}
      >
        <table className="min-w-full border-separate border-spacing-0">
          <thead className="sticky top-0 z-20">
            <tr>
              {showRowNumbers && (
                <th
                  style={{ width: ROW_NUMBER_WIDTH, minWidth: ROW_NUMBER_WIDTH, position: 'sticky', left: 0, zIndex: 35 }}
                  className="border-b border-slate-200 bg-slate-200 text-center text-[11px] font-semibold text-slate-500 shadow-[2px_0_0_0_rgba(148,163,184,0.35)] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
                  title="Indice d'origine de la ligne dans le jeu de données"
                >
                  #
                </th>
              )}
              {visibleColumns.map((col, colIndex) => {
                const frozen = colIndex < frozenCount
                return (
                  <th
                    key={col}
                    onClick={() => handleSort(col)}
                    onContextMenu={(e) => {
                      e.preventDefault()
                      setMenu({ column: col, x: e.clientX, y: e.clientY })
                    }}
                    style={{
                      width: widthOf(col),
                      minWidth: widthOf(col),
                      ...(frozen ? { position: 'sticky', left: frozenOffsets[col], zIndex: 30 } : {}),
                    }}
                    className={`group cursor-pointer select-none whitespace-nowrap border-b border-slate-200 bg-slate-100 ${padding} text-left font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 ${
                      frozen ? 'shadow-[2px_0_0_0_rgba(148,163,184,0.35)]' : ''
                    }`}
                    title="Clic : trier · Clic droit : plus d'actions"
                  >
                    <span className="flex items-center gap-1.5">
                      <span
                        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded bg-slate-300 text-[10px] font-bold text-slate-600 dark:bg-slate-600 dark:text-slate-200"
                        title={TYPE_TITLES[data.column_types[col]] || data.column_types[col]}
                      >
                        {TYPE_ICONS[data.column_types[col]] || '?'}
                      </span>
                      <span className="truncate">{col}</span>
                      {sortBy === col && <span className="text-blue-600 dark:text-blue-400">{sortDir === 'asc' ? '▲' : '▼'}</span>}
                      <span
                        onMouseDown={(e) => {
                          e.stopPropagation()
                          resizing.current = { column: col, startX: e.clientX, startWidth: widthOf(col) }
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="ml-auto h-4 w-1.5 shrink-0 cursor-col-resize rounded bg-slate-300 opacity-0 group-hover:opacity-100 dark:bg-slate-500"
                        title="Glisser pour redimensionner"
                      />
                    </span>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {virtualized && startIndex > 0 && (
              <tr style={{ height: startIndex * rowHeight }}>
                <td colSpan={visibleColumns.length + (showRowNumbers ? 1 : 0)} />
              </tr>
            )}
            {renderedRows.map(({ row, key }) => {
              const groupValue = groupBy ? String(row[groupBy]) : null
              const startsGroup = groupBy && groupValue !== previousGroup
              previousGroup = groupValue
              const groupInfo = startsGroup ? data.groups?.find((g) => g.value === groupValue) : null

              return (
                <Fragment key={key}>
                  {startsGroup && (
                    <tr className="bg-blue-50 dark:bg-blue-950/30">
                      <td colSpan={visibleColumns.length + (showRowNumbers ? 1 : 0)} className={`${padding} font-medium`}>
                        <button
                          onClick={() =>
                            setCollapsedGroups((prev) =>
                              prev.includes(groupValue)
                                ? prev.filter((g) => g !== groupValue)
                                : [...prev, groupValue],
                            )
                          }
                          className="flex items-center gap-1.5 text-blue-700 dark:text-blue-300"
                        >
                          <span className="text-[10px]">{collapsedGroups.includes(groupValue) ? '▶' : '▼'}</span>
                          {groupBy} = {groupValue}
                          {groupInfo && (
                            <span className="text-xs font-normal opacity-70">({groupInfo.count} lignes)</span>
                          )}
                        </button>
                      </td>
                    </tr>
                  )}
                  <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/60">
                    {showRowNumbers && (
                      <td
                        style={{
                          width: ROW_NUMBER_WIDTH,
                          minWidth: ROW_NUMBER_WIDTH,
                          height: rowHeight,
                          position: 'sticky',
                          left: 0,
                          zIndex: 15,
                        }}
                        className={`border-b border-slate-100 bg-slate-50 text-center text-[12px] tabular-nums text-slate-400 shadow-[2px_0_0_0_rgba(148,163,184,0.25)] dark:border-slate-800 dark:bg-slate-800/70 dark:text-slate-500`}
                        title="Indice d'origine (avant tout filtre)"
                      >
                        {typeof key === 'number' ? key + 1 : key}
                      </td>
                    )}
                    {visibleColumns.map((col, colIndex) => {
                      const value = row[col]
                      const missing = value === null || value === undefined
                      const outlier = highlightOutliers && isOutlier(value, data.outlier_bounds[col])
                      const frozen = colIndex < frozenCount
                      return (
                        <td
                          key={col}
                          onContextMenu={(e) => {
                            e.preventDefault()
                            setMenu({ column: col, x: e.clientX, y: e.clientY })
                          }}
                          style={{
                            width: widthOf(col),
                            minWidth: widthOf(col),
                            height: rowHeight,
                            ...(frozen ? { position: 'sticky', left: frozenOffsets[col], zIndex: 10 } : {}),
                          }}
                          className={`overflow-hidden text-ellipsis whitespace-nowrap border-b border-slate-100 ${padding} dark:border-slate-800 ${
                            missing
                              ? 'bg-slate-100 italic text-slate-400 dark:bg-slate-800/50 dark:text-slate-500'
                              : outlier
                                ? 'bg-orange-50 font-medium text-orange-700 dark:bg-orange-950/30 dark:text-orange-300'
                                : 'bg-white text-slate-700 dark:bg-slate-900 dark:text-slate-200'
                          } ${frozen ? 'shadow-[2px_0_0_0_rgba(148,163,184,0.25)]' : ''}`}
                          title={outlier ? 'Valeur atypique au sens de la règle de Tukey' : undefined}
                        >
                          {missing ? 'null' : formatCellValue(value)}
                        </td>
                      )
                    })}
                  </tr>
                </Fragment>
              )
            })}
            {virtualized && endIndex < displayRows.length && (
              <tr style={{ height: (displayRows.length - endIndex) * rowHeight }}>
                <td colSpan={visibleColumns.length + (showRowNumbers ? 1 : 0)} />
              </tr>
            )}
            {displayRows.length === 0 && (
              <tr>
                <td colSpan={visibleColumns.length + (showRowNumbers ? 1 : 0)} className="p-8 text-center text-slate-400 dark:text-slate-500">
                  Aucune ligne ne correspond à la recherche.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pied de pagination */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-600 dark:text-slate-300">
        <span className="tabular-nums">
          Lignes {from}–{to} sur {total}
          {data.filtered && ` (${data.total_rows_unfiltered} avant filtrage)`}
        </span>
        {virtualized && <Badge tone="green">rendu virtualisé</Badge>}

        <span className="flex items-center gap-1">
          <button onClick={() => setOffset(0)} disabled={data.offset === 0} className={BUTTON_CLASS}>
            ⏮
          </button>
          <button
            onClick={() => setOffset(Math.max(0, data.offset - pageSize))}
            disabled={data.offset === 0}
            className={BUTTON_CLASS}
          >
            ◀
          </button>
          <span className="px-1 tabular-nums">
            page {currentPage} / {pageCount}
          </span>
          <button
            onClick={() => setOffset(data.offset + pageSize)}
            disabled={to >= total}
            className={BUTTON_CLASS}
          >
            ▶
          </button>
          <button
            onClick={() => setOffset((pageCount - 1) * pageSize)}
            disabled={to >= total}
            className={BUTTON_CLASS}
          >
            ⏭
          </button>
        </span>

        <label className="flex items-center gap-1.5">
          <span>Lignes / page</span>
          <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} className={INPUT_CLASS}>
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-1.5">
          <span>Aller à la ligne</span>
          <input
            type="number"
            min={1}
            max={total}
            value={gotoRow}
            onChange={(e) => setGotoRow(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && jumpToRow()}
            className={`${INPUT_CLASS} w-24`}
          />
          <button onClick={jumpToRow} disabled={!gotoRow} className={BUTTON_CLASS}>
            Aller
          </button>
        </label>

        <span className="ml-auto text-xs text-slate-400 dark:text-slate-500">
          {(data.memory_usage_bytes / 1024 / 1024).toFixed(2)} Mo en mémoire
        </span>
      </div>

      {menu && (
        <ColumnMenu
          column={menu.column}
          position={{ x: menu.x, y: menu.y }}
          onClose={() => setMenu(null)}
          onSort={(direction) => handleSort(menu.column, direction)}
          onHide={() => setHiddenColumns((prev) => [...prev, menu.column])}
          onFilter={() => onRequestFilter?.(menu.column)}
          onStats={() => setStatsColumn(menu.column)}
          onCopy={() => navigator.clipboard?.writeText(menu.column).catch(() => {})}
        />
      )}
      {statsColumn && (
        <ColumnStatsPopover sessionId={sessionId} column={statsColumn} onClose={() => setStatsColumn(null)} />
      )}
    </div>
  )
}
