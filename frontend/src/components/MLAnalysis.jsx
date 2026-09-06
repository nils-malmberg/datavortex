import { useEffect, useState } from 'react'
import { getPreview, runClassification, runClustering, runPCA, runRegression } from '../api/client'
import ModelExportMenu from './ml/ModelExportMenu'
import NeuralNetworkBuilder from './ml/NeuralNetworkBuilder'
import PlotPreview from './PlotPreview'
import {
  BUTTON_CLASS,
  ChipMultiSelect,
  ErrorBox,
  FieldSelect,
  NumberField,
  Panel,
  PRIMARY_BUTTON_CLASS,
  SliderField,
  StatCard,
} from './ui/common'

const NUMERIC_TYPES = ['integer', 'float']

const ANALYSIS_TYPES = [
  { value: 'regression', label: 'Régression' },
  { value: 'classification', label: 'Classification' },
  { value: 'clustering', label: 'Clustering' },
  { value: 'pca', label: 'PCA / t-SNE' },
  { value: 'neural_network', label: 'Réseau de neurones' },
]

const REGRESSION_TYPES = [
  { value: 'linear', label: 'Linéaire' },
  { value: 'polynomial', label: 'Polynomiale' },
  { value: 'ridge', label: 'Ridge (L2)' },
  { value: 'lasso', label: 'Lasso (L1)' },
  { value: 'elastic_net', label: 'Elastic Net (L1+L2)' },
  { value: 'svr', label: 'SVR' },
  { value: 'gpr', label: 'Processus gaussien' },
  { value: 'gradient_boosting', label: 'Gradient Boosting' },
  { value: 'random_forest', label: 'Random Forest' },
]

const CLASSIFICATION_TYPES = [
  { value: 'logistic', label: 'Régression logistique' },
  { value: 'decision_tree', label: 'Arbre de décision' },
  { value: 'random_forest', label: 'Random Forest' },
  { value: 'svm', label: 'SVM' },
  { value: 'gradient_boosting', label: 'Gradient Boosting' },
  { value: 'knn', label: 'K plus proches voisins' },
  { value: 'naive_bayes', label: 'Naive Bayes' },
  { value: 'mlp', label: 'MLP (rapide)' },
  { value: 'voting', label: 'Vote (ensemble)' },
  { value: 'stacking', label: 'Stacking (ensemble)' },
]

const CLUSTERING_TYPES = [
  { value: 'kmeans', label: 'K-Means' },
  { value: 'dbscan', label: 'DBSCAN' },
  { value: 'hierarchical', label: 'Hiérarchique (dendrogramme)' },
  { value: 'agglomerative', label: 'Agglomératif' },
  { value: 'gmm', label: 'Mélange gaussien (GMM)' },
  { value: 'mean_shift', label: 'Mean Shift' },
]

const LINKAGES = ['ward', 'complete', 'average', 'single']

