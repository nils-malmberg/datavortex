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

export default api
