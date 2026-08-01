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
          :show-file-list="false"
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
          已选择：<strong class="ap-file-name" dir="auto">{{ selectedFolderName }}</strong>（{{ folderFileCount }} 个文件）
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
      <div class="upload-hint">
        选择后会加入右侧传输列表，可在那里查看实时速度、进度并取消或重试。
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, FolderOpened } from '@element-plus/icons-vue'
import { useFileStore } from '@/stores/file'
import { useTransferStore } from '@/stores/transfer'
import { createFolder } from '@/api/file'

const visible = ref(false)
const mode = ref('file') // 'file' | 'folder'
const fileStore = useFileStore()
const transferStore = useTransferStore()
const folderInputRef = ref(null)
const selectedFolderName = ref('')
const folderFileCount = ref(0)

const open = () => {
  mode.value = 'file'
  visible.value = true
}

const openFolder = () => {
  mode.value = 'folder'
  visible.value = true
  selectedFolderName.value = ''
  folderFileCount.value = 0
}

defineExpose({ open, openFolder })
const emit = defineEmits(['uploaded'])

const triggerFolderInput = () => {
  folderInputRef.value?.click()
}

// 文件模式：el-upload on-change 逐文件触发
const handleFileChange = (uploadFile) => {
  const file = uploadFile.raw
  if (!file) return
  transferStore.enqueueUpload(file, fileStore.currentFolderId)
  transferStore.notifyQueued(1, '上传')
  visible.value = false
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

    try {
      const result = await createFolder(folderName, parentId)
      pathToId.set(dir, result.id)
    } catch (e) {
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

  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i]
    const parentId = fileTaskIds[i]
    transferStore.enqueueUpload(file, parentId, (file.webkitRelativePath || file.name).split('/').pop())
  }

  transferStore.notifyQueued(fileList.length, '上传')
  visible.value = false
  event.target.value = ''
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
.upload-hint {
  padding: 10px 12px;
  border-radius: 10px;
  background-color: var(--ap-bg-page);
  border: 1px solid var(--ap-border-color);
  font-size: 12px;
  color: var(--ap-text-sub);
}
</style>