function describeAnalysis(analysisType, modelType, features, target) {
  if (analysisType === 'regression') return `Régression ${modelType} — ${target} ~ ${features.join(', ')}`
  if (analysisType === 'classification') return `Classification ${modelType} — ${target}`
  if (analysisType === 'clustering') return `Clustering ${modelType} — ${features.join(', ')}`
  return `${modelType.toUpperCase()} — ${features.length}D → projection`
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
  const [alpha, setAlpha] = useState(1.0)
  const [l1Ratio, setL1Ratio] = useState(0.5)
  const [kernel, setKernel] = useState('rbf')
  const [svC, setSvC] = useState(1.0)
  const [knnK, setKnnK] = useState(5)
  const [k, setK] = useState(3)
  const [eps, setEps] = useState(0.5)
  const [minSamples, setMinSamples] = useState(5)
  const [linkage, setLinkage] = useState('ward')
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

  // Empêche la fuite de la cible dans les features si elle y était déjà.
  const handleTargetChange = (col) => {
    setTarget(col)
    setFeatures((prev) => prev.filter((c) => c !== col))
  }

  const buildRegressionParams = () => {
    if (modelType === 'polynomial') return { degree: Number(degree) }
    if (['ridge', 'lasso'].includes(modelType)) return { alpha: Number(alpha) }
    if (modelType === 'elastic_net') return { alpha: Number(alpha), l1_ratio: Number(l1Ratio) }
    if (modelType === 'svr') return { kernel, C: Number(svC) }
    if (['gradient_boosting', 'random_forest'].includes(modelType)) return { n_estimators: Number(nEstimators) }
    return {}
  }

  const buildClassificationParams = () => {
    const params = {}
    if (modelType === 'decision_tree' && maxDepth) params.max_depth = Number(maxDepth)
    if (['random_forest', 'gradient_boosting'].includes(modelType)) {
      if (maxDepth) params.max_depth = Number(maxDepth)
      params.n_estimators = Number(nEstimators)
    }
    if (modelType === 'svm') params.kernel = kernel
    if (modelType === 'knn') params.k = Number(knnK)
    return params
  }

  const buildClusteringParams = () => {
    if (modelType === 'kmeans') return { k: Number(k) }
    if (modelType === 'dbscan') return { eps: Number(eps), min_samples: Number(minSamples) }
    if (['hierarchical', 'agglomerative'].includes(modelType)) return { k: Number(k), linkage }
    if (modelType === 'gmm') return { k: Number(k) }
    return {}
  }

  const buildMlReportParams = () => {
    if (analysisType === 'regression') {
      return { ml_type: 'regression', features, target, model_type: modelType, degree, params: buildRegressionParams() }
    }
    if (analysisType === 'classification') {
      return { ml_type: 'classification', features, target, model_type: modelType, params: buildClassificationParams() }
    }
    if (analysisType === 'clustering') {
      return { ml_type: 'clustering', features, model_type: modelType, params: buildClusteringParams(), color_by: colorBy || undefined }
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
        response = await runRegression(sessionId, { features, target, modelType, degree, params: buildRegressionParams() })
      } else if (analysisType === 'classification') {
        response = await runClassification(sessionId, { features, target, modelType, params: buildClassificationParams() })
      } else if (analysisType === 'clustering') {
        response = await runClustering(sessionId, { features, modelType, params: buildClusteringParams(), colorBy: colorBy || undefined })
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

  if (analysisType === 'neural_network') {
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
        <NeuralNetworkBuilder sessionId={sessionId} columns={columns} columnTypes={columnTypes} onAddToReport={onAddToReport} />
      </div>
    )
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

      <Panel className="flex flex-col gap-4">
        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-600 dark:text-slate-300">
            Features (X) {analysisType === 'pca' && '— au moins 2, numériques'}
          </p>
          <ChipMultiSelect
            options={(analysisType === 'classification' ? columns : numericColumns).filter((c) => c !== target)}
            selected={features}
            onToggle={toggleFeature}
            groupLabel="Features"
          />
        </div>

        <div className="flex flex-wrap items-end gap-4">
          {(analysisType === 'regression' || analysisType === 'classification') && (
            <FieldSelect label="Target (Y)" value={target} onChange={handleTargetChange} options={columns} allowEmpty />
          )}

          {analysisType === 'regression' && (
            <>
              <FieldSelect label="Méthode" value={modelType} onChange={setModelType} options={REGRESSION_TYPES} />
              {modelType === 'polynomial' && (
                <SliderField label="Degré" value={degree} onChange={setDegree} min={1} max={6} />
              )}
              {['ridge', 'lasso', 'elastic_net'].includes(modelType) && (
                <SliderField label="Alpha (régularisation)" value={alpha} onChange={setAlpha} min={0.01} max={10} step={0.01} format={(v) => v.toFixed(2)} />
              )}
              {modelType === 'elastic_net' && (
                <SliderField label="Ratio L1" value={l1Ratio} onChange={setL1Ratio} min={0} max={1} step={0.05} format={(v) => v.toFixed(2)} />
              )}
              {modelType === 'svr' && (
                <>
                  <FieldSelect label="Noyau" value={kernel} onChange={setKernel} options={['linear', 'rbf', 'poly']} />
                  <SliderField label="C" value={svC} onChange={setSvC} min={0.1} max={10} step={0.1} format={(v) => v.toFixed(1)} />
                </>
              )}
              {['gradient_boosting', 'random_forest'].includes(modelType) && (
                <NumberField label="Nombre d'arbres" value={nEstimators} onChange={setNEstimators} min={10} max={500} step={10} />
              )}
            </>
          )}

          {analysisType === 'classification' && (
            <>
              <FieldSelect label="Méthode" value={modelType} onChange={setModelType} options={CLASSIFICATION_TYPES} />
              {(modelType === 'decision_tree' || modelType === 'random_forest' || modelType === 'gradient_boosting') && (
                <NumberField label="Profondeur max" value={maxDepth} onChange={setMaxDepth} min={1} max={20} hint="optionnel" />
              )}
              {['random_forest', 'gradient_boosting'].includes(modelType) && (
                <NumberField label="Nombre d'arbres" value={nEstimators} onChange={setNEstimators} min={10} max={500} step={10} />
              )}
              {modelType === 'svm' && <FieldSelect label="Noyau" value={kernel} onChange={setKernel} options={['linear', 'rbf', 'poly']} />}
              {modelType === 'knn' && <SliderField label="k (voisins)" value={knnK} onChange={setKnnK} min={1} max={20} />}
            </>
          )}

          {analysisType === 'clustering' && (
            <>
              <FieldSelect label="Méthode" value={modelType} onChange={setModelType} options={CLUSTERING_TYPES} />
              {['kmeans', 'hierarchical', 'agglomerative', 'gmm'].includes(modelType) && (
                <SliderField label="k (clusters)" value={k} onChange={setK} min={2} max={10} />
              )}
              {['hierarchical', 'agglomerative'].includes(modelType) && (
                <FieldSelect label="Linkage" value={linkage} onChange={setLinkage} options={LINKAGES} />
              )}
              {modelType === 'dbscan' && (
                <>
                  <NumberField label="eps" value={eps} onChange={setEps} min={0.05} step={0.05} />
                  <NumberField label="min_samples" value={minSamples} onChange={setMinSamples} min={1} />
                </>
              )}
              <FieldSelect label="Colorer par (optionnel)" value={colorBy} onChange={setColorBy} options={columns} allowEmpty />
            </>
          )}

          {analysisType === 'pca' && (
            <>
              <FieldSelect label="Dimensions" value={String(nComponents)} onChange={(v) => setNComponents(Number(v))} options={['2', '3']} />
              <FieldSelect label="Algo" value={pcaMethod} onChange={setPcaMethod} options={['pca', 'tsne', 'umap']} />
              <FieldSelect label="Colorer par (optionnel)" value={colorBy} onChange={setColorBy} options={columns} allowEmpty />
            </>
          )}
        </div>

        <div>
          <button onClick={handleRun} disabled={!canRun || isRunning} className={`${PRIMARY_BUTTON_CLASS} px-5 py-2`}>
            {isRunning ? 'Analyse en cours…' : 'Lancer'}
          </button>
        </div>
      </Panel>

      {error && <ErrorBox>{error}</ErrorBox>}

      {result && (
        <div className="flex flex-col gap-4">
          {analysisType === 'regression' && (
            <>
              <div className="flex flex-wrap gap-3">
                <StatCard label="R²" value={result.r2.toFixed(4)} />
                <StatCard label="RMSE" value={result.rmse.toFixed(4)} />
                <StatCard label="MAE" value={result.mae.toFixed(4)} />
                <StatCard label="Échantillons" value={result.n_samples} />
                {result.cross_validation && (
                  <StatCard
                    label={`R² validé croisé (${result.cross_validation.cv} plis)`}
                    value={`${result.cross_validation.mean.toFixed(3)} ± ${result.cross_validation.std.toFixed(3)}`}
                  />
                )}
              </div>
              {result.equation && (
                <p className="rounded-md bg-slate-100 px-4 py-2 font-mono text-sm text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  {result.equation}
                </p>
              )}
              <PlotPreview figure={result.plot_data.main} />
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {result.plot_data.residuals && <PlotPreview figure={result.plot_data.residuals} />}
                {result.plot_data.feature_importance && <PlotPreview figure={result.plot_data.feature_importance} />}
              </div>
              {result.coefficients && (
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-100 dark:bg-slate-800">
                      <tr>
                        <th className="px-3 py-1.5 text-left font-semibold text-slate-600 dark:text-slate-300">Variable</th>
                        <th className="px-3 py-1.5 text-left font-semibold text-slate-600 dark:text-slate-300">Coefficient</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.coefficients.map((c) => (
                        <tr key={c.feature} className="border-t border-slate-100 dark:border-slate-800">
                          <td className="px-3 py-1.5">{c.feature}</td>
                          <td className="px-3 py-1.5 font-mono">{c.coefficient.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <ModelExportMenu sessionId={sessionId} modelId={result.model_id} task="regression" />
            </>
          )}

          {analysisType === 'classification' && (
            <>
              <div className="flex flex-wrap gap-3">
                <StatCard label="Accuracy" value={`${(result.accuracy * 100).toFixed(1)}%`} />
                <StatCard label="Precision" value={`${(result.precision * 100).toFixed(1)}%`} />
                <StatCard label="Recall" value={`${(result.recall * 100).toFixed(1)}%`} />
                <StatCard label="F1" value={`${(result.f1 * 100).toFixed(1)}%`} />
                {result.roc_auc !== null && <StatCard label="AUC (macro)" value={result.roc_auc.toFixed(3)} />}
                <StatCard label="Train / Test" value={`${result.n_train} / ${result.n_test}`} />
                {result.cross_validation && (
                  <StatCard
                    label={`Accuracy validée croisée (${result.cross_validation.cv} plis)`}
                    value={`${(result.cross_validation.mean * 100).toFixed(1)}% ± ${(result.cross_validation.std * 100).toFixed(1)}%`}
                  />
                )}
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <PlotPreview figure={result.plot_data.main} />
                {result.plot_data.roc && <PlotPreview figure={result.plot_data.roc} />}
              </div>
              {result.plot_data.feature_importance && <PlotPreview figure={result.plot_data.feature_importance} />}
              {result.tree_image_base64 && (
                <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-900">
                  <img
                    src={`data:image/png;base64,${result.tree_image_base64}`}
                    alt="Arbre de décision"
                    className="mx-auto"
                  />
                </div>
              )}
              <ModelExportMenu sessionId={sessionId} modelId={result.model_id} task="classification" />
            </>
          )}

          {analysisType === 'clustering' && (
            <>
              <div className="flex flex-wrap gap-3">
                <StatCard label="Clusters trouvés" value={result.n_clusters} />
                <StatCard label="Silhouette" value={result.silhouette_score !== null ? result.silhouette_score.toFixed(4) : '—'} />
                <StatCard label="Davies-Bouldin" value={result.davies_bouldin_score !== null ? result.davies_bouldin_score.toFixed(4) : '—'} sub="plus bas = mieux séparé" />
                <StatCard label="Calinski-Harabasz" value={result.calinski_harabasz_score !== null ? result.calinski_harabasz_score.toFixed(1) : '—'} sub="plus haut = mieux séparé" />
                <StatCard label="Échantillons" value={result.n_samples} />
              </div>
              <PlotPreview figure={result.plot_data.main} />
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                {result.plot_data.elbow_curve && <PlotPreview figure={result.plot_data.elbow_curve} />}
                {result.plot_data.dendrogram && <PlotPreview figure={result.plot_data.dendrogram} />}
              </div>
              <div className="flex flex-wrap gap-2">
                {result.cluster_sizes.map((c) => (
                  <span key={c.cluster} className="rounded-md border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                    {c.cluster} : {c.count} lignes
                  </span>
                ))}
              </div>
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
              className={`${BUTTON_CLASS} self-start`}
            >
              + Ajouter au rapport
            </button>
          )}
        </div>
      )}
    </div>
  )
}
