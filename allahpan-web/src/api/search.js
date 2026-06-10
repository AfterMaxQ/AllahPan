import request from './index'

export function searchFiles({ keyword, fileType, pageNum = 1, pageSize = 20 }) {
  const params = { keyword, pageNum, pageSize }
  if (fileType) params.fileType = fileType
  return request.get('/search', { params })
}
