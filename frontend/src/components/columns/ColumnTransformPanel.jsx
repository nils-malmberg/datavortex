import { useEffect, useState } from 'react'
import ResultTable from '../ui/ResultTable'
import {
  Badge,
  ErrorBox,
  FieldSelect,
  INPUT_CLASS,
  InfoTip,
  NumberField,
  PRIMARY_BUTTON_CLASS,
  Panel,
  Segmented,
  Toggle,
} from '../ui/common'

/**
 * Transformations dérivant une nouvelle colonne d'une colonne existante.
 * Chaque transformation n'expose que ses propres paramètres, et le résultat
 * est prévisualisé sur les premières lignes avant d'être conservé.
 */
const TRANSFORMS = [
  {
    value: 'binning',
    label: 'Découper en classes',
    hint: "Transforme une variable continue en catégories : utile pour croiser un âge avec une variable qualitative.",
    numericOnly: true,
  },
  {
    value: 'encoding',
    label: 'Encoder',
    hint: 'Traduit une variable qualitative en nombres, forme exigée par la plupart des modèles.',
    numericOnly: false,
  },
  {
    value: 'lag',
    label: 'Décaler (lag)',
    hint: "Reporte la valeur d'une ligne sur la suivante : sert à comparer une observation à la précédente.",
    numericOnly: false,
  },
  {
    value: 'rolling',
    label: 'Fenêtre glissante',
    hint: "Agrège les N dernières lignes : lisse une série et fait ressortir sa tendance.",
    numericOnly: true,
  },
]

const BINNING_METHODS = [
  { value: 'equal_width', label: 'Largeur égale' },
  { value: 'quantile', label: 'Effectifs égaux' },
  { value: 'custom', label: 'Bornes choisies' },
]

const ENCODING_METHODS = [
  { value: 'label', label: 'Ordinal (0, 1, 2…)' },
  { value: 'onehot', label: 'One-hot (une colonne par modalité)' },
  { value: 'frequency', label: 'Fréquence (effectif de la modalité)' },
]

const ROLLING_FUNCTIONS = ['mean', 'median', 'sum', 'min', 'max', 'std', 'var', 'count']

