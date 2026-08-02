import request from './index'

/**
 * Rebuild the Elasticsearch file index from the current database records.
 * The backend restricts this operation to the initial administrator.
 */
export function rebuildSearchIndex() {
  return request.post('/search/rebuild-index', null, {
    timeout: 300000,
  })
}
