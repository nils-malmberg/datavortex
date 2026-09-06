import { useEffect, useState } from 'react'
import { exportStatsTable, getAdvancedStats, getStats } from '../api/client'
import { extractFilename } from '../api/download'
import useSaveFile from '../hooks/useSaveFile'
import StatsSummaryTab from './stats/StatsSummaryTab'
import StatsCorrelationsTab from './stats/StatsCorrelationsTab'
import StatsDistributionsTab from './stats/StatsDistributionsTab'
import StatsMissingTab from './stats/StatsMissingTab'
import {
  BUTTON_CLASS,
  Badge,
  ErrorBox,
  Loading,
  Segmented,
  SliderField,
  Toggle,
} from './ui/common'

/**
 * Panneau de statistiques (refonte Phase 8).
 *
 * Quatre analyses complémentaires (résumé, corrélations, distributions,
 * valeurs manquantes) partagent une barre d'outils commune : mode avancé,
 * précision d'affichage, filtre de colonnes et export tabulaire.
 */
const TABS = [
  { value: 'summary', label: 'Résumé' },
  { value: 'correlations', label: 'Corrélations' },
  { value: 'distributions', label: 'Distributions' },
  { value: 'missing', label: 'Valeurs manquantes' },
]

const COLUMN_FILTERS = [
  { value: 'all', label: 'Toutes' },
  { value: 'numeric', label: 'Numériques' },
  { value: 'categorical', label: 'Catégorielles' },
]

const EXPORT_FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'excel', label: 'Excel' },
  { value: 'latex', label: 'LaTeX' },
]

export default function StatsPanel({ sessionId, refreshKey }) {
  const saveFile = useSaveFile()
  const [tab, setTab] = useState('summary')
  const [advanced, setAdvanced] = useState(false)
  const [precision, setPrecision] = useState(3)
  const [columnFilter, setColumnFilter] = useState('all')
  const [correlationMethod, setCorrelationMethod] = useState('pearson')

  const [basicStats, setBasicStats] = useState(null)
  const [advancedStats, setAdvancedStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [isExporting, setIsExporting] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([getStats(sessionId), getAdvancedStats(sessionId, correlationMethod)])
      .then(([basic, adv]) => {
        if (cancelled) return
        setBasicStats(basic.data)
        setAdvancedStats(adv.data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.error?.message || 'Impossible de charger les statistiques.')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId, refreshKey, correlationMethod])

  const handleExport = async (format) => {
    setExportError(null)
    setIsExporting(true)
    try {
      const response = await exportStatsTable(sessionId, { table: tab, format, precision })
      const filename = extractFilename(response.headers['content-disposition'], `stats_${tab}.${format}`)
      await saveFile(response.data, filename)
    } catch (err) {
      // La réponse d'erreur arrive en blob (responseType), il faut la relire.
      let message = "Échec de l'export."
      try {
        const parsed = JSON.parse(await err.response.data.text())
        message = parsed?.error?.message || message
      } catch {
        message = err?.message || message
      }
      setExportError(message)
    } finally {
      setIsExporting(false)
    }
  }

  if (loading) return <Loading>Calcul des statistiques avancées…</Loading>
  if (error) return <ErrorBox>{error}</ErrorBox>
  if (!advancedStats || !basicStats) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Segmented options={TABS} value={tab} onChange={setTab} ariaLabel="Type d'analyse statistique" />
          {advancedStats.filtered && <Badge tone="blue">données filtrées</Badge>}
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {advancedStats.n_rows} lignes × {advancedStats.n_columns} colonnes
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-900/60">
        <Toggle
          label="Mode avancé"
          checked={advanced}
          onChange={setAdvanced}
          hint="Affiche les indicateurs destinés aux experts : erreur standard, CV, MAD, intervalles de confiance, bornes d'outliers."
        />
        <SliderField
          label="Précision"
          value={precision}
          onChange={setPrecision}
          min={1}
          max={6}
          format={(v) => `${v} déc.`}
          hint="Nombre de décimales affichées et utilisées lors de l'export."
        />
        {tab === 'summary' && (
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-600 dark:text-slate-300">Colonnes</span>
            <Segmented options={COLUMN_FILTERS} value={columnFilter} onChange={setColumnFilter} size="sm" />
          </label>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Exporter :</span>
          {EXPORT_FORMATS.map((fmt) => (
            <button
              key={fmt.value}
              onClick={() => handleExport(fmt.value)}
              disabled={isExporting}
              className={BUTTON_CLASS}
            >
              {fmt.label}
            </button>
          ))}
        </div>
      </div>

      {exportError && <ErrorBox>{exportError}</ErrorBox>}

      {tab === 'summary' && (
        <StatsSummaryTab
          advancedStats={advancedStats}
          basicStats={basicStats}
          columnFilter={columnFilter}
          advanced={advanced}
          precision={precision}
        />
      )}
      {tab === 'correlations' && (
        <StatsCorrelationsTab
          correlations={advancedStats.correlations}
          precision={precision}
          method={correlationMethod}
          onChangeMethod={setCorrelationMethod}
        />
      )}
      {tab === 'distributions' && (
        <StatsDistributionsTab distributions={advancedStats.distributions} precision={precision} />
      )}
      {tab === 'missing' && <StatsMissingTab missing={advancedStats.missing} precision={precision} />}
    </div>
  )
}