export default function ColumnTransformPanel({ columns, numericColumns, onApply }) {
  const [transform, setTransform] = useState('binning')
  const [source, setSource] = useState('')
  const [newName, setNewName] = useState('')
  const [replace, setReplace] = useState(false)
  const [params, setParams] = useState({
    method: 'equal_width',
    bins: 5,
    edges: '',
    as_label: true,
    periods: 1,
    window: 3,
    function: 'mean',
    center: false,
    group_by: '',
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isRunning, setIsRunning] = useState(false)

  const config = TRANSFORMS.find((t) => t.value === transform)
  const sourceOptions = config.numericOnly ? numericColumns : columns

  useEffect(() => {
    if (!sourceOptions.includes(source)) setSource(sourceOptions[0] || '')
  }, [sourceOptions, source])

  useEffect(() => {
    // Réinitialise la méthode par défaut cohérente avec la transformation.
    setParams((prev) => ({
      ...prev,
      method: transform === 'binning' ? 'equal_width' : transform === 'encoding' ? 'label' : prev.method,
    }))
    setResult(null)
    setError(null)
  }, [transform])

  const set = (patch) => setParams((prev) => ({ ...prev, ...patch }))

  const buildParams = () => {
    if (transform === 'binning') {
      const payload = { method: params.method, bins: Number(params.bins), as_label: params.as_label }
      if (params.method === 'custom') {
        payload.edges = String(params.edges)
          .split(',')
          .map((v) => Number(v.trim()))
          .filter((v) => Number.isFinite(v))
      }
      return payload
    }
    if (transform === 'encoding') return { method: params.method }
    if (transform === 'lag') {
      return { periods: Number(params.periods), group_by: params.group_by || undefined }
    }
    return {
      window: Number(params.window),
      function: params.function,
      center: params.center,
      group_by: params.group_by || undefined,
    }
  }

  const apply = async () => {
    setIsRunning(true)
    setError(null)
    try {
      const data = await onApply({
        transform,
        source,
        params: buildParams(),
        newName: newName.trim() || undefined,
        replace,
      })
      setResult(data)
      setNewName('')
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Impossible d'appliquer cette transformation.")
      setResult(null)
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <Panel className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium text-slate-600 dark:text-slate-300">Transformation</span>
        <Segmented options={TRANSFORMS} value={transform} onChange={setTransform} size="sm" />
        <p className="text-xs text-slate-500 dark:text-slate-400">{config.hint}</p>
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <FieldSelect
          label="Colonne source"
          value={source}
          onChange={setSource}
          options={sourceOptions}
          hint={config.numericOnly ? 'Seules les colonnes numériques conviennent à cette transformation.' : undefined}
        />

        {transform === 'binning' && (
          <>
            <FieldSelect label="Méthode" value={params.method} onChange={(v) => set({ method: v })} options={BINNING_METHODS} />
            {params.method !== 'custom' ? (
              <NumberField label="Nombre de classes" value={params.bins} onChange={(v) => set({ bins: v })} min={2} max={100} />
            ) : (
              <label className="flex flex-col gap-1 text-sm">
                <span className="flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300">
                  Bornes
                  <InfoTip text="Valeurs séparées par des virgules, par exemple : 0, 18, 40, 65, 120" />
                </span>
                <input
                  value={params.edges}
                  onChange={(e) => set({ edges: e.target.value })}
                  placeholder="0, 18, 40, 65, 120"
                  className={`${INPUT_CLASS} w-56`}
                />
              </label>
            )}
            <Toggle
              label="Libellés lisibles"
              checked={params.as_label}
              onChange={(v) => set({ as_label: v })}
              hint="Activé : « (20, 40] ». Désactivé : le numéro de la classe, exploitable par un modèle."
            />
          </>
        )}

        {transform === 'encoding' && (
          <FieldSelect label="Méthode" value={params.method} onChange={(v) => set({ method: v })} options={ENCODING_METHODS} />
        )}

        {transform === 'lag' && (
          <>
            <NumberField
              label="Décalage"
              value={params.periods}
              onChange={(v) => set({ periods: v })}
              hint="Positif : la valeur remonte des lignes précédentes. Négatif : des lignes suivantes."
            />
            <FieldSelect
              label="Par groupe (optionnel)"
              value={params.group_by}
              onChange={(v) => set({ group_by: v })}
              options={columns}
              allowEmpty
              hint="Le décalage repart de zéro à chaque groupe, sans déborder de l'un sur l'autre."
            />
          </>
        )}

        {transform === 'rolling' && (
          <>
            <NumberField label="Fenêtre" value={params.window} onChange={(v) => set({ window: v })} min={2} suffix="lignes" />
            <FieldSelect label="Agrégation" value={params.function} onChange={(v) => set({ function: v })} options={ROLLING_FUNCTIONS} />
            <Toggle
              label="Fenêtre centrée"
              checked={params.center}
              onChange={(v) => set({ center: v })}
              hint="Centrée : la fenêtre englobe autant de lignes avant qu'après. Sinon elle ne regarde que le passé."
            />
            <FieldSelect
              label="Par groupe (optionnel)"
              value={params.group_by}
              onChange={(v) => set({ group_by: v })}
              options={columns}
              allowEmpty
            />
          </>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-slate-600 dark:text-slate-300">Nom de la colonne créée</span>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={`${source}_${transform}`}
            className={`${INPUT_CLASS} w-56`}
          />
        </label>
        <Toggle label="Remplacer si le nom existe" checked={replace} onChange={setReplace} />
        <button onClick={apply} disabled={!source || isRunning} className={PRIMARY_BUTTON_CLASS}>
          {isRunning ? 'Application…' : 'Appliquer'}
        </button>
      </div>

      {error && <ErrorBox>{error}</ErrorBox>}

      {result && (
        <div className="flex flex-col gap-2">
          <p className="flex flex-wrap items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
            {result.created_columns.map((c) => (
              <Badge key={c} tone="green">
                {c}
              </Badge>
            ))}
            <span className="text-slate-500 dark:text-slate-400">créée(s) — {result.description}</span>
          </p>
          {Object.entries(result.null_count).some(([, n]) => n > 0) && (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              Valeurs manquantes produites :{' '}
              {Object.entries(result.null_count)
                .filter(([, n]) => n > 0)
                .map(([c, n]) => `${c} (${n})`)
                .join(', ')}{' '}
              — normal pour un décalage ou une fenêtre glissante, qui n&apos;ont pas de valeur en début de série.
            </p>
          )}
          <ResultTable
            columns={Object.keys(result.preview[0] || {})}
            rows={result.preview}
            highlightColumns={result.created_columns}
            precision={4}
            maxHeight="260px"
          />
        </div>
      )}
    </Panel>
  )
}
