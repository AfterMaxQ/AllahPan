import request from './index'

export function searchFiles({
  keyword,
  fileType,
  minSize,
  maxSize,
  startTime,
  endTime,
  searchScope = 'all',
  sortBy = 'relevance',
  sortOrder = 'desc',
  filterExpression,
  pageNum = 1,
  pageSize = 20,
  signal,
}) {
  const params = { keyword, pageNum, pageSize, searchScope, sortBy, sortOrder }
  if (fileType) params.fileType = fileType
  if (minSize != null) params.minSize = minSize
  if (maxSize != null) params.maxSize = maxSize
  if (startTime) params.startTime = startTime
  if (endTime) params.endTime = endTime
  if (filterExpression?.children?.length) {
    params.filterExpression = JSON.stringify(filterExpression)
  }
  return request.get('/search', { params, signal })
}
