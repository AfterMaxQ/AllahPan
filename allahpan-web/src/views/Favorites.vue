<template>
  <div class="favorites-page">
    <div class="page-header">
      <h2>我的收藏</h2>
      <p>记录全家人最喜欢的文件</p>
    </div>

    <el-skeleton :rows="6" animated :loading="loading">
      <div v-if="list.length > 0" class="fav-grid">
        <div v-for="file in list" :key="file.id" class="fav-card" @click="handleOpen(file)">
          <div class="preview-area">
            <FileIcon
              :is-folder="file.isFolder === 1"
              :file-type="file.fileType"
              :file-name="file.fileName"
              :thumb-url="thumbUrl(file)"
              :size="isMobile ? 52 : 64"
            />
            <el-button
              class="remove-btn"
              type="danger"
              circle
              plain
              :icon="StarFilled"
              size="small"
              @click.stop="cancelFavorite(file.id)"
            />
          </div>
          <div class="info-area">
            <span class="file-name ap-file-name" dir="auto" :title="file.fileName">{{ file.fileName }}</span>
            <span class="origin-path" :title="file.filePath">{{ file.filePath }}</span>
            <span v-if="file.isFolder !== 1" class="file-size">{{ formatBytes(file.fileSize) }}</span>
          </div>
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
import { useResponsive } from '@/composables/useResponsive'
import { getFavoriteList, removeFavorite } from '@/api/favorite'
import FileIcon from '@/components/common/FileIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FilePreviewDialog from '@/components/file/FilePreviewDialog.vue'
import { formatBytes } from '@/utils/format'
import { ElMessage } from 'element-plus'

const { isMobile } = useResponsive()

const loading = ref(false)
const list = ref([])
const previewDialogRef = ref(null)

const thumbUrl = (file) => {
  if (file.thumbnailKey) {
    return `/api/file/${file.id}/thumbnail`
  }
  return ''
}

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
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: clamp(12px, 1.5vw, 18px);
}
.fav-card {
  background-color: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 0.2s ease;
}
.fav-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(61, 50, 38, 0.06);
}
.preview-area {
  height: 120px;
  background-color: var(--ap-bg-sidebar);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.remove-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}
.fav-card:hover .remove-btn {
  opacity: 1;
}
.info-area {
  padding: 12px;
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.file-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ap-text-main);
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
}
.origin-path {
  font-size: 12px;
  color: var(--ap-text-sub);
  margin-top: 4px;
  line-height: 1.4;
  overflow-wrap: anywhere;
  white-space: normal;
}
.file-size {
  font-size: 11px;
  color: var(--ap-text-sub);
  margin-top: 4px;
}

@media (max-width: 768px) {
  .fav-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .page-header {
    margin-bottom: 14px;
  }
  .fav-card .remove-btn {
    opacity: 1;
  }
  .preview-area { height: 94px; }
  .info-area { padding: 10px; }
  .file-name { font-size: 15px; line-height: 1.48; }
}
</style>
