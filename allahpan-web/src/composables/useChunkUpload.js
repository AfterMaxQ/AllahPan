import { ref } from 'vue'
import { calculateMD5 } from '@/utils/md5'
import { SpeedTracker, formatSpeed, formatETA } from '@/utils/transfer'
import { initUpload, uploadChunk, completeUpload } from '@/api/chunkUpload'
import { uploadFile } from '@/api/file'
import { uploadFileName } from '@/utils/fileName'

const CHUNK_SIZE = 2 * 1024 * 1024
const CHUNK_THRESHOLD = 10 * 1024 * 1024
// 每个文件最多同时上传两个分片。传输 store 最多会同时处理三个文件，
// 这样可以把总并发控制在 6 个请求以内，避免慢网络/代理下的请求排队和超时。
const CONCURRENCY = 2
const UPLOAD_PROGRESS_MAX = 98

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
  const speedTracker = new SpeedTracker()

  emit({ statusText: '上传中...' })
  try {
    await uploadFile(file, parentId, (evt) => {
      const loaded = evt.loaded || 0
      speedTracker.update(loaded)
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
  const speedTracker = new SpeedTracker()
  let lastReportedLoaded = 0
  let maxReportedLoaded = 0
  let mergeTimer = null

  const reportProgress = (loaded, statusText = '上传中...') => {
    const safeLoaded = Math.min(Math.max(loaded, maxReportedLoaded, 0), file.size)
    maxReportedLoaded = safeLoaded
    lastReportedLoaded = safeLoaded
    speedTracker.update(safeLoaded)
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

  const stopMergeTimer = () => {
    if (mergeTimer) {
      clearInterval(mergeTimer)
      mergeTimer = null
    }
  }

  /** 分片传完后服务器合并阶段：保持 99% 并清零测速，避免旧速度/ETA 误导 */
  const startMergeKeepalive = () => {
    stopMergeTimer()
    speedTracker.reset()
    const tick = () => {
      emit({
        statusText: '上传中...',
        progress: 99,
        percent: 99,
        loaded: file.size,
        speed: 0,
        eta: Infinity,
      })
    }
    tick()
    mergeTimer = setInterval(tick, 1000)
  }

  try {
    emit({ statusText: '准备中...', progress: 0, loaded: 0 })
    const fileMd5 = await calculateMD5(file)
    ensureNotCanceled(signal)

    emit({ statusText: '准备中...' })
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE)
    const initResult = await initUpload({
      fileName: uploadFileName(file),
      fileSize: file.size,
      fileMd5,
      contentType: file.type || 'application/octet-stream',
      parentId: parentId || 0,
      chunkSize: CHUNK_SIZE,
      totalChunks,
    }, signal)
    ensureNotCanceled(signal)

    const uploadId = initResult.uploadId
    if (initResult.status === 'instant' || initResult.status === 'completed') {
      emit({
        statusText: initResult.status === 'instant' ? '秒传中...' : '上传完成',
        progress: 99,
        percent: 99,
        loaded: file.size,
        speed: 0,
        eta: 0,
      })
      if (initResult.status === 'instant') {
        await completeUpload(uploadId, signal)
      }
      emit({
        progress: 100,
        percent: 100,
        loaded: file.size,
        speed: 0,
        eta: 0,
        status: 'success',
        statusText: '秒传完成',
      })
      return initResult
    }

    const uploadedChunks = new Set(initResult.uploadedChunks || [])

    const chunkBytes = new Map()
    for (const index of uploadedChunks) {
      chunkBytes.set(index, getChunkSize(file.size, index))
    }

    const setChunkProgress = (index, bytes) => {
      const size = getChunkSize(file.size, index)
      const prev = chunkBytes.get(index) || 0
      chunkBytes.set(index, Math.min(Math.max(prev, bytes), size))
    }

    const getTotalLoaded = () => {
      let sum = 0
      for (const bytes of chunkBytes.values()) sum += bytes
      return Math.min(sum, file.size)
    }

    reportProgress(getTotalLoaded(), '上传中...')

    const pendingChunks = []
    for (let i = 0; i < totalChunks; i++) {
      if (!uploadedChunks.has(i)) {
        const start = i * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, file.size)
        pendingChunks.push({ index: i, blob: file.slice(start, end) })
      }
    }

    const queue = [...pendingChunks]
    const workerController = new AbortController()
    let firstWorkerError = null

    // 任一 worker 失败时，必须先停止并等待其他 worker，才能让外层安全重试。
    // 否则旧一轮请求会和新一轮请求同时操作同一个 uploadId，造成分片状态竞态。
    const abortWorkers = () => {
      if (!workerController.signal.aborted) workerController.abort()
    }
    const handleCallerAbort = () => abortWorkers()
    signal?.addEventListener('abort', handleCallerAbort, { once: true })

    async function worker() {
      while (queue.length > 0 && !firstWorkerError && !workerController.signal.aborted) {
        ensureNotCanceled(signal)
        const chunk = queue.shift()
        try {
          await uploadChunk(
            uploadId,
            chunk.index,
            chunk.blob,
            (chunkPercent) => {
              setChunkProgress(chunk.index, Math.round(chunk.blob.size * chunkPercent / 100))
              reportProgress(getTotalLoaded(), '上传中...')
            },
            workerController.signal,
          )
        } catch (e) {
          // 调用方取消，或其他 worker 已经失败并触发了内部 abort，均由外层统一收口。
          if (isCanceledError(e) || signal?.aborted || workerController.signal.aborted) return
          firstWorkerError = e
          abortWorkers()
          return
        }
        setChunkProgress(chunk.index, chunk.blob.size)
        reportProgress(getTotalLoaded(), '上传中...')
      }
    }

    const workerCount = Math.min(CONCURRENCY, Math.max(pendingChunks.length, 1))
    try {
      await Promise.all(Array.from({ length: workerCount }, () => worker()))
      ensureNotCanceled(signal)
      if (firstWorkerError) throw firstWorkerError
    } finally {
      signal?.removeEventListener('abort', handleCallerAbort)
    }

    startMergeKeepalive()
    await completeUpload(uploadId, signal)
    stopMergeTimer()

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
    stopMergeTimer()
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
