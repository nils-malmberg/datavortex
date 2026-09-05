export function extractFilename(contentDisposition, fallback) {
  const match = /filename="?([^"]+)"?/.exec(contentDisposition || '')
  return match ? match[1] : fallback
}

export function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
