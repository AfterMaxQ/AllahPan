import axios from 'axios'
import { useUserStore } from '@/stores/user'

const noTimeoutAxios = axios.create({
  baseURL: '/api',
  timeout: 120000, // 单片 2MB，120s 足够；避免长时间挂死
})

noTimeoutAxios.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

noTimeoutAxios.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code === undefined) return res
    if (res.code === 200) return res.data
    return Promise.reject(new Error(res.message || 'Error'))
  },
  (error) => Promise.reject(error)
)

export function isRetryableUploadError(error) {
  const status = error?.response?.status
  if ([408, 429, 500, 502, 503, 504, 524].includes(status)) return true
  const code = error?.code
  if (code === 'ECONNABORTED' || code === 'ERR_NETWORK' || code === 'ETIMEDOUT') return true
  const msg = (error?.message || '').toLowerCase()
  return msg.includes('timeout') || msg.includes('network') || msg.includes('524')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function withRetry(requestFn, { maxRetries = 4, baseDelay = 1500, signal } = {}) {
  let lastError
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    if (signal?.aborted) {
      throw new DOMException('上传已取消', 'AbortError')
    }
    try {
      return await requestFn()
    } catch (error) {
      lastError = error
      if (error?.name === 'AbortError' || error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED') {
        throw error
      }
      if (!isRetryableUploadError(error) || attempt === maxRetries) throw error
      await sleep(baseDelay * Math.pow(2, attempt))
    }
  }
  throw lastError
}

export function initUpload(data, signal) {
  return withRetry(
    () => noTimeoutAxios.post('/file/chunk/init', data, { signal }),
    { maxRetries: 3, signal }
  )
}

export function uploadChunk(uploadId, chunkIndex, chunkBlob, onProgress, signal) {
  const formData = new FormData()
  formData.append('uploadId', uploadId)
  formData.append('chunkIndex', chunkIndex)
  formData.append('chunk', chunkBlob, 'chunk')

  const actualSize = chunkBlob.size

  return withRetry(
    () => noTimeoutAxios.post('/file/chunk/upload', formData, {
      signal,
      onUploadProgress: (event) => {
        if (!onProgress) return
        if (event.total > 0) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        } else if (event.loaded > 0) {
          onProgress(Math.min(99, Math.round((event.loaded / actualSize) * 100)))
        }
      },
    }),
    { maxRetries: 5, baseDelay: 2000, signal }
  )
}

export function completeUpload(uploadId, signal) {
  return withRetry(
    () => noTimeoutAxios.post('/file/chunk/complete', { uploadId }, {
      signal,
      timeout: 600000, // 大文件合并可能较久
    }),
    { maxRetries: 3, baseDelay: 3000, signal }
  )
}

export function getUploadStatus(uploadId) {
  return noTimeoutAxios.get(`/file/chunk/status/${uploadId}`)
}
