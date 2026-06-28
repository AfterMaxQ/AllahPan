import { ref } from 'vue'
import { calculateMD5 } from '@/utils/md5'
import { SpeedTracker, formatSpeed, formatETA } from '@/utils/transfer'
import { initUpload, uploadChunk, completeUpload } from '@/api/chunkUpload'
import { uploadFile } from '@/api/file'

const CHUNK_SIZE = 10 * 1024 * 1024 // 10MB
const CHUNK_THRESHOLD = 10 * 1024 * 1024 // 10MB：超过此值使用分片上传
const CONCURRENCY = 6

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

export async function uploadTransferFile(file, parentId, taskId, onTaskUpdate, signal) {
  if (file.size > CHUNK_THRESHOLD) {
    return uploadWithChunks(file, parentId, taskId, onTaskUpdate, signal)
  }
  return uploadSingleStep(file, parentId, taskId, onTaskUpdate, signal)
}

// ---- 单步上传（小文件） ----

async function uploadSingleStep(file, parentId, taskId, onTaskUpdate, signal) {
  const emit = createEmitter(taskId, file, onTaskUpdate)
  const speedTracker = new SpeedTracker()
  let previousLoaded = 0

  emit({ statusText: '上传中...' })
  try {
    await uploadFile(file, parentId, (evt) => {
      const loaded = evt.loaded || 0
      const delta = loaded - previousLoaded
      previousLoaded = loaded
      if (delta > 0) speedTracker.addSample(delta)
      const speed = speedTracker.getSpeed()
      const progress = evt.percent || Math.round((loaded / file.size) * 100)
      emit({
        progress,
        percent: progress,
        loaded,
        speed,
        eta: speedTracker.getETA(Math.max(file.size - loaded, 0)),
      })
    }, signal)
    emit({ progress: 100, percent: 100, loaded: file.size, status: 'success', statusText: '上传成功' })
  } catch (e) {
    if (isCanceledError(e) || signal?.aborted) {
      emit({ status: 'canceled', statusText: '已取消' })
      throw e
    }
    emit({ status: 'exception', statusText: '上传失败' })
    throw e
  }
}

// ---- 分片上传（大文件） ----

async function uploadWithChunks(file, parentId, taskId, onTaskUpdate, signal) {
  const emit = createEmitter(taskId, file, onTaskUpdate)

  try {
    // 1. 计算 MD5
    emit({ statusText: '计算文件指纹...' })
    const fileMd5 = await calculateMD5(file, (p) => {
      const progress = Math.round(p * 0.05)
      emit({ progress, percent: progress, statusText: `计算指纹 ${p}%` }) // 前5%留给MD5
    })
    ensureNotCanceled(signal)

    // 2. 初始化上传会话
    emit({ statusText: '初始化...' })
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    const initResult = await initUpload({
      fileName: file.name,
      fileSize: file.size,
      fileMd5,
      contentType: file.type || 'application/octet-stream',
      parentId: parentId || 0,
      chunkSize: CHUNK_SIZE,
      totalChunks,
    })
    ensureNotCanceled(signal)

    const uploadId = initResult.uploadId
    const uploadedChunks = new Set(initResult.uploadedChunks || [])
    const isResumed = initResult.status === 'resumed'

    emit({
      statusText: isResumed ? `续传中...（已上传 ${uploadedChunks.size}/${totalChunks}）` : '上传中...',
      progress: Math.round((uploadedChunks.size / totalChunks) * 100),
      percent: Math.round((uploadedChunks.size / totalChunks) * 100),
      loaded: uploadedChunks.size * CHUNK_SIZE,
    })

    // 3. 收集待上传分片
    const pendingChunks = []
    for (let i = 0; i < totalChunks; i++) {
      if (!uploadedChunks.has(i)) {
        const start = i * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, file.size)
        pendingChunks.push({ index: i, blob: file.slice(start, end) })
      }
    }

    // 4. 并发上传
    const speedTracker = new SpeedTracker()
    const getChunkSize = (index) => {
      const start = index * CHUNK_SIZE
      return Math.max(0, Math.min(CHUNK_SIZE, file.size - start))
    }
    let completedCount = uploadedChunks.size
    let completedBytes = Array.from(uploadedChunks)
      .reduce((sum, index) => sum + getChunkSize(index), 0)
    const inFlightBytes = new Map()
    const queue = [...pendingChunks]

    const emitUploadProgress = (statusText) => {
      const partialBytes = Array.from(inFlightBytes.values())
        .reduce((sum, bytes) => sum + bytes, 0)
      const loaded = Math.min(completedBytes + partialBytes, file.size)
      const remaining = file.size - loaded
      const speed = speedTracker.getSpeed()
      const progress = Math.round((loaded / file.size) * 100)
      emit({
        progress,
        percent: progress,
        loaded,
        speed,
        eta: speedTracker.getETA(remaining),
        statusText,
      })
    }

    async function worker() {
      while (queue.length > 0) {
        ensureNotCanceled(signal)
        const chunk = queue.shift()
        try {
          await uploadChunk(uploadId, chunk.index, chunk.blob, (chunkPercent) => {
            inFlightBytes.set(chunk.index, Math.round(chunk.blob.size * chunkPercent / 100))
            emitUploadProgress(`分片 ${completedCount}/${totalChunks} · 正在上传第 ${chunk.index + 1} 片 (${chunkPercent}%)`)
          }, signal)
        } catch (e) {
          inFlightBytes.delete(chunk.index)
          if (isCanceledError(e) || signal?.aborted) {
            return
          }
          throw e
        }
        inFlightBytes.delete(chunk.index)
        completedCount += 1
        completedBytes = Math.min(completedBytes + chunk.blob.size, file.size)
        speedTracker.addSample(chunk.blob.size)
        emitUploadProgress(`分片 ${completedCount}/${totalChunks}`)
      }
    }

    const workers = Array.from({ length: Math.min(CONCURRENCY, pendingChunks.length) }, () => worker())
    await Promise.all(workers)
    ensureNotCanceled(signal)

    // 5. 完成上传
    emit({ statusText: '合并分片中...' })
    const result = await completeUpload(uploadId)
    emit({ progress: 100, percent: 100, loaded: file.size, status: 'success', statusText: '上传成功' })
    return result

  } catch (e) {
    if (isCanceledError(e) || signal?.aborted) {
      emit({ status: 'canceled', statusText: '已取消' })
      throw e
    }
    const errMsg = e?.response?.data?.message || e?.message || '未知错误'
    emit({ status: 'exception', statusText: `上传失败：${errMsg}` })
    throw e
  }
}

// ====================== useChunkUpload ======================

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
