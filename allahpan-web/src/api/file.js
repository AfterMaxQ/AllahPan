import request from './index'
import axios from 'axios'
import { useUserStore } from '@/stores/user'

// 无超时的 axios 实例（用于大文件下载）
const noTimeoutAxios = axios.create({ baseURL: '/api', timeout: 0 })
noTimeoutAxios.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

// 单步上传（multipart）
export function uploadFile(file, parentId, onProgress, signal) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('parentId', parentId || 0)
  return request.post('/file/upload', formData, {
    timeout: 300000, // 5 分钟超时，覆盖默认 30s，给慢速网络和 MinIO 处理足够时间
    signal,
    onUploadProgress: (event) => {
      if (onProgress) {
        if (event.total > 0) {
          onProgress({
            percent: Math.round((event.loaded / event.total) * 100),
            loaded: event.loaded,
          })
        } else if (event.loaded > 0) {
          // event.total 可能为 0（如 chunked encoding），按文件大小估算进度
          onProgress({
            percent: Math.round((event.loaded / file.size) * 100),
            loaded: event.loaded,
          })
        }
      }
    },
  })
}

// 文件列表
export function getFileList(parentId = 0) {
  return request.get('/file/list', { params: { parentId } })
}

// 目录树（面包屑）
export function getFileTree(folderId) {
  return request.get(`/file/tree/${folderId}`)
}

// 文件详情
export function getFileDetail(fileId) {
  return request.get(`/file/${fileId}`)
}

// 创建文件夹
export function createFolder(folderName, parentId) {
  return request.post('/file/create-folder', { folderName, parentId })
}

// 重命名
export function renameFile(fileId, newName) {
  return request.put(`/file/${fileId}/rename`, { newName })
}

// 移动
export function moveFile(fileId, targetParentId) {
  return request.put(`/file/${fileId}/move`, { targetParentId })
}

async function readBlobError(response) {
  const contentType = response.headers?.['content-type'] || ''
  if (!contentType.includes('application/json')) return null
  try {
    const text = await response.data.text()
    const data = JSON.parse(text)
    return data.message || data.msg || '请求失败'
  } catch {
    return '请求失败'
  }
}

export function saveBlob(blob, fileName) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName || 'download'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

export async function requestBlob(url, onProgress, signal) {
  const response = await noTimeoutAxios.get(url, {
    responseType: 'blob',
    signal,
    onDownloadProgress: (event) => {
      if (onProgress && event.loaded > 0) {
        onProgress({
          percent: event.total > 0 ? Math.round((event.loaded / event.total) * 100) : 0,
          loaded: event.loaded,
          total: event.total || 0,
        })
      }
    },
  })
  const blobError = await readBlobError(response)
  if (blobError) throw new Error(blobError)
  return response.data
}

// 下载文件（以 blob 方式获取，调用方决定是否触发保存）
export async function downloadFile(fileId, fileName, onProgress, signal) {
  const blob = await requestBlob(`/file/${fileId}/download`, onProgress, signal)
  saveBlob(blob, fileName)
  return blob
}

export async function downloadFileBlob(fileId, onProgress, signal) {
  return requestBlob(`/file/${fileId}/download`, onProgress, signal)
}

export async function createFileObjectUrl(fileId, signal) {
  const blob = await requestBlob(`/file/${fileId}/stream`, null, signal)
  return window.URL.createObjectURL(blob)
}

export async function createThumbnailObjectUrl(fileId, signal) {
  const blob = await requestBlob(`/file/${fileId}/thumbnail`, null, signal)
  return window.URL.createObjectURL(blob)
}

export async function createObjectUrlFromApi(url, signal) {
  const apiUrl = url?.startsWith('/api') ? url.slice(4) : url
  const blob = await requestBlob(apiUrl, null, signal)
  return window.URL.createObjectURL(blob)
}

// 预览流 URL
export function getStreamUrl(fileId) {
  return `/api/file/${fileId}/stream`
}

// 缩略图 URL
export function getThumbnailUrl(fileId) {
  return `/api/file/${fileId}/thumbnail`
}

// 软删除
export function deleteFile(fileId) {
  return request.delete(`/file/${fileId}`)
}

// 批量删除
export function batchDeleteFiles(fileIds) {
  return request.delete('/file/batch', { data: { fileIds } })
}

// 垃圾站列表
export function getTrashList(pageNum = 1, pageSize = 50) {
  return request.get('/file/trash', { params: { pageNum, pageSize } })
}

// 恢复文件
export function restoreFile(fileId) {
  return request.put(`/file/trash/${fileId}/restore`)
}

// 永久删除
export function permanentDelete(fileId) {
  return request.delete(`/file/trash/${fileId}`)
}
