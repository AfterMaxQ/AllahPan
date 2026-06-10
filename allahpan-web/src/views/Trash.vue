<template>
  <div class="trash-page">
    <div class="page-header">
      <h2>垃圾站</h2>
      <p>删除的文件会保留在这里，可以随时恢复</p>
    </div>

    <el-skeleton :rows="6" animated :loading="loading">
      <div v-if="trashList.length > 0" class="trash-table">
        <el-table :data="trashList" style="width: 100%">
          <el-table-column label="名称">
            <template #default="{ row }">
              <span class="file-name">{{ row.fileName }}</span>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="110">
            <template #default="{ row }">
              {{ row.isFolder === 1 ? '-' : formatBytes(row.fileSize) }}
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
      <EmptyState
        v-else-if="!loading"
        title="垃圾站是空的"
        description="干干净净，没有需要恢复的文件"
      />
    </el-skeleton>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTrashList, restoreFile, permanentDelete } from '@/api/file'
import { formatBytes, formatDate } from '@/utils/format'
import EmptyState from '@/components/common/EmptyState.vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const trashList = ref([])

const fetchTrash = async () => {
  loading.value = true
  try {
    trashList.value = await getTrashList()
  } catch (e) {
    console.error('加载垃圾站失败', e)
  } finally {
    loading.value = false
  }
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

onMounted(fetchTrash)
</script>

<style scoped>
.trash-page {
  max-width: 900px;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0 0 4px 0;
  color: var(--ap-text-main);
  font-size: 20px;
}
.page-header p {
  color: var(--ap-text-sub);
  margin: 0;
  font-size: 14px;
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
}
</style>
