import request from './index'

export function createShareLink(fileId, expireHours = 24) {
  return request.post(`/share/${fileId}`, null, { params: { expireHours } })
}

export function getSharedContent(code) {
  return request.get(`/share/${code}`)
}

export function deleteShareLink(code) {
  return request.delete(`/share/${code}`)
}

export async function downloadSharedFile(code, fileName, onProgress, signal) {
  if (signal?.aborted) throw new DOMException('下载已取消', 'AbortError')
  const a = document.createElement('a')
  a.href = `/api/share/${encodeURIComponent(code)}/download`
  a.download = fileName || 'download'
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  onProgress?.({ percent: 100, loaded: 0, total: 0, handedOff: true })
  return { handedOff: true }
}
