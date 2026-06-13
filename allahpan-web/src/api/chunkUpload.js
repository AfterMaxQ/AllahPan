import axios from 'axios'
import { useUserStore } from '@/stores/user'

// 无超时限制的 axios 实例，用于分片上传/下载
const noTimeoutAxios = axios.create({
  baseURL: '/api',
  timeout: 0,
})

// 复用 JWT 拦截器
noTimeoutAxios.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

// 复用响应拦截器（解包 CommonResult）
noTimeoutAxios.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code === undefined) return res
    if (res.code === 200) return res.data
    return Promise.reject(new Error(res.message || 'Error'))
  },
  (error) => Promise.reject(error)
)

/**
 * 初始化上传会话（支持断点续传）
 * @returns {{ uploadId, uploadedChunks, status }}
 */
export function initUpload(data) {
  return noTimeoutAxios.post('/file/chunk/init', data)
}

/**
 * 上传单个分片
 * @param {string} uploadId
 * @param {number} chunkIndex
 * @param {Blob} chunkBlob
 * @param {Function} onProgress - (percent: 0-100)
 */
export function uploadChunk(uploadId, chunkIndex, chunkBlob, onProgress) {
  const formData = new FormData()
  formData.append('uploadId', uploadId)
  formData.append('chunkIndex', chunkIndex)
  formData.append('chunk', chunkBlob, 'chunk')

  return noTimeoutAxios.post('/file/chunk/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
}

/**
 * 合并分片并完成上传
 */
export function completeUpload(uploadId) {
  return noTimeoutAxios.post('/file/chunk/complete', { uploadId })
}

/**
 * 查询上传会话状态（用于断点续传恢复）
 */
export function getUploadStatus(uploadId) {
  return noTimeoutAxios.get(`/file/chunk/status/${uploadId}`)
}
