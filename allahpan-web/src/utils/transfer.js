// ====================== SpeedTracker ======================

/**
 * 滑动窗口测速器 — 取最近 N 个样本计算瞬时速度。
 * 上传（useChunkUpload）和下载（FileDownloadDialog）共用。
 */
export class SpeedTracker {
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

  reset() {
    this.samples = []
    this.totalBytes = 0
  }
}

// ====================== Format helpers ======================

/**
 * 格式化传输速度：B/s、KB/s、MB/s
 */
export function formatSpeed(bytesPerSec) {
  if (bytesPerSec >= 1e6) return (bytesPerSec / 1e6).toFixed(1) + ' MB/s'
  if (bytesPerSec >= 1e3) return (bytesPerSec / 1e3).toFixed(0) + ' KB/s'
  return bytesPerSec.toFixed(0) + ' B/s'
}

/**
 * 格式化预估剩余时间：Xs / Xm Ys / 计算中...
 */
export function formatETA(seconds) {
  if (!isFinite(seconds) || seconds <= 0) return '计算中...'
  if (seconds < 60) return Math.ceil(seconds) + 's'
  const m = Math.floor(seconds / 60)
  const s = Math.ceil(seconds % 60)
  return m + 'm ' + s + 's'
}
