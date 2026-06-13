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
        <span>{{ formatSize(loaded) }}/{{ formatSize(total) }}</span>
      </div>
      <div v-if="progress.status === 'error'" class="error-msg">{{ errorMsg }}</div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { downloadFile } from '@/api/file'

const visible = ref(false)
const downloading = ref(false)
const fileName = ref('')
const errorMsg = ref('')
const speed = ref(0)
const eta = ref(0)
const loaded = ref(0)
const total = ref(0)
const progress = reactive({ percent: 0, status: '' })

// SpeedTracker 内联
let samples = []
let totalBytes = 0

function addSample(bytes) {
  const now = Date.now()
  samples.push({ bytes, timestamp: now })
  if (samples.length > 5) samples.shift()
  totalBytes += bytes
}

function getSpeed() {
  if (samples.length < 2) return 0
  const first = samples[0]
  const last = samples[samples.length - 1]
  const dur = (last.timestamp - first.timestamp) / 1000
  const bytes = samples.slice(1).reduce((s, v) => s + v.bytes, 0)
  return dur > 0 ? bytes / dur : 0
}

function formatSpeed(bps) {
  if (bps >= 1e6) return (bps / 1e6).toFixed(1) + ' MB/s'
  if (bps >= 1e3) return (bps / 1e3).toFixed(0) + ' KB/s'
  return bps.toFixed(0) + ' B/s'
}

function formatETA(seconds) {
  if (!isFinite(seconds) || seconds <= 0) return '--'
  if (seconds < 60) return Math.ceil(seconds) + 's'
  return Math.floor(seconds / 60) + 'm ' + Math.ceil(seconds % 60) + 's'
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const open = (fileId, name) => {
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
  samples = []
  totalBytes = 0

  downloadFile(fileId, name, (evt) => {
    progress.percent = evt.percent
    loaded.value = evt.loaded
    total.value = evt.total
    addSample(evt.loaded - totalBytes)
    totalBytes = evt.loaded
    speed.value = getSpeed()
    const remaining = evt.total - evt.loaded
    eta.value = speed.value > 0 ? remaining / speed.value : Infinity
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
