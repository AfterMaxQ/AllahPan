<template>
  <el-dialog
    v-model="visible"
    :title="file?.fileName"
    width="75%"
    top="5vh"
    destroy-on-close
  >
    <div class="preview-body" v-loading="loading">
      <!-- 图片预览 -->
      <div v-if="file?.fileType === 'IMAGE'" class="preview-center">
        <el-image
          :src="mediaUrl"
          fit="contain"
          class="preview-img"
          :preview-src-list="[mediaUrl]"
        />
      </div>

      <!-- 视频预览 -->
      <div v-else-if="file?.fileType === 'VIDEO'" class="preview-center">
        <video :src="mediaUrl" controls autoplay class="preview-video" />
      </div>

      <!-- 文档预览：已提取文字时直接展示文本内容 -->
      <div v-else-if="file?.fileType === 'DOCUMENT' && ocrText" class="preview-doc" style="flex-direction: column; align-items: stretch; width: 100%; padding: 0;">
        <div class="doc-text-preview">
          <div class="doc-text-header">
            <el-icon size="18" color="#C4946B"><Cpu /></el-icon>
            <span>文本内容</span>
          </div>
          <div class="doc-text-body">{{ ocrText }}</div>
        </div>
        <div class="doc-text-actions">
          <p>{{ file?.fileName }} ({{ formatBytes(file?.fileSize) }})</p>
          <el-button type="primary" @click="triggerDownload">下载到本地查看</el-button>
        </div>
      </div>

      <!-- 文档/其他 -->
      <div v-else class="preview-doc">
        <div class="doc-icon-section">
          <el-icon size="80" color="#8B7E6E"><Document /></el-icon>
          <h3>该格式暂不支持在线预览</h3>
          <p>{{ file?.fileName }} ({{ formatBytes(file?.fileSize) }})</p>
          <el-button type="primary" @click="triggerDownload">下载到本地查看</el-button>
        </div>
      </div>

      <!-- OCR / AI 识别文字（可折叠，仅 IMAGE 等非 DOCUMENT 文件显示） -->
      <div v-if="ocrText && file?.fileType !== 'DOCUMENT'" class="ocr-section">
        <div class="ocr-header" @click="ocrExpanded = !ocrExpanded">
          <el-icon color="#C4946B"><Cpu /></el-icon>
          <span>图片内容</span>
          <el-icon class="ocr-arrow" :class="{ expanded: ocrExpanded }"><ArrowRight /></el-icon>
        </div>
        <div v-show="ocrExpanded" class="ocr-content">{{ ocrText }}</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { Document, Cpu, ArrowRight } from '@element-plus/icons-vue'
import { getFileDetail, getStreamUrl, getDownloadUrl } from '@/api/file'
import { formatBytes } from '@/utils/format'

const visible = ref(false)
const loading = ref(false)
const file = ref(null)
const mediaUrl = ref('')
const ocrText = ref('')
const ocrExpanded = ref(false)

const open = async (targetFile) => {
  file.value = targetFile
  visible.value = true
  loading.value = true
  ocrText.value = ''
  ocrExpanded.value = false
  mediaUrl.value = ''

  try {
    const detail = await getFileDetail(targetFile.id)
    if (detail.processStatus >= 2) {
      ocrText.value = detail.originText || ''
    }

    if (detail.fileType === 'IMAGE' || detail.fileType === 'VIDEO') {
      mediaUrl.value = getStreamUrl(targetFile.id)
    }
  } catch (e) {
    console.error('加载预览失败', e)
  } finally {
    loading.value = false
  }
}

const triggerDownload = async () => {
  try {
    const res = await getDownloadUrl(file.value.id)
    window.open(res.downloadUrl, '_blank')
  } catch (e) {
    console.error('下载失败', e)
  }
}

defineExpose({ open })
</script>

<style scoped>
.preview-body {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.preview-center {
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #1e1e1e;
  border-radius: 12px;
  overflow: hidden;
  padding: 12px;
  max-height: 60vh;
}
.preview-img {
  max-width: 100%;
  max-height: 55vh;
}
.preview-video {
  width: 100%;
  max-height: 55vh;
  outline: none;
}
.preview-doc {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.doc-icon-section {
  text-align: center;
}
.doc-icon-section h3 {
  margin: 16px 0 8px 0;
  color: var(--ap-text-main);
}
.doc-icon-section p {
  color: var(--ap-text-sub);
  margin-bottom: 24px;
}
.ocr-section {
  background-color: var(--ap-bg-sidebar);
  border-radius: 10px;
  padding: 12px 16px;
  border-left: 4px solid var(--el-color-primary);
}
.ocr-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 8px;
  cursor: pointer;
  user-select: none;
}
.ocr-arrow {
  margin-left: auto;
  transition: transform 0.25s;
}
.ocr-arrow.expanded {
  transform: rotate(90deg);
}
.ocr-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--ap-text-main);
  max-height: 120px;
  overflow-y: auto;
}
.doc-text-preview {
  background-color: var(--ap-bg-sidebar);
  border-radius: 10px;
  border-left: 4px solid var(--el-color-primary);
  overflow: hidden;
}
.doc-text-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-weight: 600;
  font-size: 13px;
  color: #C4946B;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.doc-text-body {
  padding: 16px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--ap-text-main);
  max-height: 50vh;
  overflow-y: auto;
}
.doc-text-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}
.doc-text-actions p {
  color: var(--ap-text-sub);
  font-size: 13px;
  margin: 0;
}
</style>
