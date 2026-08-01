<template>
  <div class="trash-page">
    <div class="page-header">
      <div class="header-top">
        <h2>垃圾站</h2>
        <el-button
          v-if="trashList.length > 0"
          type="danger"
          @click="handleEmptyTrash"
        >
          一键清空
        </el-button>
      </div>
      <p>删除的文件会保留在这里，可以随时恢复</p>
    </div>

    <!-- 批量操作栏 -->
    <div v-if="selectedRows.length > 0" class="batch-bar">
      <span>已选择 {{ selectedRows.length }} 项</span>
      <el-button type="danger" @click="handleBatchDelete">彻底删除选中</el-button>
    </div>

    <el-skeleton :rows="6" animated :loading="loading">
      <template v-if="trashList.length > 0">
        <!-- 桌面端表格 -->
        <div v-if="!isMobile" class="trash-table">
          <el-table
            :data="trashList"
            style="width: 100%"
            @selection-change="handleSelectionChange"
            ref="tableRef"
          >
            <el-table-column type="selection" width="45" />
            <el-table-column label="名称">
              <template #default="{ row }">
                <div class="file-name-cell">
                  <FileIcon
                    :is-folder="row.isFolder === 1"
                    :file-type="row.fileType"
                    :file-name="row.fileName"
                    :size="32"
                  />
                  <span class="file-name ap-file-name" dir="auto" :title="row.fileName">{{ row.fileName }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="110">
              <template #default="{ row }">
                {{ formatBytes(row.fileSize) }}
              </template>
            </el-table-column>
            <el-table-column label="删除时间" width="170">
              <template #default="{ row }">
                {{ formatDate(row.deleteTime) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" align="right">
              <template #default="{ row }">
                <el-button type="primary" size="small" plain @click="handleRestore(row)">恢复</el-button>
                <el-button type="danger" size="small" plain @click="handlePermanentDelete(row)">彻底删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <!-- 移动端卡片列表 -->
          <div v-else class="trash-cards">
          <div v-for="row in trashList" :key="row.id" class="trash-card">
            <FileIcon
              :is-folder="row.isFolder === 1"
              :file-type="row.fileType"
              :file-name="row.fileName"
              :size="40"
            />
            <div class="trash-card-body">
              <span class="file-name ap-file-name" dir="auto" :title="row.fileName">{{ row.fileName }}</span>
              <div class="trash-meta">
                <span>{{ formatBytes(row.fileSize) }}</span>
                <span>{{ formatDate(row.deleteTime) }}</span>
              </div>
            </div>
            <div class="trash-card-actions">
              <el-button type="primary" size="small" plain @click="handleRestore(row)">恢复</el-button>
              <el-button type="danger" size="small" plain @click="handlePermanentDelete(row)">删除</el-button>
            </div>
          </div>
        </div>
      </template>
      <EmptyState
        v-else-if="!loading"
        title="垃圾站是空的"
        description="干干净净，没有需要恢复的文件"
      />
    </el-skeleton>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, onMounted } from 'vue'
import { useResponsive } from '@/composables/useResponsive'
import { getTrashList, restoreFile, permanentDelete, emptyTrash, batchPermanentDelete } from '@/api/file'
import { formatBytes, formatDate } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import FileIcon from '@/components/common/FileIcon.vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const { isMobile } = useResponsive()

const loading = ref(false)
const trashList = ref([])
const selectedRows = ref([])
const tableRef = ref(null)
let trashController = null
let trashRequestId = 0

const fetchTrash = async () => {
  const requestId = ++trashRequestId
  trashController?.abort()
  trashController = new AbortController()
  loading.value = true
  try {
    const result = await getTrashList(1, 50, trashController.signal)
    if (requestId === trashRequestId) {
      trashList.value = result
      selectedRows.value = []
    }
  } catch (e) {
    if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
      console.error('加载垃圾站失败', e)
    }
  } finally {
    if (requestId === trashRequestId) loading.value = false
  }
}

const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const handleRestore = async (file) => {
  try {
    await restoreFile(file.id)
    ElMessage.success('文件已恢复')
    fetchTrash()
  } catch (e) { /* 拦截器统一处理 */ }
}

const handlePermanentDelete = (file) => {
  ElMessageBox.confirm(
    `「${file.fileName}」将被永久删除，无法恢复。确定继续吗？`,
    '不可逆操作',
    { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'error' }
  ).then(async () => {
    try {
      await permanentDelete(file.id)
      ElMessage.success('已永久删除')
      fetchTrash()
    } catch (e) { /* 拦截器统一处理 */ }
  }).catch(() => {})
}

const handleBatchDelete = () => {
  const names = selectedRows.value.map(r => r.fileName).slice(0, 5).join('、')
  const suffix = selectedRows.value.length > 5 ? ` 等 ${selectedRows.value.length} 项` : ''
  ElMessageBox.confirm(
    `「${names}${suffix}」将被永久删除，无法恢复。确定继续吗？`,
    '不可逆操作',
    { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'error' }
  ).then(async () => {
    try {
      const ids = selectedRows.value.map(r => r.id)
      const res = await batchPermanentDelete(ids)
      ElMessage.success(res?.message || `已删除 ${res?.deletedCount || ids.length} 个文件`)
      fetchTrash()
    } catch (e) { /* 拦截器统一处理 */ }
  }).catch(() => {})
}

const handleEmptyTrash = () => {
  ElMessageBox.confirm(
    '垃圾站中所有文件将被永久删除，无法恢复。确定清空吗？',
    '不可逆操作',
    { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'error' }
  ).then(async () => {
    try {
      const res = await emptyTrash()
      ElMessage.success(res?.message || '垃圾站已清空')
      fetchTrash()
    } catch (e) { /* 拦截器统一处理 */ }
  }).catch(() => {})
}

onMounted(fetchTrash)
onBeforeUnmount(() => {
  trashRequestId++
  trashController?.abort()
})
</script>

<style scoped>
.trash-page {
  /* max-width removed for responsive */
}
.page-header {
  margin-bottom: 24px;
}
.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-header h2 {
  margin: 0;
  color: var(--ap-text-main);
  font-size: 20px;
}
.page-header p {
  color: var(--ap-text-sub);
  margin: 0;
  font-size: 14px;
}
.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  margin-bottom: 12px;
  background: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 10px;
  font-size: 14px;
  color: var(--ap-text-main);
}
.trash-table {
  background-color: var(--ap-bg-card);
  border-radius: 14px;
  border: 1px solid var(--ap-border-color);
  overflow: hidden;
}
.file-name {
  font-weight: 500;
  color: var(--ap-text-main);
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
}
.file-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

@media (max-width: 768px) {
  .trash-cards {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .trash-card {
    background: var(--ap-bg-card);
    border: 1px solid var(--ap-border-color);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .trash-card-body {
    min-width: 0;
    flex: 1;
    margin-bottom: 10px;
  }
  .trash-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: var(--ap-text-sub);
    margin-top: 4px;
  }
  .trash-card-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    flex-wrap: wrap;
  }
  .file-name { font-size: 15px; line-height: 1.48; }
  .page-header {
    margin-bottom: 14px;
  }
}
</style>
