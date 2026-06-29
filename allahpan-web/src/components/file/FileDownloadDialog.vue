<template>
  <el-dialog
    v-model="visible"
    title="下载文件"
    width="400px"
    :close-on-click-modal="false"
    :show-close="!downloading"
    destroy-on-close
  >
    <div class="download-body">
      <div class="file-name" :title="fileName">{{ fileName }}</div>
      <el-progress
        :percentage="progress.percent"
        :status="progress.status === 'done' ? 'success' : progress.status === 'error' ? 'exception' : ''"
        :stroke-width="6"
      />
      <div class="download-detail">
        <span>{{ formatSpeed(speed) }}</span>
        <span>{{ formatETA(eta) }}</span>
        <span>{{ formatBytes(loaded) }}/{{ formatBytes(total) }}</span>
      </div>
      <div v-if="progress.status === 'error'" class="error-msg">{{ errorMsg }}</div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { downloadFile } from '@/api/file'
import { SpeedTracker, formatSpeed, formatETA } from '@/utils/transfer'
import { formatBytes } from '@/utils/format'

const visible = ref(false)
const downloading = ref(false)
const fileName = ref('')
const errorMsg = ref('')
const speed = ref(0)
const eta = ref(0)
const loaded = ref(0)
const total = ref(0)
const progress = reactive({ percent: 0, status: '' })

const speedTracker = new SpeedTracker()

const open = (fileId, name, fileSize) => {
  visible.value = true
  downloading.value = true
  fileName.value = name || '文件'
  errorMsg.value = ''
  progress.percent = 0
  progress.status = ''
  speed.value = 0
  eta.value = 0
  loaded.value = 0
  total.value = 0
  speedTracker.reset()

  downloadFile(fileId, name, (evt) => {
    const effectiveTotal = evt.total || fileSize || 0
    if (effectiveTotal > 0) {
      progress.percent = Math.round((evt.loaded / effectiveTotal) * 100)
    }
    loaded.value = evt.loaded
    total.value = effectiveTotal
    speedTracker.update(evt.loaded)
    speed.value = speedTracker.getSpeed()
    const remaining = effectiveTotal - evt.loaded
    eta.value = speedTracker.getETA(remaining)
  })
    .then(() => {
      progress.status = 'done'
      progress.percent = 100
      downloading.value = false
    })
    .catch((err) => {
      progress.status = 'error'
      errorMsg.value = err.message || '下载失败'
      downloading.value = false
    })
}

defineExpose({ open })
</script>

<style scoped>
.download-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ap-text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.download-detail {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--ap-text-sub);
}
.error-msg {
  font-size: 12px;
  color: #f56c6c;
}
</style>
