<template>
  <div class="favorites-page">
    <div class="page-header">
      <h2>我的收藏</h2>
      <p>记录全家人最喜欢的文件</p>
    </div>

    <el-skeleton :rows="6" animated :loading="loading">
      <div v-if="list.length > 0" class="fav-grid">
        <div v-for="file in list" :key="file.id" class="fav-card">
          <FileIcon
            :is-folder="file.isFolder === 1"
            :file-type="file.fileType"
            :size="48"
          />
          <div class="fav-info">
            <span class="name" @click="handleOpen(file)">{{ file.fileName }}</span>
            <span class="origin-path">{{ file.filePath }}</span>
          </div>
          <el-button
            type="danger"
            circle
            plain
            :icon="StarFilled"
            size="small"
            @click="cancelFavorite(file.id)"
          />
        </div>
      </div>
      <EmptyState
        v-else-if="!loading"
        title="收藏夹空荡荡"
        description="在文件浏览中右键文件，即可添加到收藏"
      />
    </el-skeleton>

    <FilePreviewDialog ref="previewDialogRef" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { StarFilled } from '@element-plus/icons-vue'
import { getFavoriteList, removeFavorite } from '@/api/favorite'
import FileIcon from '@/components/common/FileIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FilePreviewDialog from '@/components/file/FilePreviewDialog.vue'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const list = ref([])
const previewDialogRef = ref(null)

const loadFavorites = async () => {
  loading.value = true
  try {
    list.value = await getFavoriteList()
  } catch (e) {
    console.error('加载收藏失败', e)
  } finally {
    loading.value = false
  }
}

const cancelFavorite = async (fileId) => {
  try {
    await removeFavorite(fileId)
    ElMessage.success('已取消收藏')
    loadFavorites()
  } catch (e) { /* 拦截器统一处理 */ }
}

const handleOpen = (file) => {
  if (file.isFolder !== 1) {
    previewDialogRef.value?.open(file)
  }
}

onMounted(loadFavorites)
</script>

<style scoped>
.favorites-page {
  max-width: 900px;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h2 {
  margin: 0;
  color: var(--ap-text-main);
  font-size: 20px;
}
.page-header p {
  color: var(--ap-text-sub);
  margin: 4px 0 0 0;
  font-size: 14px;
}
.fav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}
.fav-card {
  background-color: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 14px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: box-shadow 0.2s ease;
}
.fav-card:hover {
  box-shadow: 0 4px 12px rgba(61, 50, 38, 0.04);
}
.fav-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.fav-info .name {
  font-weight: 600;
  color: var(--ap-text-main);
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fav-info .name:hover {
  color: var(--el-color-primary);
}
.fav-info .origin-path {
  font-size: 12px;
  color: var(--ap-text-sub);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
