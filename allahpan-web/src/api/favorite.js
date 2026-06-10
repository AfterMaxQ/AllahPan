import request from './index'

export function addFavorite(fileId) {
  return request.post(`/favorite/${fileId}`)
}

export function removeFavorite(fileId) {
  return request.delete(`/favorite/${fileId}`)
}

export function checkFavorite(fileId) {
  return request.get(`/favorite/check/${fileId}`)
}

export function getFavoriteList(pageNum = 1, pageSize = 50) {
  return request.get('/favorite/list', { params: { pageNum, pageSize } })
}
