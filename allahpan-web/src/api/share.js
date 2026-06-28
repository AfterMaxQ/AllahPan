import request from './index'
import { requestBlob, saveBlob } from './file'

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
  const blob = await requestBlob(`/share/${code}/download`, onProgress, signal)
  saveBlob(blob, fileName)
  return blob
}
