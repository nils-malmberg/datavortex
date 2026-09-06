import { useMemo, useState } from 'react'

const MAX_NODES_PER_LAYER = 16 // au-delà, dessiner chaque neurone/connexion devient illisible et lourd
const NODE_RADIUS = 9
const LAYER_GAP = 150
const NODE_GAP = 28
const PADDING = 100

function weightColor(value, maxAbs) {
  const ratio = maxAbs > 0 ? Math.min(1, Math.abs(value) / maxAbs) : 0
  const alpha = 0.15 + ratio * 0.75
  return value >= 0 ? `rgba(37, 99, 235, ${alpha})` : `rgba(220, 38, 38, ${alpha})`
}

/**
 * Diagramme du réseau de neurones (Phase 8.1) : nœuds d'entrée nommés par les
 * features, couches cachées, sortie nommée par les classes (ou la cible en
 * régression), connexions colorées par le signe/l'intensité du poids réel.
 * Les couches trop larges sont échantillonnées (les poids restent réels,
 * seul l'affichage est limité) pour rester lisible et léger.
 */
export default function NetworkDiagram({ layerSizes, weights, featureNames, targetClasses, task }) {
  const [hoveredLayer, setHoveredLayer] = useState(null)

  const layout = useMemo(() => {
    const layers = layerSizes.map((size, layerIndex) => {
      const shown = Math.min(size, MAX_NODES_PER_LAYER)
      const indices = Array.from({ length: shown }, (_, i) =>
        shown === size ? i : Math.round((i * (size - 1)) / Math.max(1, shown - 1)),
      )
      return { size, shown, indices, x: PADDING + layerIndex * LAYER_GAP }
    })
    const maxShown = Math.max(...layers.map((l) => l.shown))
    const height = PADDING * 2 + maxShown * NODE_GAP
    layers.forEach((layer) => {
      const totalHeight = layer.shown * NODE_GAP
      const startY = (height - totalHeight) / 2 + NODE_GAP / 2
      layer.positions = layer.indices.map((_, i) => startY + i * NODE_GAP)
    })
    const width = PADDING * 2 + (layers.length - 1) * LAYER_GAP
    return { layers, width, height }
  }, [layerSizes])

  const maxAbsWeight = useMemo(() => {
    let max = 0
    for (const layer of weights) {
      for (const row of layer.kernel) {
        for (const v of row) max = Math.max(max, Math.abs(v))
      }
    }
    return max || 1
  }, [weights])

  const labelFor = (layerIndex, nodeIndex) => {
    if (layerIndex === 0) return featureNames[nodeIndex] || `x${nodeIndex + 1}`
    if (layerIndex === layout.layers.length - 1) {
      if (task === 'classification' && targetClasses) {
        return targetClasses.length === 2 ? targetClasses[1] : targetClasses[nodeIndex] || `classe ${nodeIndex}`
      }
      return 'y'
    }
    return null
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <svg width={layout.width} height={layout.height} className="mx-auto block" role="img" aria-label="Diagramme du réseau de neurones">
        {/* Connexions : dessinées avant les nœuds pour rester en arrière-plan */}
        {layout.layers.slice(0, -1).map((layer, layerIndex) => {
          const next = layout.layers[layerIndex + 1]
          const kernel = weights[layerIndex]?.kernel
          if (!kernel) return null
          const dimmed = hoveredLayer !== null && hoveredLayer !== layerIndex && hoveredLayer !== layerIndex + 1
          return (
            <g key={layerIndex} opacity={dimmed ? 0.08 : 1}>
              {layer.indices.map((fromIdx, i) =>
                next.indices.map((toIdx, j) => {
                  const w = kernel[fromIdx]?.[toIdx] ?? 0
                  return (
                    <line
                      key={`${i}-${j}`}
                      x1={layer.x} y1={layer.positions[i]}
                      x2={next.x} y2={next.positions[j]}
                      stroke={weightColor(w, maxAbsWeight)}
                      strokeWidth={0.5 + (Math.abs(w) / maxAbsWeight) * 2}
                    />
                  )
                }),
              )}
            </g>
          )
        })}

        {/* Nœuds */}
        {layout.layers.map((layer, layerIndex) => (
          <g
            key={layerIndex}
            onMouseEnter={() => setHoveredLayer(layerIndex)}
            onMouseLeave={() => setHoveredLayer(null)}
          >
            {layer.indices.map((nodeIdx, i) => {
              const label = labelFor(layerIndex, nodeIdx)
              const isInput = layerIndex === 0
              const isOutput = layerIndex === layout.layers.length - 1
              return (
                <g key={i}>
                  <circle
                    cx={layer.x} cy={layer.positions[i]} r={NODE_RADIUS}
                    className="fill-white stroke-slate-400 dark:fill-slate-800 dark:stroke-slate-500"
                    strokeWidth={1.5}
                  />
                  {/* Étiquettes posées à côté (pas au-dessus) des nœuds d'entrée/sortie :
                      avec des couches denses, un espacement vertical au-dessus/dessous
                      ferait chevaucher le texte entre nœuds voisins. */}
                  {label && (isInput || isOutput) && (
                    <text
                      x={isInput ? layer.x - NODE_RADIUS - 6 : layer.x + NODE_RADIUS + 6}
                      y={layer.positions[i]}
                      dominantBaseline="middle"
                      textAnchor={isInput ? 'end' : 'start'}
                      className="fill-slate-600 text-[10px] dark:fill-slate-300"
                    >
                      {String(label).slice(0, 12)}
                    </text>
                  )}
                </g>
              )
            })}
            {layer.shown < layer.size && (
              <text
                x={layer.x} y={layout.height - 12} textAnchor="middle"
                className="fill-slate-400 text-[10px] italic dark:fill-slate-500"
              >
                {layer.size} neurones (affichage limité)
              </text>
            )}
          </g>
        ))}
      </svg>

      <div className="mt-2 flex items-center justify-center gap-4 text-xs text-slate-500 dark:text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-6 rounded" style={{ background: 'rgba(37, 99, 235, 0.75)' }} /> poids positif
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-6 rounded" style={{ background: 'rgba(220, 38, 38, 0.75)' }} /> poids négatif
        </span>
        <span>intensité ∝ |poids|</span>
      </div>
    </div>
  )
}
