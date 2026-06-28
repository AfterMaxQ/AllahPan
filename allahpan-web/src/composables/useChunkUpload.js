import { ref } from 'vue'
import { calculateMD5 } from '@/utils/md5'
import { SpeedTracker, formatSpeed, formatETA } from '@/utils/transfer'
import { initUpload, uploadChunk, completeUpload } from '@/api/chunkUpload'
import { uploadFile } from '@/api/file'

// 2MB 分片：降低 Cloudflare/Nginx 单请求超时（524）风险
const CHUNK_SIZE = 2 * 1024 * 1024
const CHUNK_THRESHOLD = 10 * 1024 * 1024
const CONCURRENCY = 3
const UPLOAD_PROGRESS_MAX = 98 // 留 2% 给合并完成

function isCanceledError(error) {
  return error?.name === 'CanceledError'
    || error?.name === 'AbortError'
    || error?.code === 'ERR_CANCELED'
}

function ensureNotCanceled(signal) {
  if (signal?.aborted) {
    throw new DOMException('上传已取消', 'AbortError')
  }
}

function createEmitter(taskId, file, onTaskUpdate) {
  return (overrides) => onTaskUpdate?.(taskId, {
    progress: 0,
    percent: 0,
    speed: 0,
    eta: 0,
    loaded: 0,
    total: file.size,
    status: 'running',
    statusText: '准备中...',
    ...overrides,
  })
}

function getChunkSize(fileSize, index) {
  const start = index * CHUNK_SIZE
  return Math.max(0, Math.min(CHUNK_SIZE, fileSize - start))
}

function toUploadProgress(loaded, fileSize) {
  return Math.min(UPLOAD_PROGRESS_MAX, Math.round((loaded / fileSize) * UPLOAD_PROGRESS_MAX))
}

export async function uploadTransferFile(file, parentId, taskId, onTaskUpdate, signal) {
  if (file.size > CHUNK_THRESHOLD) {
    return uploadWithChunks(file, parentId, taskId, onTaskUpdate, signal)
  }
  return uploadSingleStep(file, parentId, taskId, onTaskUpdate, signal)
}

async function uploadSingleStep(file, parentId, taskId, onTaskUpdate, signal) {
  const emit = createEmitter(taskId, file, onTaskUpdate)
  const speedTracker = new SpeedTracker(8)
  let previousLoaded = 0

  emit({ statusText: '上传中...' })
  try {
    await uploadFile(file, parentId, (evt) => {
      const loaded = evt.loaded || 0
      const delta = loaded - previousLoaded
      previousLoaded = loaded
      if (delta > 0) speedTracker.addSample(delta)
      const progress = evt.percent || Math.round((loaded / file.size) * 100)
      emit({
        progress,
        percent: progress,
        loaded,
        speed: speedTracker.getSpeed(),
        eta: speedTracker.getETA(Math.max(file.size - loaded, 0)),
        statusText: '上传中...',
      })
    }, signal)
    emit({ progress: 100, percent: 100, loaded: file.size, status: 'success', statusText: '上传完成' })
  } catch (e) {
    if (isCanceledError(e) || signal?.aborted) {
      emit({ status: 'canceled', statusText: '已取消' })
      throw e
    }
    emit({ status: 'exception', statusText: '上传失败' })
    throw e
  }
}

