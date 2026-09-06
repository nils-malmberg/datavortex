import { useEffect, useState } from 'react'
import { getPreview, runClassification, runClustering, runPCA, runRegression } from '../api/client'
import PlotPreview from './PlotPreview'

const NUMERIC_TYPES = ['integer', 'float']

const ANALYSIS_TYPES = [
  { value: 'regression', label: 'Regression' },
  { value: 'classification', label: 'Classification' },
  { value: 'clustering', label: 'Clustering' },
  { value: 'pca', label: 'PCA' },
]

function describeAnalysis(analysisType, modelType, features, target) {
  if (analysisType === 'regression') return `Régression ${modelType} — ${target} ~ ${features.join(', ')}`
  if (analysisType === 'classification') return `Classification ${modelType} — ${target}`
  if (analysisType === 'clustering') return `Clustering ${modelType} — ${features.join(', ')}`
  return `${modelType.toUpperCase()} — ${features.length}D → projection`
}

function ColumnCheckbox({ label, checked, onChange }) {
  return (
    <label
      className={`cursor-pointer rounded-md border px-2.5 py-1 text-xs font-medium ${
        checked
          ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950/40 dark:text-blue-300'
          : 'border-slate-300 bg-white text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300'
      }`}
    >
      <input type="checkbox" className="hidden" checked={checked} onChange={onChange} />
      {label}
    </label>
  )
}

function FieldSelect({ label, value, onChange, options, allowEmpty, emptyLabel = '—' }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-slate-600 dark:text-slate-300">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="min-w-[9rem] rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
      >
        {allowEmpty && <option value="">{emptyLabel}</option>}
        {options.map((col) => (
          <option key={col} value={col}>
            {col}
          </option>
        ))}
      </select>
    </label>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-2 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-slate-800 dark:text-slate-100">{value}</p>
    </div>
  )
}

