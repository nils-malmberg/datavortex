import { useEffect, useState } from 'react'
import { getDetailedProfile } from '../api/client'
import ProfileColumnsTab from './profile/ProfileColumnsTab'
import ProfileQualityTab from './profile/ProfileQualityTab'
import ProfileAnomaliesTab from './profile/ProfileAnomaliesTab'
import ProfileSuggestionsTab from './profile/ProfileSuggestionsTab'
import { Badge, ErrorBox, Loading, Segmented, SliderField } from './ui/common'

/**
 * Profilage détaillé : ce qu'il faut savoir sur un jeu de données avant de
 * l'analyser — contenu colonne par colonne, qualité mesurée, anomalies, et
 * les corrections à envisager.
 */
const TABS = [
  { value: 'profile', label: 'Profil' },
  { value: 'quality', label: 'Qualité' },
  { value: 'anomalies', label: 'Anomalies' },
  { value: 'suggestions', label: 'Suggestions' },
]

export default function DataProfile({ sessionId, refreshKey }) {
  const [tab, setTab] = useState('quality')
  const [precision, setPrecision] = useState(3)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getDetailedProfile(sessionId)
      .then(({ data: payload }) => !cancelled && setData(payload))
      .catch((err) =>
        !cancelled && setError(err?.response?.data?.error?.message || 'Impossible de profiler ce jeu de données.'),
      )
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [sessionId, refreshKey])

  if (loading) return <Loading>Analyse du jeu de données…</Loading>
  if (error) return <ErrorBox>{error}</ErrorBox>
  if (!data) return null

  const highPriority = data.suggestions.filter((s) => s.priority === 'haute').length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented options={TABS} value={tab} onChange={setTab} ariaLabel="Section du profilage" />
          {data.filtered && <Badge tone="blue">données filtrées</Badge>}
          {highPriority > 0 && <Badge tone="red">{highPriority} point(s) à corriger en priorité</Badge>}
        </div>
        <SliderField
          label="Précision"
          value={precision}
          onChange={setPrecision}
          min={0}
          max={6}
          format={(v) => `${v} déc.`}
        />
      </div>

      {tab === 'profile' && <ProfileColumnsTab profile={data.profile} precision={precision} />}
      {tab === 'quality' && (
        <ProfileQualityTab quality={data.quality} duplicates={data.duplicates} missing={data.missing} />
      )}
      {tab === 'anomalies' && <ProfileAnomaliesTab anomalies={data.anomalies} precision={precision} />}
      {tab === 'suggestions' && <ProfileSuggestionsTab suggestions={data.suggestions} />}
    </div>
  )
}
