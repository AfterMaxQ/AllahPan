<template>
  <el-dialog
    v-model="visible"
    :title="mode === 'folder' ? '上传文件夹' : '上传文件'"
    width="520px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <div class="dialog-body">
      <!-- 文件模式：拖拽上传 -->
      <div v-if="mode === 'file'">
        <el-upload
          class="ap-uploader"
          drag
          action=""
          multiple
          :auto-upload="false"
          :on-change="handleFileChange"
        >
          <el-icon class="el-icon--upload" size="40" color="var(--el-color-primary-light-3)">
            <UploadFilled />
          </el-icon>
          <div class="el-upload__text">
            拖拽文件到这里，或<em>点击上传</em>
          </div>
        </el-upload>
      </div>

      <!-- 文件夹模式：点击选择文件夹 -->
      <div v-else class="ap-uploader folder-uploader" @click="triggerFolderInput">
        <el-icon size="40" color="var(--el-color-primary-light-3)">
          <FolderOpened />
        </el-icon>
        <div class="el-upload__text">
          点击选择<em>文件夹</em>
        </div>
        <div v-if="selectedFolderName" class="folder-name">
          已选择：<strong>{{ selectedFolderName }}</strong>（{{ folderFileCount }} 个文件）
        </div>
      </div>
      <input
        ref="folderInputRef"
        type="file"
        webkitdirectory
        directory
        style="display: none"
        @change="handleFolderChange"
      />

      <!-- 上传任务列表 -->
      <div v-if="tasks.length > 0" class="task-list">
        <div v-for="task in tasks" :key="task.id" class="task-item">
          <div class="task-info">
            <span class="task-name" :title="task.name">{{ task.name }}</span>
            <span class="task-status" :class="task.status">{{ task.statusText }}</span>
          </div>
          <el-progress
            :percentage="task.progress"
            :status="task.progressStatus"
            :stroke-width="4"
          />
          <div v-if="task.status === 'pending' && task.speed > 0" class="task-detail">
            {{ formatSpeed(task.speed) }} · {{ formatETA(task.eta) }} · {{ formatSize(task.loaded) }}/{{ formatSize(task.total) }}
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, FolderOpened } from '@element-plus/icons-vue'
import { useFileStore } from '@/stores/file'
import { createFolder } from '@/api/file'
import { useChunkUpload } from '@/composables/useChunkUpload'

const visible = ref(false)
const mode = ref('file') // 'file' | 'folder'
const fileStore = useFileStore()
const tasks = ref([])
const folderInputRef = ref(null)
const selectedFolderName = ref('')
const folderFileCount = ref(0)

const { uploadFiles, formatSpeed, formatETA } = useChunkUpload()

