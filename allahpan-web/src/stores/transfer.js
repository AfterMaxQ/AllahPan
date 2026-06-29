import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { uploadTransferFile } from '@/composables/useChunkUpload'
import { downloadFileBlob, saveBlob } from '@/api/file'
import { isRetryableUploadError } from '@/api/chunkUpload'
import { SpeedTracker } from '@/utils/transfer'
import { useFileStore } from '@/stores/file'

const MAX_UPLOADS = 3
const MAX_DOWNLOADS = 3
const MAX_UPLOAD_AUTO_RETRIES = 2

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function createId(prefix) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function normalizeError(error, fallback) {
  if (error?.name === 'CanceledError' || error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') {
    return '已取消'
  }
  const status = error?.response?.status
  if (status === 524 || status === 504) return '网络超时，请检查网络后重试'
  if (status === 502 || status === 503) return '服务暂时不可用，请稍后重试'
  return error?.response?.data?.message || error?.message || fallback
}

function createTask(type, payload) {
  return {
    id: createId(type),
    type,
    name: payload.name,
    file: payload.file,
    fileId: payload.fileId,
    parentId: payload.parentId ?? 0,
    size: payload.size ?? payload.file?.size ?? 0,
    progress: 0,
    loaded: 0,
    total: payload.size ?? payload.file?.size ?? 0,
    speed: 0,
    eta: Infinity,
    status: 'queued',
    statusText: '等待中...',
    error: '',
    controller: null,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

export const useTransferStore = defineStore('transfer', () => {
  const panelVisible = ref(false)
  const uploads = ref([])
  const downloads = ref([])

  const allTasks = computed(() => [...uploads.value, ...downloads.value])
  const runningTasks = computed(() => allTasks.value.filter((task) => task.status === 'running'))
  const activeCount = computed(() => allTasks.value.filter((task) => ['queued', 'running'].includes(task.status)).length)
  const totalSpeed = computed(() => runningTasks.value.reduce((sum, task) => sum + (task.speed || 0), 0))

  function openPanel() {
    panelVisible.value = true
  }

  function closePanel() {
    panelVisible.value = false
  }

  function togglePanel() {
    panelVisible.value = !panelVisible.value
  }

  function updateTask(task, updates) {
    Object.assign(task, {
      ...updates,
      progress: updates.progress ?? updates.percent ?? task.progress,
      updatedAt: Date.now(),
    })
  }

  function enqueueUpload(file, parentId = 0, name = file.name) {
    const task = createTask('upload', { file, parentId, name, size: file.size })
    uploads.value.unshift(task)
    openPanel()
    scheduleUploads()
    return task.id
  }

  function enqueueUploads(files, parentId = 0) {
    return Array.from(files).map((file) => enqueueUpload(file, parentId))
  }

  function enqueueDownload(file) {
    const task = createTask('download', {
      fileId: file.id,
      name: file.fileName || file.name || 'download',
      size: file.fileSize || file.size || 0,
    })
    downloads.value.unshift(task)
    openPanel()
    scheduleDownloads()
    return task.id
  }

  function scheduleUploads() {
    const running = uploads.value.filter((task) => task.status === 'running').length
    const slots = Math.max(MAX_UPLOADS - running, 0)
    uploads.value
      .filter((task) => task.status === 'queued')
      .slice(0, slots)
      .forEach(startUpload)
  }

  function scheduleDownloads() {
    const running = downloads.value.filter((task) => task.status === 'running').length
    const slots = Math.max(MAX_DOWNLOADS - running, 0)
    downloads.value
      .filter((task) => task.status === 'queued')
      .slice(0, slots)
      .forEach(startDownload)
  }

  async function startUpload(task) {
    let attempt = 0
    while (attempt <= MAX_UPLOAD_AUTO_RETRIES) {
      task.controller = new AbortController()
      updateTask(task, {
        status: 'running',
        statusText: attempt > 0 ? '重试中...' : '准备中...',
        error: '',
      })

      try {
        await uploadTransferFile(task.file, task.parentId, task.id, (_, updates) => {
          updateTask(task, updates)
        }, task.controller.signal)
        updateTask(task, {
          status: 'success',
          statusText: '上传完成',
          progress: 100,
          loaded: task.total,
          speed: 0,
          eta: 0,
        })
        useFileStore().triggerRefresh()
        task.controller = null
        scheduleUploads()
        return
      } catch (error) {
        const canceled = task.controller?.signal.aborted
        task.controller = null
        if (canceled) {
          updateTask(task, {
            status: 'canceled',
            statusText: '已取消',
            speed: 0,
            error: '已取消',
          })
          scheduleUploads()
          return
        }

        const canRetry = isRetryableUploadError(error) && attempt < MAX_UPLOAD_AUTO_RETRIES
        if (canRetry) {
          attempt += 1
          await sleep(2000 * attempt)
          continue
        }

        updateTask(task, {
          status: 'exception',
          statusText: '上传失败',
          speed: 0,
          error: normalizeError(error, '上传失败'),
        })
        console.error('上传任务失败:', error)
        scheduleUploads()
        return
      }
    }
  }

  async function startDownload(task) {
    task.controller = new AbortController()
    const speedTracker = new SpeedTracker()
    updateTask(task, { status: 'running', statusText: '下载中...', error: '' })

    try {
      const blob = await downloadFileBlob(task.fileId, (evt) => {
        const total = evt.total || task.total || 0
        const loaded = evt.loaded || 0
        speedTracker.update(loaded)
        const speed = speedTracker.getSpeed()
        updateTask(task, {
          total,
          loaded,
          speed,
          eta: speedTracker.getETA(Math.max(total - loaded, 0)),
          progress: total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : task.progress,
        })
      }, task.controller.signal)
      saveBlob(blob, task.name)
      updateTask(task, {
        status: 'success',
        statusText: '下载完成',
        progress: 100,
        loaded: task.total || blob.size,
        total: task.total || blob.size,
        speed: 0,
        eta: 0,
      })
    } catch (error) {
      const canceled = task.controller?.signal.aborted
      updateTask(task, {
        status: canceled ? 'canceled' : 'exception',
        statusText: canceled ? '已取消' : '下载失败',
        speed: 0,
        error: normalizeError(error, '下载失败'),
      })
      if (!canceled) console.error('下载任务失败:', error)
    } finally {
      task.controller = null
      scheduleDownloads()
    }
  }

  function cancelTask(task) {
    if (!task || !['queued', 'running'].includes(task.status)) return
    if (task.status === 'queued') {
      updateTask(task, { status: 'canceled', statusText: '已取消' })
      return
    }
    task.controller?.abort()
  }

  function retryTask(task) {
    if (!task || !['exception', 'canceled'].includes(task.status)) return
    updateTask(task, {
      status: 'queued',
      statusText: '等待中...',
      progress: 0,
      loaded: 0,
      speed: 0,
      eta: Infinity,
      error: '',
    })
    if (task.type === 'upload') scheduleUploads()
    if (task.type === 'download') scheduleDownloads()
  }

  function clearFinished(type) {
    const removable = ['success', 'exception', 'canceled']
    if (!type || type === 'upload') {
      uploads.value = uploads.value.filter((task) => !removable.includes(task.status))
    }
    if (!type || type === 'download') {
      downloads.value = downloads.value.filter((task) => !removable.includes(task.status))
    }
  }

  function notifyQueued(count, label) {
    if (count > 0) ElMessage.success(`已添加 ${count} 个${label}任务`)
  }

  return {
    panelVisible,
    uploads,
    downloads,
    allTasks,
    runningTasks,
    activeCount,
    totalSpeed,
    openPanel,
    closePanel,
    togglePanel,
    enqueueUpload,
    enqueueUploads,
    enqueueDownload,
    cancelTask,
    retryTask,
    clearFinished,
    notifyQueued,
  }
})
