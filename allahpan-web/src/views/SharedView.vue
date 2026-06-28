<template>
  <div class="share-landing">
    <div class="card" v-loading="loading">
      <div class="logo">
        <el-icon size="28" color="var(--el-color-primary)"><Share /></el-icon>
        <span>AllahPan 共享</span>
      </div>

      <template v-if="expired">
        <EmptyState
          title="链接已失效"
          description="该分享链接可能已过期，或已被分享者取消"
        />
      </template>

      <template v-else-if="errorMessage">
        <EmptyState
          title="加载失败"
          :description="errorMessage"
        />
      </template>

      <template v-else-if="sharedItem">
        <div class="share-info">
          <div class="preview-block">
            <FileIcon
              :is-folder="false"
              :file-type="sharedItem.fileType"
              :size="80"
            />
          </div>
          <h3>{{ sharedItem.fileName }}</h3>
          <p class="meta">
            大小：{{ formatBytes(sharedItem.fileSize) }}
            <template v-if="sharedItem.createTime">
              &nbsp;|&nbsp; {{ formatDate(sharedItem.createTime) }}
            </template>
          </p>
          <el-button type="primary" size="large" class="dl-btn"
            :loading="downloading" :disabled="downloading"
            @click="handleDownload">
            {{ downloading ? '下载中...' : '下载文件' }}
          </el-button>
          <div v-if="downloading" class="download-hint">
            <el-progress :percentage="100" :indeterminate="true" :stroke-width="4" :duration="3" />
            <p>正在准备下载，请稍候...</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Share } from '@element-plus/icons-vue'
import { getSharedContent } from '@/api/share'
import { formatBytes, formatDate } from '@/utils/format'
import FileIcon from '@/components/common/FileIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const route = useRoute()
const loading = ref(false)
const expired = ref(false)
const sharedItem = ref(null)

const errorMessage = ref('')
const downloading = ref(false)

const loadShare = async () => {
  const code = route.params.code
  loading.value = true
  try {
    sharedItem.value = await getSharedContent(code)
  } catch (err) {
    const status = err?.response?.status
    if (status === 404 || err?.data?.message?.includes('过期') || err?.data?.message?.includes('不存在')) {
      expired.value = true
    } else {
      errorMessage.value = status ? `服务器错误 (${status})` : '网络连接失败，请稍后重试'
    }
    console.error('加载分享失败', err)
  } finally {
    loading.value = false
  }
}

const handleDownload = () => {
  if (downloading.value) return
  downloading.value = true
  if (sharedItem.value?.downloadUrl) {
    const a = document.createElement('a')
    a.href = sharedItem.value.downloadUrl
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }
  setTimeout(() => { downloading.value = false }, 3000)
}

onMounted(loadShare)
</script>

<style scoped>
.share-landing {
  background-color: var(--ap-bg-page);
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.card {
  background-color: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 20px;
  box-shadow: 0 12px 32px rgba(61, 50, 38, 0.05);
  padding: 40px;
  width: 420px;
  text-align: center;
}
.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-primary);
  margin-bottom: 24px;
}
.share-info {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.preview-block {
  margin-bottom: 16px;
}
.share-info h3 {
  margin: 0 0 8px 0;
  color: var(--ap-text-main);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta {
  font-size: 12px;
  color: var(--ap-text-sub);
  margin: 0 0 24px 0;
}
.dl-btn {
  width: 100%;
}
.download-hint {
  margin-top: 16px;
}
.download-hint p {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: var(--ap-text-sub);
}
</style>
