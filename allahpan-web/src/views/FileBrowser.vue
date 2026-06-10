<template>
  <div class="file-browser">
    <!-- 工具栏 -->
    <FileToolbar
      :selected-count="selectedFiles.length"
      @upload="triggerUpload"
      @upload-folder="triggerUploadFolder"
      @create-folder="triggerCreateFolder"
      @batch-delete="triggerBatchDelete"
    />

    <!-- 文件列表 -->
    <el-skeleton :rows="6" animated :loading="loading">
      <template v-if="files.length > 0">
        <FileGridView
          v-if="fileStore.viewMode === 'grid'"
          :files="files"
          :selected-ids="selectedFiles.map((f) => f.id)"
          @item-contextmenu="openContextMenu"
          @item-toggle-select="toggleItemSelection"
          @item-open="handleItemOpen"
        />
        <FileListView
          v-else
          :files="files"
          @selection-change="handleListSelection"
          @item-contextmenu="openContextMenu"
          @item-open="handleItemOpen"
        />
      </template>
      <EmptyState v-else>
        <template #action>
          <div class="empty-actions">
            <el-button type="primary" :icon="Upload" size="large" @click="triggerUpload">上传文件</el-button>
            <el-button :icon="FolderOpened" size="large" @click="triggerUploadFolder">上传文件夹</el-button>
            <el-button :icon="FolderAdd" size="large" @click="triggerCreateFolder">新建文件夹</el-button>
          </div>
        </template>
      </EmptyState>
    </el-skeleton>

    <!-- 右键菜单 -->
    <FileContextMenu
      :visible="contextMenuVisible"
      :x="contextMenuX"
      :y="contextMenuY"
      :active-file="rightClickedFile"
      @action="handleMenuAction"
      @close="contextMenuVisible = false"
    />

    <!-- 对话框 -->
    <FileUploadDialog ref="uploadDialogRef" @uploaded="loadData" />
    <FolderCreateDialog ref="folderDialogRef" @created="loadData" />
    <FilePreviewDialog ref="previewDialogRef" />

    <!-- 分享链接弹窗 -->
    <el-dialog v-model="shareVisible" title="分享文件" width="460px" destroy-on-close>
      <div class="share-box">
        <p>通过以下链接即可访问该文件：</p>
        <el-input :model-value="shareLink" readonly class="share-input">
          <template #append>
            <el-button @click="copyShareLink">复制</el-button>
          </template>
        </el-input>
        <p class="expire-tip">有效期至：{{ shareExpireTime }}</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useFileStore } from '@/stores/file'
import { getFileList, deleteFile, batchDeleteFiles, getDownloadUrl, renameFile } from '@/api/file'
import { addFavorite } from '@/api/favorite'
import { createShareLink } from '@/api/share'
import { formatDate } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, FolderOpened, FolderAdd } from '@element-plus/icons-vue'
import { useFileWatcher } from '@/composables/useFileWatcher'

import FileToolbar from '@/components/file/FileToolbar.vue'
import FileGridView from '@/components/file/FileGridView.vue'
import FileListView from '@/components/file/FileListView.vue'
import FileContextMenu from '@/components/file/FileContextMenu.vue'
import FileUploadDialog from '@/components/file/FileUploadDialog.vue'
import FolderCreateDialog from '@/components/file/FolderCreateDialog.vue'
import FilePreviewDialog from '@/components/file/FilePreviewDialog.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const fileStore = useFileStore()

const loading = ref(false)
const files = ref([])
const selectedFiles = ref([])

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const rightClickedFile = ref(null)

// 对话框引用
const uploadDialogRef = ref(null)
const folderDialogRef = ref(null)
const previewDialogRef = ref(null)

// 分享
const shareVisible = ref(false)
const shareLink = ref('')
const shareExpireTime = ref('')

const loadData = async () => {
  loading.value = true
  selectedFiles.value = []
  try {
    files.value = await getFileList(fileStore.currentFolderId)
  } catch (e) {
    console.error('加载文件列表失败', e)
  } finally {
    loading.value = false
  }
}

watch(() => fileStore.currentFolderId, loadData, { immediate: true })

// 实时文件变更监听（SSE）
useFileWatcher(() => {
  loadData()
})

// 上传 & 新建文件夹
const triggerUpload = () => uploadDialogRef.value?.open()
const triggerUploadFolder = () => uploadDialogRef.value?.openFolder()
const triggerCreateFolder = () => folderDialogRef.value?.open()

// 批量删除
const triggerBatchDelete = () => {
  if (selectedFiles.value.length === 0) return
  ElMessageBox.confirm(
    `确定要删除这 ${selectedFiles.value.length} 个文件吗？`,
    '批量删除',
    { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
  ).then(async () => {
    try {
      const ids = selectedFiles.value.map((f) => f.id)
      await batchDeleteFiles(ids)
      ElMessage.success('已删除')
      loadData()
    } catch (e) { /* 拦截器统一处理 */ }
  }).catch(() => {})
}

// 选择
const toggleItemSelection = (file) => {
  const idx = selectedFiles.value.findIndex((f) => f.id === file.id)
  if (idx > -1) {
    selectedFiles.value.splice(idx, 1)
  } else {
    selectedFiles.value.push(file)
  }
}

const handleListSelection = (selection) => {
  selectedFiles.value = selection
}

// 打开文件/文件夹
const handleItemOpen = (file) => {
  if (file.isFolder === 1) {
    fileStore.setCurrentFolder(file.id)
  } else {
    previewDialogRef.value?.open(file)
  }
}

// 右键菜单
const openContextMenu = (event, file) => {
  rightClickedFile.value = file
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuVisible.value = true
}

const handleMenuAction = async (action) => {
  const file = rightClickedFile.value
  if (!file) return
  contextMenuVisible.value = false

  try {
    switch (action) {
      case 'open':
        handleItemOpen(file)
        break
      case 'download': {
        const res = await getDownloadUrl(file.id)
        window.open(res.downloadUrl, '_blank')
        break
      }
      case 'favorite':
        await addFavorite(file.id)
        ElMessage.success('已加入收藏')
        break
      case 'share': {
        const res = await createShareLink(file.id, 24)
        shareLink.value = `${window.location.origin}/share/${res.shareCode}`
        shareExpireTime.value = formatDate(res.expireTime)
        shareVisible.value = true
        break
      }
      case 'rename': {
        const { value } = await ElMessageBox.prompt('请输入新名称', '重命名', {
          inputValue: file.fileName,
          confirmButtonText: '确定',
          cancelButtonText: '取消',
        })
        if (value?.trim()) {
          await renameFile(file.id, value.trim())
          ElMessage.success('重命名成功')
          loadData()
        }
        break
      }
      case 'move':
        ElMessage.info('移动功能请在后续版本中使用')
        break
      case 'delete':
        await ElMessageBox.confirm(
          `确定要删除「${file.fileName}」吗？`,
          '删除文件',
          { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
        )
        await deleteFile(file.id)
        ElMessage.success('已移入垃圾站')
        loadData()
        break
    }
  } catch (e) {
    if (e !== 'cancel') console.error('操作失败', e)
  }
}

const copyShareLink = () => {
  navigator.clipboard.writeText(shareLink.value)
  ElMessage.success('链接已复制到剪贴板')
}
</script>

<style scoped>
.empty-actions {
  display: flex;
  gap: 20px;
  justify-content: center;
}
.share-box {
  padding: 8px 0;
}
.share-input {
  margin: 16px 0;
}
.expire-tip {
  font-size: 12px;
  color: var(--ap-text-sub);
}
</style>
