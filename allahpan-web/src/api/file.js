import request from './index'

// 单步上传（multipart）
export function uploadFile(file, parentId, onProgress) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('parentId', parentId || 0)
  return request.post('/file/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
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

// 下载文件（以 blob 方式获取并触发浏览器下载）
export async function downloadFile(fileId, fileName) {
  const blob = await request.get(`/file/${fileId}/download`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName || 'download'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
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
