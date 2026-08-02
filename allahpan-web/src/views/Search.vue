<template>
  <div class="search-page">
    <div class="page-header">
      <div class="page-title-row">
        <div>
          <h2>搜索结果</h2>
          <p v-if="keyword">
            找到与「<strong>{{ keyword }}</strong>」相关的结果，共 {{ total }} 项
          </p>
        </div>
        <span v-if="keyword && loading" class="loading-label">正在搜索…</span>
      </div>
    </div>

    <SearchFilterBar
      v-if="keyword"
      :filters="filters"
      :total="total"
      :type-aggregations="typeAggregations"
      @change="handleFilterChange"
      @reset="resetFilters"
    />

    <el-skeleton :rows="6" animated :loading="loading">
      <div v-if="results.length > 0" class="result-list">
        <SearchResultItem
          v-for="item in results"
          :key="item.fileId"
          :item="item"
          @click="openDetail(item.fileId)"
        />
      </div>
      <EmptyState
        v-else-if="!loading && keyword"
        title="未找到相关内容"
        description="换个关键词试试，或调整筛选条件"
      />
    </el-skeleton>

    <el-pagination
      v-if="total > pageSize"
      class="search-pagination"
      background
      layout="prev, pager, next, total"
      :current-page="pageNum"
      :page-size="pageSize"
      :total="total"
      @current-change="handlePageChange"
    />

    <FilePreviewDialog ref="previewDialogRef" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { searchFiles } from '@/api/search'
import { getFileDetail } from '@/api/file'
import SearchFilterBar from '@/components/search/SearchFilterBar.vue'
import SearchResultItem from '@/components/search/SearchResultItem.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FilePreviewDialog from '@/components/file/FilePreviewDialog.vue'

const route = useRoute()
const router = useRouter()

const pageSize = 20
const loading = ref(false)
const results = ref([])
const total = ref(0)
const keyword = ref('')
const pageNum = ref(1)
const typeAggregations = ref([])
const filters = ref(createDefaultFilters())
const previewDialogRef = ref(null)

let expressionId = 0
let searchController = null
let searchRequestId = 0

function createDefaultFilters() {
  return {
    fileType: '',
    minSize: null,
    maxSize: null,
    startTime: '',
    endTime: '',
    timePreset: 'all',
    sizePreset: 'all',
    searchScope: 'all',
    sortBy: 'relevance',
    sortOrder: 'desc',
    filterExpression: null,
  }
}

const firstQueryValue = (value) => Array.isArray(value) ? value[0] : value
const queryText = (value) => {
  const text = firstQueryValue(value)
  return text == null ? '' : String(text)
}

const parseNumber = (value) => {
  const text = queryText(value)
  if (!text) return null
  const number = Number(text)
  return Number.isFinite(number) && number >= 0 ? number : null
}

const withExpressionIds = (group) => {
  if (!group || group.type !== 'group' || !Array.isArray(group.children)) return null
  return {
    type: 'group',
    id: `route-expression-${Date.now()}-${++expressionId}`,
    logic: group.logic === 'OR' ? 'OR' : 'AND',
    children: group.children.map((child) => {
      if (child?.type === 'group' || Array.isArray(child?.children)) return withExpressionIds(child)
      return {
        type: 'condition',
        id: `route-expression-${Date.now()}-${++expressionId}`,
        field: String(child?.field || 'fileName'),
        operator: String(child?.operator || 'contains'),
        value: child?.value ?? '',
      }
    }).filter(Boolean),
  }
}

const parseExpression = (value) => {
  const raw = queryText(value)
  if (!raw) return null
  try {
    return withExpressionIds(JSON.parse(raw))
  } catch {
    return null
  }
}

const detectSizePreset = (minSize, maxSize) => {
  const MB = 1024 * 1024
  const GB = 1024 * MB
  if (minSize == null && maxSize == null) return 'all'
  if (minSize == null && maxSize === 10 * MB - 1) return 'lt10m'
  if (minSize === 10 * MB && maxSize === 100 * MB - 1) return '10m100m'
  if (minSize === 100 * MB && maxSize === GB - 1) return '100m1g'
  if (minSize === GB && maxSize == null) return 'gt1g'
  return 'all'
}

const parseFilters = (query) => {
  const minSize = parseNumber(query.minSize)
  const maxSize = parseNumber(query.maxSize)
  return {
    fileType: ['IMAGE', 'VIDEO', 'DOCUMENT', 'OTHER'].includes(queryText(query.fileType).toUpperCase())
      ? queryText(query.fileType).toUpperCase() : '',
    minSize,
    maxSize,
    startTime: queryText(query.startTime),
    endTime: queryText(query.endTime),
    timePreset: ['today', '7d', '30d', '1y', 'custom'].includes(queryText(query.timePreset))
      ? queryText(query.timePreset)
      : (query.startTime || query.endTime ? 'custom' : 'all'),
    sizePreset: detectSizePreset(minSize, maxSize),
    searchScope: ['all', 'name', 'content'].includes(queryText(query.searchScope))
      ? queryText(query.searchScope) : 'all',
    sortBy: ['relevance', 'fileName', 'fileSize', 'createTime'].includes(queryText(query.sortBy))
      ? queryText(query.sortBy) : 'relevance',
    sortOrder: ['asc', 'desc'].includes(queryText(query.sortOrder))
      ? queryText(query.sortOrder) : 'desc',
    filterExpression: parseExpression(query.filterExpression),
  }
}

