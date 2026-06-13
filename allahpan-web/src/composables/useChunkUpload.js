import { ref } from 'vue'
import { calculateMD5 } from '@/utils/md5'
import { initUpload, uploadChunk, completeUpload } from '@/api/chunkUpload'
import { uploadFile } from '@/api/file'

const CHUNK_SIZE = 10 * 1024 * 1024 // 10MB
const CHUNK_THRESHOLD = 10 * 1024 * 1024 // 10MB：超过此值使用分片上传
const CONCURRENCY = 6

// ====================== SpeedTracker ======================

class SpeedTracker {
  constructor(windowSize = 5) {
    this.samples = [] // [{ bytes, timestamp }]
    this.windowSize = windowSize
    this.totalBytes = 0
  }

  addSample(bytes) {
    const now = Date.now()
    this.samples.push({ bytes, timestamp: now })
    if (this.samples.length > this.windowSize) {
      this.samples.shift()
    }
    this.totalBytes += bytes
  }

  getSpeed() {
    if (this.samples.length < 2) return 0
    const first = this.samples[0]
    const last = this.samples[this.samples.length - 1]
    const totalBytes = this.samples.slice(1).reduce((s, v) => s + v.bytes, 0)
    const duration = (last.timestamp - first.timestamp) / 1000
    return duration > 0 ? totalBytes / duration : 0
  }

  getETA(remainingBytes) {
    const speed = this.getSpeed()
    return speed > 0 ? remainingBytes / speed : Infinity
  }
}

// ====================== Format helpers ======================

function formatSpeed(bytesPerSec) {
  if (bytesPerSec >= 1e6) return (bytesPerSec / 1e6).toFixed(1) + ' MB/s'
  if (bytesPerSec >= 1e3) return (bytesPerSec / 1e3).toFixed(0) + ' KB/s'
  return bytesPerSec.toFixed(0) + ' B/s'
}

function formatETA(seconds) {
  if (!isFinite(seconds)) return '--'
  if (seconds < 60) return Math.ceil(seconds) + 's'
  const m = Math.floor(seconds / 60)
  const s = Math.ceil(seconds % 60)
  return m + 'm ' + s + 's'
}

// ====================== useChunkUpload ======================

export function useChunkUpload() {
  const uploading = ref(false)
  let cancelFlag = false

  /**
   * 上传一批文件（自动选择单步/分片）
   * @param {File[]} files
   * @param {number} parentId
   * @param {Function} onTaskUpdate - (taskId, { percent, speed, eta, loaded, total, status, statusText })
   * @param {string} [taskId] - 可选，传入则由调用方管理任务 ID，避免重复创建
   */
  async function uploadFiles(files, parentId, onTaskUpdate, taskId) {
    uploading.value = true
    cancelFlag = false

    for (const file of files) {
      if (cancelFlag) break

      const tid = taskId || Date.now().toString(36) + Math.random().toString(36).slice(2, 6)

      if (file.size > CHUNK_THRESHOLD) {
        await uploadWithChunks(file, parentId, tid, onTaskUpdate)
      } else {
        await uploadSingleStep(file, parentId, tid, onTaskUpdate)
      }
    }

    uploading.value = false
  }

  function cancel() {
    cancelFlag = true
  }

  // ---- 单步上传（小文件，复用原有逻辑） ----

  async function uploadSingleStep(file, parentId, taskId, onTaskUpdate) {
    const emit = (overrides) => onTaskUpdate(taskId, {
      percent: 0, speed: 0, eta: 0, loaded: 0, total: file.size,
      status: 'pending', statusText: '准备中...',
      ...overrides,
    })

    emit({ statusText: '上传中...' })
    try {
      await uploadFile(file, parentId, (p) => {
        emit({ percent: p, loaded: Math.round(file.size * p / 100) })
      })
      emit({ percent: 100, loaded: file.size, status: 'success', statusText: '上传成功' })
    } catch (e) {
      emit({ status: 'exception', statusText: '上传失败' })
      throw e
    }
  }

  // ---- 分片上传（大文件） ----

  async function uploadWithChunks(file, parentId, taskId, onTaskUpdate) {
    const emit = (overrides) => onTaskUpdate(taskId, {
      percent: 0, speed: 0, eta: 0, loaded: 0, total: file.size,
      status: 'pending', statusText: '准备中...',
      ...overrides,
    })

    try {
      // 1. 计算 MD5
      emit({ statusText: '计算文件指纹...' })
      const fileMd5 = await calculateMD5(file, (p) => {
        emit({ percent: Math.round(p * 0.05), statusText: `计算指纹 ${p}%` }) // 前5%留给MD5
      })
      if (cancelFlag) return

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
      if (cancelFlag) return

      const uploadId = initResult.uploadId
      const uploadedChunks = new Set(initResult.uploadedChunks || [])
      const isResumed = initResult.status === 'resumed'

      emit({
        statusText: isResumed ? `续传中...（已上传 ${uploadedChunks.size}/${totalChunks}）` : '上传中...',
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
      const uploadedBytes = uploadedChunks.size * CHUNK_SIZE
      const queue = [...pendingChunks]

      async function worker() {
        while (queue.length > 0 && !cancelFlag) {
          const chunk = queue.shift()
          // 分片内部进度：实时反馈当前分片的上传进度
          await uploadChunk(uploadId, chunk.index, chunk.blob, (chunkPercent) => {
            const doneBeforeThis = totalChunks - queue.length - 1
            if (doneBeforeThis >= 0) {
              const loadedSoFar = Math.min(
                doneBeforeThis * CHUNK_SIZE + Math.round(chunk.blob.size * chunkPercent / 100),
                file.size
              )
              const remainingSoFar = file.size - loadedSoFar
              emit({
                percent: Math.round((loadedSoFar / file.size) * 100),
                loaded: loadedSoFar,
                speed: speedTracker.getSpeed(),
                eta: speedTracker.getETA(remainingSoFar),
                statusText: `${doneBeforeThis}/${totalChunks} 分片 · 当前分片 ${chunkPercent}%`,
              })
            }
          })
          speedTracker.addSample(chunk.blob.size)
          const done = totalChunks - queue.length
          const loaded = Math.min(done * CHUNK_SIZE, file.size)
          const remaining = file.size - loaded
          const speed = speedTracker.getSpeed()
          const eta = speedTracker.getETA(remaining)

          emit({
            percent: Math.round((done / totalChunks) * 100),
            loaded,
            speed,
            eta,
            statusText: `${done}/${totalChunks} 分片`,
          })
        }
      }

      const workers = Array.from({ length: Math.min(CONCURRENCY, pendingChunks.length) }, () => worker())
      await Promise.all(workers)
      if (cancelFlag) return

      // 5. 完成上传
      emit({ statusText: '合并分片中...' })
      const result = await completeUpload(uploadId)
      emit({ percent: 100, loaded: file.size, status: 'success', statusText: '上传成功' })
      return result

    } catch (e) {
      if (!cancelFlag) {
        emit({ status: 'exception', statusText: '上传失败' })
      }
      throw e
    }
  }

  return { uploadFiles, cancel, uploading, CHUNK_THRESHOLD, formatSpeed, formatETA }
}
