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
