# Phase 5 : Dark Mode & Multi-fichiers

## Dark Mode

### Frontend
- TailwindCSS dark mode (déjà dans tailwind.config.js généralement)
- Toggle button pour switch light/dark dans header
- Persist choix dans localStorage
- CSS variables pour couleurs (light/dark)
- App.jsx: wrapper avec classe `dark`
- Tous les composants: utiliser `dark:bg-gray-900` `dark:text-white` etc

### Backend
- Aucun changement nécessaire

### Colours palette
- Light: bg-white, text-gray-900, borders-gray-200
- Dark: bg-gray-950, text-gray-50, borders-gray-800

---

## Multi-fichiers avec Tabs

### Frontend
- TabManager.jsx : gère session_ids multiples
- Chaque onglet = une session_id unique
- Peut switcher entre tabs
- Bouton "+" pour ajouter tab
- Bouton "X" pour fermer tab
- Active tab en highlight

- Dashboard.jsx modifié : accepte session_id en paramètre
- Tous les appels API incluent session_id

### Backend
- SessionManager : dict {session_id -> {data, stats, filters, columns}}
- Limite sessions (ex: 10 max par navigateur)
- Auto-cleanup sessions inactives (>1h)
- Rien de complexe, session_id déjà utilisé

### Tests
- Upload 2 fichiers différents dans 2 tabs
- Filtrer dans tab 1, vérifier tab 2 inchangé
- Stats différentes par tab
- Créer colonnes différentes par tab
- Exporter chaque tab séparément