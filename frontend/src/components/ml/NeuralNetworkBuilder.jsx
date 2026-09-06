import { useState } from 'react'
import { runNeuralNetwork } from '../../api/client'
import PlotPreview from '../PlotPreview'
import {
  BUTTON_CLASS,
  ChipMultiSelect,
  ErrorBox,
  FieldSelect,
  NumberField,
  Panel,
  PRIMARY_BUTTON_CLASS,
  SectionTitle,
  SliderField,
  StatCard,
} from '../ui/common'
import ModelExportMenu from './ModelExportMenu'
import NetworkDiagram from './NetworkDiagram'

const ACTIVATIONS = ['relu', 'tanh', 'sigmoid', 'linear']
const OPTIMIZERS = ['adam', 'sgd', 'rmsprop']

function defaultLayers() {
  return [
    { units: 16, activation: 'relu', dropout: 0 },
    { units: 8, activation: 'relu', dropout: 0 },
  ]
}

/**
 * Constructeur de réseau de neurones (Phase 8.1) : architecture éditable,
 * entraînement TensorFlow/Keras réel côté serveur, courbes d'apprentissage
 * et diagramme du réseau construit à partir des poids effectivement appris.
 */
export default function NeuralNetworkBuilder({ sessionId, columns, columnTypes, onAddToReport }) {
  const numericColumns = columns.filter((c) => ['integer', 'float'].includes(columnTypes[c]))

  const [features, setFeatures] = useState([])
  const [target, setTarget] = useState('')
  const [task, setTask] = useState('classification')
  const [layers, setLayers] = useState(defaultLayers())
  const [optimizer, setOptimizer] = useState('adam')
  const [learningRate, setLearningRate] = useState(0.001)
  const [batchSize, setBatchSize] = useState(32)
  const [epochs, setEpochs] = useState(50)
  const [validationSplit, setValidationSplit] = useState(0.2)
  const [showAdvancedViz, setShowAdvancedViz] = useState(false)

  const [result, setResult] = useState(null)
  const [isTraining, setIsTraining] = useState(false)
  const [error, setError] = useState(null)

  const toggleFeature = (col) => setFeatures((prev) => (prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]))

  const updateLayer = (index, patch) =>
    setLayers((prev) => prev.map((layer, i) => (i === index ? { ...layer, ...patch } : layer)))

  const addLayer = () => setLayers((prev) => (prev.length >= 8 ? prev : [...prev, { units: 16, activation: 'relu', dropout: 0 }]))
  const removeLayer = (index) => setLayers((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== index)))

  const canTrain = features.length > 0 && !!target && layers.length > 0

  const handleTrain = async () => {
    setIsTraining(true)
    setError(null)
    setResult(null)
    try {
      const { data } = await runNeuralNetwork(sessionId, {
        features, target, task, layers, optimizer,
        learningRate: Number(learningRate), batchSize: Number(batchSize),
        epochs: Number(epochs), validationSplit: Number(validationSplit),
      })
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.error?.message || "Impossible d'entraîner ce réseau avec ces paramètres.")
    } finally {
      setIsTraining(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Panel className="flex flex-col gap-4">
        <SectionTitle hint="MLP (perceptron multicouche) entraîné avec TensorFlow/Keras, architecture entièrement configurable.">
          Architecture du réseau
        </SectionTitle>

        <div>
          <p className="mb-1.5 text-sm font-medium text-slate-600 dark:text-slate-300">Features (X)</p>
          <ChipMultiSelect options={numericColumns} selected={features} onToggle={toggleFeature} groupLabel="Features" />
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <FieldSelect label="Target (Y)" value={target} onChange={setTarget} options={columns} allowEmpty />
          <FieldSelect
            label="Tâche"
            value={task}
            onChange={setTask}
            options={[{ value: 'classification', label: 'Classification' }, { value: 'regression', label: 'Régression' }]}
          />
          <FieldSelect label="Optimiseur" value={optimizer} onChange={setOptimizer} options={OPTIMIZERS} />
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300">Couches cachées</p>
          {layers.map((layer, index) => (
            <div key={index} className="flex flex-wrap items-end gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              <span className="text-xs font-semibold text-slate-400 dark:text-slate-500">Couche {index + 1}</span>
              <SliderField label="Neurones" value={layer.units} onChange={(v) => updateLayer(index, { units: v })} min={1} max={512} />
              <FieldSelect label="Activation" value={layer.activation} onChange={(v) => updateLayer(index, { activation: v })} options={ACTIVATIONS} />
              <SliderField
                label="Dropout"
                value={Math.round(layer.dropout * 100)}
                onChange={(v) => updateLayer(index, { dropout: v / 100 })}
                min={0} max={50} format={(v) => `${v}%`}
              />
              <button onClick={() => removeLayer(index)} disabled={layers.length <= 1} className={BUTTON_CLASS}>
                Retirer
              </button>
            </div>
          ))}
          <button onClick={addLayer} disabled={layers.length >= 8} className={`${BUTTON_CLASS} self-start`}>
            + Ajouter une couche
          </button>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <SliderField label="Taux d'apprentissage" value={learningRate} onChange={setLearningRate} min={0.0001} max={0.1} step={0.0001} format={(v) => v.toFixed(4)} />
          <NumberField label="Taille de batch" value={batchSize} onChange={setBatchSize} min={1} max={512} />
          <NumberField label="Époques" value={epochs} onChange={setEpochs} min={1} max={500} />
          <SliderField label="Validation" value={Math.round(validationSplit * 100)} onChange={(v) => setValidationSplit(v / 100)} min={5} max={40} format={(v) => `${v}%`} />
        </div>

        <button onClick={handleTrain} disabled={!canTrain || isTraining} className={`${PRIMARY_BUTTON_CLASS} self-start px-6 py-2`}>
          {isTraining ? 'Entraînement en cours…' : 'Entraîner le réseau'}
        </button>
      </Panel>

      {error && <ErrorBox>{error}</ErrorBox>}

      {result && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-3">
            {result.task === 'classification' ? (
              <StatCard label="Accuracy" value={`${(result.performance.accuracy * 100).toFixed(1)}%`} />
            ) : (
              <>
                <StatCard label="R²" value={result.performance.r2.toFixed(4)} />
                <StatCard label="RMSE" value={result.performance.rmse.toFixed(4)} />
                <StatCard label="MAE" value={result.performance.mae.toFixed(4)} />
              </>
            )}
            <StatCard label="Train / Test" value={`${result.n_train} / ${result.n_test}`} />
          </div>

          <SectionTitle>Courbes d&apos;apprentissage (train vs validation)</SectionTitle>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PlotPreview figure={result.plot_data.loss} />
            <PlotPreview figure={result.plot_data.metric} />
          </div>

          <SectionTitle hint="Nœuds d'entrée nommés par les features, sortie nommée par la cible/les classes, connexions colorées par les poids réellement appris.">
            Diagramme du réseau
          </SectionTitle>
          <NetworkDiagram
            layerSizes={result.layer_sizes}
            weights={result.weights}
            featureNames={result.feature_names}
            targetClasses={result.target_classes}
            task={result.task}
          />

          <button onClick={() => setShowAdvancedViz((v) => !v)} className={`${BUTTON_CLASS} self-start`}>
            {showAdvancedViz ? 'Masquer' : 'Afficher'} la visualisation avancée
          </button>
          {showAdvancedViz && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <PlotPreview figure={result.plot_data.main} />
              {result.plot_data.feature_importance && <PlotPreview figure={result.plot_data.feature_importance} />}
            </div>
          )}

          <ModelExportMenu sessionId={sessionId} modelId={result.model_id} task="neural_network" />

          {onAddToReport && (
            <button
              onClick={() =>
                onAddToReport({
                  id: crypto.randomUUID(),
                  kind: 'ml',
                  params: { ml_type: 'neural_network', features, target, task, layers, optimizer, learningRate, batchSize, epochs, validationSplit },
                  label: `Réseau de neurones — ${target} (${layers.length} couche(s))`,
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
