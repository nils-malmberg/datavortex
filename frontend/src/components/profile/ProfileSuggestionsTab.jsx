import { Badge, EmptyState, Panel } from '../ui/common'

/** Onglet « Suggestions » : actions de nettoyage, classées par priorité. */
const PRIORITY = {
  haute: { tone: 'red', label: 'Priorité haute' },
  moyenne: { tone: 'amber', label: 'Priorité moyenne' },
  basse: { tone: 'blue', label: 'À examiner' },
  info: { tone: 'green', label: 'Information' },
}

export default function ProfileSuggestionsTab({ suggestions }) {
  if (!suggestions || suggestions.length === 0) {
    return <EmptyState>Aucune suggestion : le jeu de données ne présente pas de défaut structurel.</EmptyState>
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Ces suggestions sont déduites des contrôles de qualité et d&apos;anomalies. Elles décrivent ce qui a été
        constaté et l&apos;action correspondante — le choix de l&apos;appliquer reste le vôtre, car il dépend de ce
        que représentent réellement vos données.
      </p>
      {suggestions.map((item, i) => {
        const priority = PRIORITY[item.priority] || PRIORITY.info
        return (
          <Panel key={i} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={priority.tone}>{priority.label}</Badge>
              <h4 className="font-semibold text-slate-800 dark:text-slate-100">{item.title}</h4>
              {item.columns.map((c) => (
                <Badge key={c} tone="slate">
                  {c}
                </Badge>
              ))}
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-300">{item.detail}</p>
            <p className="text-sm font-medium text-blue-700 dark:text-blue-300">→ {item.action}</p>
          </Panel>
        )
      })}
    </div>
  )
}