async function uploadWithChunks(file, parentId, taskId, onTaskUpdate, signal) {
  const emit = createEmitter(taskId, file, onTaskUpdate)
  const speedTracker = new SpeedTracker(8)
  let lastReportedLoaded = 0

  const reportProgress = (loaded, statusText = '上传中...') => {
    const safeLoaded = Math.min(Math.max(loaded, 0), file.size)
    const delta = safeLoaded - lastReportedLoaded
    if (delta > 0) speedTracker.addSample(delta)
    lastReportedLoaded = safeLoaded
    const speed = speedTracker.getSpeed()
    const remaining = file.size - safeLoaded
    emit({
      progress: toUploadProgress(safeLoaded, file.size),
      percent: toUploadProgress(safeLoaded, file.size),
      loaded: safeLoaded,
      speed,
      eta: speedTracker.getETA(remaining),
      statusText,
    })
  }

  try {
    emit({ statusText: '准备中...', progress: 0, loaded: 0 })
    const fileMd5 = await calculateMD5(file)
    ensureNotCanceled(signal)

    emit({ statusText: '准备中...' })
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    const initResult = await initUpload({
      fileName: file.name,
      fileSize: file.size,
      fileMd5,
      contentType: file.type || 'application/octet-stream',
      parentId: parentId || 0,
      chunkSize: CHUNK_SIZE,
      totalChunks,
    }, signal)
    ensureNotCanceled(signal)

    const uploadId = initResult.uploadId
    const uploadedChunks = new Set(initResult.uploadedChunks || [])

    let completedBytes = Array.from(uploadedChunks)
      .reduce((sum, index) => sum + getChunkSize(file.size, index), 0)
    const inFlightBytes = new Map()

    const getTotalLoaded = () => {
      const partial = Array.from(inFlightBytes.values()).reduce((sum, n) => sum + n, 0)
      return Math.min(completedBytes + partial, file.size)
    }

    reportProgress(completedBytes, '上传中...')

    const pendingChunks = []
    for (let i = 0; i < totalChunks; i++) {
      if (!uploadedChunks.has(i)) {
        const start = i * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, file.size)
        pendingChunks.push({ index: i, blob: file.slice(start, end) })
      }
    }

    const queue = [...pendingChunks]

    async function worker() {
      while (queue.length > 0) {
        ensureNotCanceled(signal)
        const chunk = queue.shift()
        try {
          await uploadChunk(uploadId, chunk.index, chunk.blob, (chunkPercent) => {
            inFlightBytes.set(chunk.index, Math.round(chunk.blob.size * chunkPercent / 100))
            reportProgress(getTotalLoaded(), '上传中...')
          }, signal)
        } catch (e) {
          inFlightBytes.delete(chunk.index)
          if (isCanceledError(e) || signal?.aborted) return
          throw e
        }
        inFlightBytes.delete(chunk.index)
        completedBytes = Math.min(completedBytes + chunk.blob.size, file.size)
        reportProgress(completedBytes, '上传中...')
      }
    }

    const workerCount = Math.min(CONCURRENCY, Math.max(pendingChunks.length, 1))
    await Promise.all(Array.from({ length: workerCount }, () => worker()))
    ensureNotCanceled(signal)

    emit({ statusText: '正在完成...', progress: 99, loaded: file.size })
    await completeUpload(uploadId, signal)
    emit({
      progress: 100,
      percent: 100,
      loaded: file.size,
      speed: 0,
      eta: 0,
      status: 'success',
      statusText: '上传完成',
    })
    return initResult
  } catch (e) {
    if (isCanceledError(e) || signal?.aborted) {
      emit({ status: 'canceled', statusText: '已取消' })
      throw e
    }
    const errMsg = normalizeUploadError(e)
    emit({
      status: 'exception',
      statusText: '上传失败',
      loaded: lastReportedLoaded,
      progress: toUploadProgress(lastReportedLoaded, file.size),
    })
    throw new Error(errMsg)
  }
}

function normalizeUploadError(error) {
  const status = error?.response?.status
  if (status === 524 || status === 504) return '网络超时，请检查网络后重试'
  if (status === 502 || status === 503) return '服务暂时不可用，请稍后重试'
  return error?.response?.data?.message || error?.message || '上传失败'
}

export function useChunkUpload() {
  const uploading = ref(false)
  let abortController = null

  async function uploadFiles(files, parentId, onTaskUpdate, taskId) {
    uploading.value = true
    abortController = new AbortController()
    try {
      for (const file of files) {
        const tid = taskId || Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
        await uploadTransferFile(file, parentId, tid, onTaskUpdate, abortController.signal)
      }
    } finally {
      uploading.value = false
    }
  }

  function cancel() {
    abortController?.abort()
  }

  return { uploadFiles, cancel, uploading, CHUNK_THRESHOLD, formatSpeed, formatETA }
}
