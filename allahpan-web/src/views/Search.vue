<template>
  <div class="search-page">
    <div class="page-header">
      <h2>搜索结果</h2>
      <p v-if="keyword">找到与「<strong>{{ keyword }}</strong>」相关的结果，共 {{ total }} 项</p>
    </div>

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
        description="换个关键词试试，或文件可能尚未被 AI 识别"
      />
    </el-skeleton>

    <FilePreviewDialog ref="previewDialogRef" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { searchFiles } from '@/api/search'
import { getFileDetail } from '@/api/file'
import SearchResultItem from '@/components/search/SearchResultItem.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FilePreviewDialog from '@/components/file/FilePreviewDialog.vue'

const route = useRoute()
const loading = ref(false)
const results = ref([])
const total = ref(0)
const keyword = ref('')
const previewDialogRef = ref(null)

const executeSearch = async () => {
  const q = route.query.q
  if (!q) return
  keyword.value = q
  loading.value = true
  try {
    const res = await searchFiles({ keyword: q, pageSize: 50 })
    results.value = res.list || []
    total.value = res.totalCount || 0
  } catch (e) {
    console.error('搜索失败', e)
    // 认证错误已由拦截器处理并跳转登录页，不重复提示
    const msg = e.message || ''
    if (msg !== '未授权' && !msg.includes('未登录') && !msg.includes('token')) {
      ElMessage.error('搜索服务暂不可用，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}

watch(() => route.query.q, executeSearch)
onMounted(executeSearch)

const openDetail = async (fileId) => {
  try {
    const detail = await getFileDetail(fileId)
    previewDialogRef.value?.open(detail)
  } catch (e) {
    console.error('获取文件详情失败', e)
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0 0 8px 0;
  color: var(--ap-text-main);
  font-size: 20px;
}
.page-header p {
  color: var(--ap-text-sub);
  font-size: 14px;
  margin: 0;
}
.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 768px) {
  .page-header {
    margin-bottom: 14px;
  }
  .result-list {
    gap: 8px;
  }
}
</style>
