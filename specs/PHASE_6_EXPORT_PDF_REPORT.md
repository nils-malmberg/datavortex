# Phase 6 : Export PDF Report Avancé

## PDF Report Content

Rapport PDF contenant sélection d'éléments :

### Sections possibles
1. **Couverture** : titre, date, nom fichier
2. **Résumé exécutif** : # lignes, colonnes, types
3. **Statistiques** : stats descriptives par colonne (selectable)
4. **Data Preview** : tableau sample des données
5. **Graphiques** : les plots créés (selectable)
6. **Corrélations** : heatmap corrélations
7. **Métadonnées** : encoding, séparateur, filters appliqués

### UI - Report Builder
- ReportBuilder.jsx : modal/drawer avec checklist
- Checkboxes par section (stat table, plots, etc)
- Sélecteur plots : lister tous les plots créés, cocher les à inclure
- Options : format page (A4, Letter), orientation
- Bouton "Generate PDF"

### Backend
- Route POST /api/report/pdf
- Body : {session_id, sections: ['stats', 'plots', ...], plot_ids: [...]}
- Utilise reportlab ou weasyprint pour générer PDF
- Include plotly graphs comme images
- Return fichier PDF

### Tests
- Generate report avec toutes sections
- Generate report avec sections sélectionnées
- Vérifier PDF contient les bons plots
- Vérifier stats sont correctes
- Export et ouvre dans navigateur