export default function MLAnalysis({ sessionId, refreshKey, onAddToReport }) {
  const [columns, setColumns] = useState([])
  const [columnTypes, setColumnTypes] = useState({})
  const [analysisType, setAnalysisType] = useState('regression')

  const [features, setFeatures] = useState([])
  const [target, setTarget] = useState('')
  const [colorBy, setColorBy] = useState('')

  const [modelType, setModelType] = useState('linear')
  const [degree, setDegree] = useState(2)
  const [maxDepth, setMaxDepth] = useState('')
  const [nEstimators, setNEstimators] = useState(100)
  const [k, setK] = useState(3)
  const [eps, setEps] = useState(0.5)
  const [minSamples, setMinSamples] = useState(5)
  const [pcaMethod, setPcaMethod] = useState('pca')
  const [nComponents, setNComponents] = useState(2)

  const [result, setResult] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getPreview(sessionId).then(({ data }) => {
      setColumns(data.columns)
      setColumnTypes(data.column_types)
    })
  }, [sessionId, refreshKey])

  const numericColumns = columns.filter((c) => NUMERIC_TYPES.includes(columnTypes[c]))

  const handleTypeChange = (value) => {
    setAnalysisType(value)
    setResult(null)
    setError(null)
    setFeatures([])
    setTarget('')
    setColorBy('')
    if (value === 'regression') setModelType('linear')
    if (value === 'classification') setModelType('logistic')
    if (value === 'clustering') setModelType('kmeans')
    if (value === 'pca') setPcaMethod('pca')
  }

  const toggleFeature = (col) => {
    setFeatures((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]))
  }

  const buildMlReportParams = () => {
    if (analysisType === 'regression') {
      return { ml_type: 'regression', features, target, model_type: modelType, degree }
    }
    if (analysisType === 'classification') {
      const params = {}
      if (modelType === 'decision_tree' && maxDepth) params.max_depth = Number(maxDepth)
      if (modelType === 'random_forest') {
        if (maxDepth) params.max_depth = Number(maxDepth)
        params.n_estimators = Number(nEstimators)
      }
      return { ml_type: 'classification', features, target, model_type: modelType, params }
    }
    if (analysisType === 'clustering') {
      const params = modelType === 'kmeans' ? { k: Number(k) } : { eps: Number(eps), min_samples: Number(minSamples) }
      return { ml_type: 'clustering', features, model_type: modelType, params, color_by: colorBy || undefined }
    }
    return { ml_type: 'pca', features, n_components: nComponents, method: pcaMethod, color_by: colorBy || undefined }
  }

  const handleRun = async () => {
    setIsRunning(true)
    setError(null)
    setResult(null)
    try {
      let response
      if (analysisType === 'regression') {
        response = await runRegression(sessionId, { features, target, modelType, degree })
      } else if (analysisType === 'classification') {
        const params = {}
        if (modelType === 'decision_tree' && maxDepth) params.max_depth = Number(maxDepth)
        if (modelType === 'random_forest') {
          if (maxDepth) params.max_depth = Number(maxDepth)
          params.n_estimators = Number(nEstimators)
        }
        response = await runClassification(sessionId, { features, target, modelType, params })
      } else if (analysisType === 'clustering') {
        const params = modelType === 'kmeans' ? { k: Number(k) } : { eps: Number(eps), min_samples: Number(minSamples) }
        response = await runClustering(sessionId, { features, modelType, params, colorBy: colorBy || undefined })
      } else {
        response = await runPCA(sessionId, { features, nComponents, method: pcaMethod, colorBy: colorBy || undefined })
      }
      setResult(response.data)
    } catch (err) {
      setError(
        err?.response?.data?.error?.message || "Impossible d'exécuter cette analyse avec ces paramètres.",
      )
    } finally {
      setIsRunning(false)
    }
  }

  const canRun = (() => {
    if (analysisType === 'regression') return features.length > 0 && !!target
    if (analysisType === 'classification') return features.length > 0 && !!target
    if (analysisType === 'clustering') return features.length > 0
    return features.length >= 2
  })()

  if (columns.length === 0) {
    return <p className="p-4 text-sm text-slate-500 dark:text-slate-400">Chargement des colonnes…</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap gap-2">
        {ANALYSIS_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => handleTypeChange(t.value)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              analysisType === t.value
                ? 'bg-blue-600 text-white dark:bg-blue-500'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-600 dark:text-slate-300">
            Features (X) {analysisType === 'pca' && '— au moins 2, numériques'}
          </p>
          <div className="flex flex-wrap gap-2">
            {(analysisType === 'classification' ? columns : numericColumns).map((col) => (
              <ColumnCheckbox
                key={col}
                label={col}
                checked={features.includes(col)}
                onChange={() => toggleFeature(col)}
              />
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          {(analysisType === 'regression' || analysisType === 'classification') && (
            <FieldSelect label="Target (Y)" value={target} onChange={setTarget} options={columns} allowEmpty />
          )}

          {analysisType === 'regression' && (
            <>
              <FieldSelect
                label="Type"
                value={modelType}
                onChange={setModelType}
                options={['linear', 'polynomial']}
              />
              {modelType === 'polynomial' && (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="font-medium text-slate-600 dark:text-slate-300">Degré ({degree})</span>
                  <input
                    type="range" min={1} max={6} value={degree}
                    onChange={(e) => setDegree(Number(e.target.value))}
                    className="w-40"
                  />
                </label>
              )}
            </>
          )}

          {analysisType === 'classification' && (
            <>
              <FieldSelect
                label="Type"
                value={modelType}
                onChange={setModelType}
                options={['logistic', 'decision_tree', 'random_forest']}
              />
              {(modelType === 'decision_tree' || modelType === 'random_forest') && (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="font-medium text-slate-600 dark:text-slate-300">Profondeur max (optionnel)</span>
                  <input
                    type="number" min={1} max={20} value={maxDepth}
                    onChange={(e) => setMaxDepth(e.target.value)}
                    placeholder="auto"
                    className="w-24 rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  />
                </label>
              )}
              {modelType === 'random_forest' && (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="font-medium text-slate-600 dark:text-slate-300">Nombre d&apos;arbres</span>
                  <input
                    type="number" min={10} max={500} step={10} value={nEstimators}
                    onChange={(e) => setNEstimators(e.target.value)}
                    className="w-24 rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                  />
                </label>
              )}
            </>
          )}

          {analysisType === 'clustering' && (
            <>
              <FieldSelect label="Type" value={modelType} onChange={setModelType} options={['kmeans', 'dbscan']} />
              {modelType === 'kmeans' ? (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="font-medium text-slate-600 dark:text-slate-300">k ({k})</span>
                  <input type="range" min={2} max={10} value={k} onChange={(e) => setK(Number(e.target.value))} className="w-40" />
                </label>
              ) : (
                <>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium text-slate-600 dark:text-slate-300">eps</span>
                    <input
                      type="number" step={0.1} min={0.05} value={eps}
                      onChange={(e) => setEps(e.target.value)}
                      className="w-24 rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-sm">
                    <span className="font-medium text-slate-600 dark:text-slate-300">min_samples</span>
                    <input
                      type="number" min={1} value={minSamples}
                      onChange={(e) => setMinSamples(e.target.value)}
                      className="w-24 rounded-md border border-slate-300 px-3 py-1.5 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                    />
                  </label>
                </>
              )}
              <FieldSelect
                label="Colorer par (optionnel)"
                value={colorBy}
                onChange={setColorBy}
                options={columns}
                allowEmpty
              />
            </>
          )}

          {analysisType === 'pca' && (
            <>
              <FieldSelect label="Dimensions" value={String(nComponents)} onChange={(v) => setNComponents(Number(v))} options={['2', '3']} />
              <FieldSelect label="Algo" value={pcaMethod} onChange={setPcaMethod} options={['pca', 'tsne', 'umap']} />
              <FieldSelect
                label="Colorer par (optionnel)"
                value={colorBy}
                onChange={setColorBy}
                options={columns}
                allowEmpty
              />
            </>
          )}
        </div>

        <div>
          <button
            onClick={handleRun}
            disabled={!canRun || isRunning}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 dark:bg-blue-500 dark:hover:bg-blue-600"
          >
            {isRunning ? 'Analyse en cours…' : 'Run'}
          </button>
        </div>
      </div>

      {error && (
        <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </p>
      )}

      {result && (
        <div className="flex flex-col gap-4">
          {analysisType === 'regression' && (
            <>
              <div className="flex flex-wrap gap-3">
                <StatCard label="R²" value={result.r2.toFixed(4)} />
                <StatCard label="RMSE" value={result.rmse.toFixed(4)} />
                <StatCard label="Échantillons" value={result.n_samples} />
              </div>
              <p className="rounded-md bg-slate-100 px-4 py-2 font-mono text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {result.equation}
              </p>
              <PlotPreview figure={result.plot_data.main} />
            </>
          )}

          {analysisType === 'classification' && (
            <>
              <div className="flex flex-wrap gap-3">
                <StatCard label="Accuracy" value={`${(result.accuracy * 100).toFixed(1)}%`} />
                <StatCard label="Train / Test" value={`${result.n_train} / ${result.n_test}`} />
              </div>
              <PlotPreview figure={result.plot_data.main} />
              {result.plot_data.feature_importance && (
                <PlotPreview figure={result.plot_data.feature_importance} />
              )}
              {result.tree_image_base64 && (
                <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
                  <img
                    src={`data:image/png;base64,${result.tree_image_base64}`}
                    alt="Arbre de décision"
                    className="mx-auto"
                  />
                </div>
              )}
            </>
          )}

          {analysisType === 'clustering' && (
            <>
              <div className="flex flex-wrap gap-3">
                <StatCard label="Clusters trouvés" value={result.n_clusters} />
                <StatCard
                  label="Silhouette score"
                  value={result.silhouette_score !== null ? result.silhouette_score.toFixed(4) : '—'}
                />
                <StatCard label="Échantillons" value={result.n_samples} />
              </div>
              <PlotPreview figure={result.plot_data.main} />
              {result.plot_data.elbow_curve && <PlotPreview figure={result.plot_data.elbow_curve} />}
            </>
          )}

          {analysisType === 'pca' && (
            <>
              <div className="flex flex-wrap gap-3">
                {result.explained_variance && (
                  <StatCard
                    label="Variance expliquée"
                    value={`${result.explained_variance.map((v) => `${(v * 100).toFixed(1)}%`).join(' + ')}`}
                  />
                )}
                <StatCard label="Échantillons" value={result.n_samples} />
              </div>
              <PlotPreview figure={result.plot_data.main} />
            </>
          )}

          {onAddToReport && (
            <button
              onClick={() =>
                onAddToReport({
                  id: crypto.randomUUID(),
                  kind: 'ml',
                  params: buildMlReportParams(),
                  label: describeAnalysis(analysisType, analysisType === 'pca' ? pcaMethod : modelType, features, target),
                })
              }
              className="self-start rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              + Ajouter au rapport
            </button>
          )}
        </div>
      )}
    </div>
  )
}