const stripExpression = (group) => {
  if (!group?.children?.length) return null
  const children = group.children.map((child) => {
    if (child.type === 'group') {
      const nested = stripExpression(child)
      return nested ? { type: 'group', logic: child.logic === 'OR' ? 'OR' : 'AND', children: nested.children } : null
    }
    const hasValue = child.value !== '' && child.value != null
      && (!Array.isArray(child.value) || (child.value.length > 0
        && child.value.every((value) => value !== '' && value != null)))
    if (!hasValue) return null
    return { type: 'condition', field: child.field, operator: child.operator, value: child.value }
  }).filter(Boolean)
  return children.length
    ? { type: 'group', logic: group.logic === 'OR' ? 'OR' : 'AND', children }
    : null
}

const localDateRange = (preset) => {
  if (!preset || preset === 'all' || preset === 'custom') return { startTime: '', endTime: '' }
  const end = new Date()
  const start = new Date(end)
  if (preset === 'today') {
    start.setHours(0, 0, 0, 0)
  } else if (preset === '7d') {
    start.setDate(start.getDate() - 7)
  } else if (preset === '30d') {
    start.setDate(start.getDate() - 30)
  } else if (preset === '1y') {
    start.setFullYear(start.getFullYear() - 1)
  }
  return { startTime: start.toISOString(), endTime: end.toISOString() }
}

const normalizeForQuery = (input) => {
  const next = { ...createDefaultFilters(), ...input }
  const timeRange = next.timePreset && next.timePreset !== 'custom'
    ? localDateRange(next.timePreset)
    : { startTime: next.startTime || '', endTime: next.endTime || '' }
  const expression = stripExpression(next.filterExpression)
  return { ...next, ...timeRange, filterExpression: expression }
}

const buildQuery = (q, inputFilters, nextPage = 1) => {
  const normalized = normalizeForQuery(inputFilters)
  const query = { q, pageNum: String(nextPage) }
  if (normalized.fileType) query.fileType = normalized.fileType
  if (normalized.minSize != null) query.minSize = String(normalized.minSize)
  if (normalized.maxSize != null) query.maxSize = String(normalized.maxSize)
  if (normalized.startTime) query.startTime = normalized.startTime
  if (normalized.endTime) query.endTime = normalized.endTime
  if (normalized.timePreset && normalized.timePreset !== 'all') query.timePreset = normalized.timePreset
  if (normalized.searchScope !== 'all') query.searchScope = normalized.searchScope
  if (normalized.sortBy !== 'relevance' || normalized.sortOrder !== 'desc') {
    query.sortBy = normalized.sortBy
    query.sortOrder = normalized.sortOrder
  }
  if (normalized.filterExpression) query.filterExpression = JSON.stringify(normalized.filterExpression)
  return query
}

const executeSearch = async () => {
  const q = queryText(route.query.q).trim()
  keyword.value = q
  filters.value = parseFilters(route.query)
  pageNum.value = Math.max(1, Number(queryText(route.query.pageNum)) || 1)

  if (!q) {
    searchController?.abort()
    results.value = []
    typeAggregations.value = []
    total.value = 0
    loading.value = false
    return
  }

  const requestId = ++searchRequestId
  searchController?.abort()
  searchController = new AbortController()
  loading.value = true
  try {
    const res = await searchFiles({
      keyword: q,
      ...normalizeForQuery(filters.value),
      pageNum: pageNum.value,
      pageSize,
      signal: searchController.signal,
    })
    if (requestId !== searchRequestId) return
    results.value = res.list || []
    total.value = Number(res.totalCount || 0)
    typeAggregations.value = res.aggregations?.fileTypes || []
  } catch (e) {
    if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
      console.error('搜索失败', e)
      const msg = e.message || ''
      if (msg !== '未授权' && !msg.includes('未登录') && !msg.includes('token')) {
        ElMessage.error(msg.includes('筛选') ? msg : '搜索服务暂不可用，请稍后重试')
      }
    }
  } finally {
    if (requestId === searchRequestId) loading.value = false
  }
}

const navigateWithFilters = (nextFilters, nextPage = 1) => {
  const q = queryText(route.query.q).trim()
  if (!q) return
  router.push({ path: '/search', query: buildQuery(q, nextFilters, nextPage) })
}

const handleFilterChange = (nextFilters) => navigateWithFilters(nextFilters, 1)

const resetFilters = () => navigateWithFilters(createDefaultFilters(), 1)

const handlePageChange = (page) => navigateWithFilters(filters.value, page)

const openDetail = async (fileId) => {
  try {
    const detail = await getFileDetail(fileId)
    previewDialogRef.value?.open(detail)
  } catch (e) {
    console.error('获取文件详情失败', e)
  }
}

watch(() => route.fullPath, executeSearch, { immediate: true })
onBeforeUnmount(() => {
  searchRequestId++
  searchController?.abort()
})
</script>

<style scoped>
.page-header { margin-bottom: 14px; }
.page-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.page-header h2 { margin: 0 0 8px; color: var(--ap-text-main); font-size: 20px; }
.page-header p { margin: 0; color: var(--ap-text-sub); font-size: 14px; }
.loading-label { flex: 0 0 auto; color: var(--el-color-primary-dark-2); font-size: 12px; }
.result-list { display: flex; flex-direction: column; gap: 12px; }
.search-pagination { margin-top: 18px; justify-content: center; }

@media (max-width: 768px) {
  .page-header { margin-bottom: 10px; }
  .page-header h2 { margin-bottom: 5px; font-size: 18px; }
  .page-header p { font-size: 12px; line-height: 1.5; }
  .result-list { gap: 8px; }
  .search-pagination { justify-content: flex-start; overflow-x: auto; padding-bottom: 4px; }
}
</style>
