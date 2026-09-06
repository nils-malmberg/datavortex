import axios from 'axios'

// Le proxy Vite (vite.config.js) redirige /api vers http://localhost:8000
const api = axios.create({
  baseURL: '/api',
})

export function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function parseFile(sessionId, separator) {
  return api.post('/parse', { session_id: sessionId, separator })
}

export function getPreview(sessionId) {
  return api.get(`/data/${sessionId}/preview`)
}

export function getStats(sessionId) {
  return api.get(`/stats/${sessionId}`)
}

export function plot1D(sessionId, params) {
  return api.post('/plot/1d', { session_id: sessionId, ...params })
}

export function plot2D(sessionId, params) {
  return api.post('/plot/2d', { session_id: sessionId, ...params })
}

export function plot3D(sessionId, params) {
  return api.post('/plot/3d', { session_id: sessionId, ...params })
}

export function exportPlot(sessionId, kind, params, format, { width = 900, height = 600 } = {}) {
  return api.post(
    '/export/plot',
    { session_id: sessionId, kind, params, format, width, height },
    { responseType: 'blob' },
  )
}

export function applyFilter(sessionId, filter) {
  return api.post(`/data/${sessionId}/filter`, { filter })
}

export function createColumn(sessionId, { name, formula, overwrite = false, previewOnly = false, previewRows = 10 }) {
  return api.post(`/data/${sessionId}/columns`, {
    name,
    formula,
    overwrite,
    preview_only: previewOnly,
    preview_rows: previewRows,
  })
}

export function exportCsv(sessionId, { separator = ',', encoding = 'utf-8', includeFilterComment = true } = {}) {
  return api.post(
    '/export/csv',
    { session_id: sessionId, separator, encoding, include_filter_comment: includeFilterComment },
    { responseType: 'blob' },
  )
}

export function deleteSession(sessionId) {
  return api.delete(`/session/${sessionId}`)
}

export function generateReportPdf(
  sessionId,
  { sections, plots = [], pageFormat = 'A4', orientation = 'portrait', resizePlotsToFit = true },
) {
  return api.post(
    '/report/pdf',
    {
      session_id: sessionId,
      sections,
      plots,
      page_format: pageFormat,
      orientation,
      resize_plots_to_fit: resizePlotsToFit,
    },
    { responseType: 'blob' },
  )
}

export function mergeSessions(sessionIds, mode, keyColumn, leftSuffix = '_x', rightSuffix = '_y') {
  return api.post('/merge', {
    session_ids: sessionIds,
    mode,
    key_column: keyColumn,
    left_suffix: leftSuffix,
    right_suffix: rightSuffix,
  })
}

export function runRegression(sessionId, { features, target, modelType = 'linear', degree = 2 }) {
  return api.post('/ml/regression', {
    session_id: sessionId, features, target, model_type: modelType, degree,
  })
}

export function runClassification(sessionId, { features, target, modelType = 'logistic', params = {} }) {
  return api.post('/ml/classification', {
    session_id: sessionId, features, target, model_type: modelType, params,
  })
}

export function runClustering(sessionId, { features, modelType = 'kmeans', params = {}, colorBy }) {
  return api.post('/ml/clustering', {
    session_id: sessionId, features, model_type: modelType, params, color_by: colorBy,
  })
}

export function runPCA(sessionId, { features, nComponents = 2, method = 'pca', colorBy }) {
  return api.post('/ml/pca', {
    session_id: sessionId, features, n_components: nComponents, method, color_by: colorBy,
  })
}


export default api

// --- Statistiques avancées (Phase 8) -----------------------------------------

export function getAdvancedStats(sessionId, method = 'pearson') {
  return api.get(`/stats/${sessionId}/advanced`, { params: { method } })
}

export function exportStatsTable(sessionId, { table, format, precision = 4 }) {
  return api.post('/stats/export', { session_id: sessionId, table, format, precision }, { responseType: 'blob' })
}

export function plotAdvanced(sessionId, payload) {
  return api.post('/plot/advanced', { session_id: sessionId, ...payload })
}

export function applyAdvancedFilter(sessionId, { filter, invert = false, previewRows = 50, previewMode = 'all' }) {
  return api.post('/filters/apply', {
    session_id: sessionId,
    filter,
    invert,
    preview_rows: previewRows,
    preview_mode: previewMode,
  })
}

export function getRows(sessionId, { offset = 0, limit = 100, sortBy, sortDir = 'asc', search = '', searchColumn, groupBy } = {}) {
  return api.get(`/data/${sessionId}/rows`, {
    params: {
      offset,
      limit,
      sort_by: sortBy || undefined,
      sort_dir: sortDir,
      search: search || '',
      search_column: searchColumn || undefined,
      group_by: groupBy || undefined,
    },
  })
}

export function getColumnStats(sessionId, column) {
  return api.get(`/column/${sessionId}/${encodeURIComponent(column)}/stats`)
}
