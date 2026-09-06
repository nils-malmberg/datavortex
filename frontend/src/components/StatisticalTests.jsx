import { useEffect, useMemo, useState } from 'react'
import { getPreview, runStatisticalTest } from '../api/client'
import TestResult from './tests/TestResult'
import {
  ALTERNATIVES,
  DISTRIBUTIONS,
  FAMILIES,
  POST_HOC,
  TESTS,
  testConfig,
} from './tests/testCatalog'
import {
  Badge,
  ErrorBox,
  FieldSelect,
  InfoTip,
  Loading,
  NumberField,
  PRIMARY_BUTTON_CLASS,
  Panel,
  Segmented,
  SliderField,
  Toggle,
} from './ui/common'

const NUMERIC_TYPES = ['integer', 'float']
const MAX_LEVELS_LISTED = 50

/**
 * Tests statistiques : comparaison de groupes, ANOVA, corrélation et
 * ajustement de loi. Le formulaire s'adapte au test choisi et n'expose que
 * les champs qu'il utilise réellement.
 */
export default function StatisticalTests({ sessionId, refreshKey }) {
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})
  const [rows, setRows] = useState([])

  const [family, setFamily] = useState('hypothesis')
  const [test, setTest] = useState('ttest_ind')
  const [params, setParams] = useState({
    column: '',
    column_b: '',
    group_column: '',
    group_a: '',
    group_b: '',
    factor_a: '',
    factor_b: '',
    alternative: 'two-sided',
    popmean: 0,
    equal_variance: false,
    post_hoc: 'tukey',
    distribution: 'norm',
  })
  const [alpha, setAlpha] = useState(0.05)
  const [precision, setPrecision] = useState(4)

  const [result, setResult] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState(null)

  const numericColumns = useMemo(
    () => columns.filter((c) => NUMERIC_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )
  const categoricalColumns = useMemo(
    () => columns.filter((c) => !NUMERIC_TYPES.includes(columnTypes[c])),
    [columns, columnTypes],
  )

  // Modalités observées d'une colonne, estimées sur l'échantillon d'aperçu.
  const levelsOf = (column) => {
    if (!column) return []
    return [...new Set(rows.map((row) => String(row[column])).filter((v) => v !== 'null'))]
      .sort()
      .slice(0, MAX_LEVELS_LISTED)
  }

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
      setRows(data.rows)
      const numeric = data.columns.filter((c) => NUMERIC_TYPES.includes(data.column_types[c]))
      const categorical = data.columns.filter((c) => !NUMERIC_TYPES.includes(data.column_types[c]))
      const groupColumn = categorical[0] || ''
      // Deux modalités concrètes dès le départ : un facteur à 3 niveaux ou plus
      // rendrait le premier lancement impossible à résoudre automatiquement.
      const firstLevels = groupColumn
        ? [...new Set(data.rows.map((row) => String(row[groupColumn])).filter((v) => v !== 'null'))].sort()
        : []
      setParams((prev) => ({
        ...prev,
        column: numeric[0] || data.columns[0] || '',
        column_b: numeric[1] || numeric[0] || '',
        group_column: groupColumn,
        factor_a: groupColumn,
        factor_b: categorical[1] || '',
        group_a: firstLevels[0] || '',
        group_b: firstLevels[1] || '',
      }))
      setResult(null)
    })
  }, [sessionId, refreshKey])

  const config = testConfig(family, test)

  const handleFamilyChange = (nextFamily) => {
    setFamily(nextFamily)
    setTest(TESTS[nextFamily][0].value)
    setResult(null)
  }

  const set = (patch) => setParams((prev) => ({ ...prev, ...patch }))

  const groupLevels = levelsOf(params.group_column)

  const run = async () => {
    setIsRunning(true)
    setError(null)
    try {
      const payload = { family, test, alpha }
      for (const field of config.fields) payload[field] = params[field]
      // Sans sélection explicite, le backend choisit lui-même les deux modalités.
      if (!payload.group_a) delete payload.group_a
      if (!payload.group_b) delete payload.group_b
      const { data } = await runStatisticalTest(sessionId, payload)
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Impossible d'exécuter ce test.")
      setResult(null)
    } finally {
      setIsRunning(false)
    }
  }

  if (columns.length === 0) return <Loading>Chargement des colonnes…</Loading>

  const columnOptions = family === 'goodness_of_fit' && test === 'chi2' ? columns : numericColumns

  return (
    <div className="flex flex-col gap-4">
      <Segmented options={FAMILIES} value={family} onChange={handleFamilyChange} ariaLabel="Famille de test" />

      <Panel className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <FieldSelect
            label="Test"
            value={test}
            onChange={(v) => {
              setTest(v)
              setResult(null)
            }}
            options={TESTS[family]}
          />
          <p className="max-w-xl flex-1 text-xs text-slate-500 dark:text-slate-400">{config.hint}</p>
        </div>

        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          {config.fields.includes('column') && (
            <FieldSelect
              label={family === 'correlation' ? 'Première variable' : 'Colonne mesurée'}
              value={params.column}
              onChange={(v) => set({ column: v })}
              options={columnOptions}
            />
          )}
          {config.fields.includes('column_b') && (
            <FieldSelect
              label={family === 'correlation' ? 'Seconde variable' : 'Seconde colonne'}
              value={params.column_b}
              onChange={(v) => set({ column_b: v })}
              options={test === 'chi2' ? columns : numericColumns}
            />
          )}
          {config.fields.includes('group_column') && (
            <FieldSelect
              label="Colonne de groupes"
              value={params.group_column}
              onChange={(v) => {
                const levels = levelsOf(v)
                set({ group_column: v, group_a: levels[0] || '', group_b: levels[1] || '' })
              }}
              options={categoricalColumns.length ? categoricalColumns : columns}
            />
          )}
          {config.fields.includes('group_a') && groupLevels.length > 0 && (
            <>
              <FieldSelect
                label="Groupe A"
                value={params.group_a}
                onChange={(v) => set({ group_a: v })}
                options={groupLevels}
                allowEmpty
                emptyLabel="— automatique —"
              />
              <FieldSelect
                label="Groupe B"
                value={params.group_b}
                onChange={(v) => set({ group_b: v })}
                options={groupLevels}
                allowEmpty
                emptyLabel="— automatique —"
              />
            </>
          )}
          {config.fields.includes('factor_a') && (
            <FieldSelect
              label="Premier facteur"
              value={params.factor_a}
              onChange={(v) => set({ factor_a: v })}
              options={categoricalColumns.length ? categoricalColumns : columns}
            />
          )}
          {config.fields.includes('factor_b') && (
            <FieldSelect
              label="Second facteur"
              value={params.factor_b}
              onChange={(v) => set({ factor_b: v })}
              options={categoricalColumns.length ? categoricalColumns : columns}
            />
          )}
          {config.fields.includes('popmean') && (
            <NumberField
              label="Valeur de référence"
              value={params.popmean}
              onChange={(v) => set({ popmean: v })}
              step="any"
              hint="La moyenne théorique à laquelle comparer l'échantillon."
            />
          )}
          {config.fields.includes('alternative') && (
            <FieldSelect
              label="Hypothèse alternative"
              value={params.alternative}
              onChange={(v) => set({ alternative: v })}
              options={ALTERNATIVES}
              hint="Un test unilatéral est plus puissant, mais la direction doit être décidée avant de voir les données."
            />
          )}
          {config.fields.includes('post_hoc') && (
            <FieldSelect
              label="Comparaisons deux à deux"
              value={params.post_hoc}
              onChange={(v) => set({ post_hoc: v })}
              options={POST_HOC}
              hint="Une ANOVA significative dit qu'au moins deux groupes diffèrent, sans dire lesquels."
            />
          )}
          {config.fields.includes('distribution') && (
            <FieldSelect
              label="Loi testée"
              value={params.distribution}
              onChange={(v) => set({ distribution: v })}
              options={DISTRIBUTIONS}
            />
          )}
          {config.fields.includes('equal_variance') && (
            <Toggle
              label="Variances supposées égales"
              checked={params.equal_variance}
              onChange={(v) => set({ equal_variance: v })}
              hint="Désactivé : test de Welch, valable même si les variances diffèrent. C'est le choix par défaut recommandé."
            />
          )}
        </div>

        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <SliderField
            label="Seuil α"
            value={alpha}
            onChange={setAlpha}
            min={0.001}
            max={0.2}
            step={0.001}
            format={(v) => v.toFixed(3)}
            hint="Risque accepté de rejeter à tort l'hypothèse nulle. Convention usuelle : 0,05."
          />
          <SliderField label="Précision" value={precision} onChange={setPrecision} min={1} max={8} format={(v) => `${v} déc.`} />
          <button onClick={run} disabled={isRunning} className={PRIMARY_BUTTON_CLASS}>
            {isRunning ? 'Calcul…' : 'Exécuter le test'}
          </button>
          <span className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
            <InfoTip text="Enchaîner de nombreux tests sur les mêmes données augmente mécaniquement le risque de faux positif : à α = 0,05, un test sur vingt ressort significatif par hasard." />
            Multiplier les tests multiplie les faux positifs
          </span>
        </div>
      </Panel>

      {error && <ErrorBox>{error}</ErrorBox>}

      {result ? (
        <TestResult result={result} precision={precision} />
      ) : (
        !error && (
          <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400 dark:border-slate-700 dark:text-slate-500">
            Configurez un test puis lancez-le pour obtenir la statistique, la p-value, la taille d&apos;effet et son
            interprétation.
          </p>
        )
      )}

      {result && (
        <p className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
          <Badge tone="slate">{result.family}</Badge>
          <Badge tone="slate">{result.test}</Badge>
          Résultat calculé sur les données actuellement filtrées.
        </p>
      )}
    </div>
  )
}