function formatSize(bytes) {
  if (bytes == null || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const open = () => {
  mode.value = 'file'
  visible.value = true
  tasks.value = []
}

const openFolder = () => {
  mode.value = 'folder'
  visible.value = true
  tasks.value = []
  selectedFolderName.value = ''
  folderFileCount.value = 0
}

defineExpose({ open, openFolder })
const emit = defineEmits(['uploaded'])

const triggerFolderInput = () => {
  folderInputRef.value?.click()
}

// 创建任务并注册回调
const createTask = (name) => {
  const taskId = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  const task = {
    id: taskId,
    name,
    progress: 0,
    speed: 0,
    eta: 0,
    loaded: 0,
    total: 0,
    status: 'pending',
    statusText: '准备中...',
    progressStatus: '',
  }
  tasks.value.push(task)
  return taskId
}

const onTaskUpdate = (taskId, updates) => {
  const t = tasks.value.find((task) => task.id === taskId)
  if (!t) return
  Object.assign(t, {
    ...updates,
    progressStatus: updates.status === 'success' ? 'success'
      : updates.status === 'exception' ? 'exception' : '',
  })
}

// 文件模式：el-upload on-change 逐文件触发
const handleFileChange = async (uploadFile) => {
  const file = uploadFile.raw
  const taskId = createTask(file.name)

  try {
    await uploadFiles([file], fileStore.currentFolderId, onTaskUpdate, taskId)
    ElMessage.success(`${file.name} 上传成功`)
    emit('uploaded')
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(`${file.name} 上传失败`)
  }
}

// 文件夹模式：解析目录结构 -> 创建文件夹 -> 上传文件
const handleFolderChange = async (event) => {
  const files = Array.from(event.target.files)
  if (files.length === 0) return

  // 提取根文件夹名
  const firstPath = files[0].webkitRelativePath || files[0].name
  selectedFolderName.value = firstPath.split('/')[0]
  folderFileCount.value = files.length

  // 1. 收集所有唯一目录路径，按深度排序
  const dirSet = new Set()
  files.forEach((f) => {
    const path = f.webkitRelativePath || f.name
    const parts = path.split('/')
    for (let i = 1; i < parts.length; i++) {
      dirSet.add(parts.slice(0, i).join('/'))
    }
  })
  const dirs = Array.from(dirSet).sort(
    (a, b) => a.split('/').length - b.split('/').length
  )

  // 2. 逐层创建文件夹，构建 path -> id 映射
  const pathToId = new Map()
  pathToId.set('', fileStore.currentFolderId)

  for (const dir of dirs) {
    const parts = dir.split('/')
    const folderName = parts[parts.length - 1]
    const parentPath = parts.slice(0, -1).join('/')
    const parentId = pathToId.get(parentPath)

    const taskId = 'folder-' + dir
    tasks.value.push({
      id: taskId,
      name: dir,
      progress: 0,
      speed: 0, eta: 0, loaded: 0, total: 0,
      status: 'pending',
      statusText: '创建文件夹...',
      progressStatus: '',
    })

    try {
      const result = await createFolder(folderName, parentId)
      pathToId.set(dir, result.id)
      const t = tasks.value.find((task) => task.id === taskId)
      if (t) {
        t.progress = 100
        t.status = 'success'
        t.statusText = '已创建'
        t.progressStatus = 'success'
      }
    } catch (e) {
      const t = tasks.value.find((task) => task.id === taskId)
      if (t) {
        t.status = 'exception'
        t.statusText = '创建失败（可能已存在同名文件夹）'
        t.progressStatus = 'exception'
      }
      ElMessage.error(`创建文件夹 "${dir}" 失败，请检查是否有同名文件夹已存在`)
      return
    }
  }

  // 3. 上传所有文件到对应子文件夹
  const fileList = []
  const fileTaskIds = []
  for (const file of files) {
    const path = file.webkitRelativePath || file.name
    const parts = path.split('/')
    const parentPath = parts.slice(0, -1).join('/')
    const parentId = pathToId.get(parentPath) || fileStore.currentFolderId

    fileList.push(file)
    fileTaskIds.push(parentId)
  }

  // 按 parentId 分组处理，每组独立上传
  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i]
    const parentId = fileTaskIds[i]
    const name = (file.webkitRelativePath || file.name).split('/').pop()
    const taskId = createTask(name)

    try {
      await uploadFiles([file], parentId, onTaskUpdate, taskId)
      ElMessage.success(`${name} 上传成功`)
    } catch (e) {
      ElMessage.error(`${name} 上传失败`)
    }
  }

  emit('uploaded')
}
</script>

<style scoped>
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.ap-uploader :deep(.el-upload-dragger) {
  border: 2px dashed var(--ap-border-color);
  background-color: var(--ap-bg-page);
  border-radius: 12px;
  padding: 40px 20px;
}
.ap-uploader :deep(.el-upload-dragger:hover) {
  border-color: var(--el-color-primary);
}
.folder-uploader {
  border: 2px dashed var(--ap-border-color);
  background-color: var(--ap-bg-page);
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s;
}
.folder-uploader:hover {
  border-color: var(--el-color-primary);
}
.folder-uploader .el-upload__text {
  color: var(--ap-text-sub);
  font-size: 14px;
  margin-top: 12px;
}
.folder-uploader .folder-name {
  margin-top: 12px;
  font-size: 13px;
  color: var(--ap-text-main);
}
.task-list {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--ap-border-color);
  border-radius: 10px;
  padding: 12px;
  background-color: var(--ap-bg-page);
}
.task-item {
  margin-bottom: 12px;
}
.task-item:last-child {
  margin-bottom: 0;
}
.task-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
}
.task-name {
  color: var(--ap-text-main);
  font-weight: 500;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-status {
  font-size: 12px;
  color: var(--ap-text-sub);
  flex-shrink: 0;
}
.task-status.success { color: #67c23a; }
.task-status.exception { color: #f56c6c; }
.task-detail {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ap-text-sub);
}
</style>
