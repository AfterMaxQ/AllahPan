// ====================== SpeedTracker ======================

/**
 * 基于「累计字节 + 时间窗口」的测速器。
 *
 * 调用方在每次进度回调时传入【累计已传输字节数】（而非增量），
 * 测速器在最近 windowMs 毫秒的窗口内用 (Δ字节 / Δ时间) 计算速度。
 *
 * 相比旧版「样本增量 + 固定样本数窗口」实现：
 * - 单次/快速上传只产生一个进度事件时也能给出速度（用起始点兜底），
 *   不会再恒为 0；
 * - 分片并发上传时进度事件成簇到达也能得到平滑、稳定的速度。
 *
 * 上传（useChunkUpload）和下载（transfer store）共用。
 */
export class SpeedTracker {
  constructor(windowMs = 3000, staleMs = 2000) {
    this.windowMs = windowMs
    this.staleMs = staleMs
    this.samples = []
    this.startTime = 0
    this.startLoaded = 0
    this.lastUpdateTime = 0
  }

  /** 传入累计已传输字节数 */
  update(loaded) {
    if (loaded == null || loaded < 0) return
    const now = Date.now()
    this.lastUpdateTime = now
    if (this.startTime === 0) {
      this.startTime = now
      this.startLoaded = loaded
    }
    this.samples.push({ loaded, t: now })
    const cutoff = now - this.windowMs
    while (this.samples.length > 2 && this.samples[0].t < cutoff) {
      this.samples.shift()
    }
  }

  /** 超过 staleMs 无新数据视为停滞（如服务器合并、分片重试等待） */
  isStale() {
    return this.lastUpdateTime > 0 && Date.now() - this.lastUpdateTime > this.staleMs
  }

  getSpeed() {
    if (this.isStale()) return 0
    if (this.samples.length >= 2) {
      const first = this.samples[0]
      const last = this.samples[this.samples.length - 1]
      const dt = (last.t - first.t) / 1000
      const db = last.loaded - first.loaded
      if (dt > 0 && db > 0) return db / dt
    }
    if (this.startTime > 0 && this.samples.length > 0) {
      const last = this.samples[this.samples.length - 1]
      const dt = (last.t - this.startTime) / 1000
      const db = last.loaded - this.startLoaded
      if (dt > 0 && db > 0) return db / dt
    }
    return 0
  }

  getETA(remainingBytes) {
    const speed = this.getSpeed()
    return speed > 0 ? remainingBytes / speed : Infinity
  }

  reset() {
    this.samples = []
    this.startTime = 0
    this.startLoaded = 0
    this.lastUpdateTime = 0
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
