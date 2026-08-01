<template>
  <div class="file-browser">
    <FileToolbar
      :selected-count="selectedFiles.length"
      :total-count="totalFiles"
      :view-mode="fileStore.viewMode"
      @upload="triggerUpload"
      @upload-folder="triggerUploadFolder"
      @create-folder="triggerCreateFolder"
      @batch-delete="triggerBatchDelete"
      @share="triggerShare"
      @clear-selection="selectedFiles = []"
      @view-mode-change="fileStore.setViewMode"
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
          :selected-ids="selectedFiles.map((f) => f.id)"
          @selection-change="handleListSelection"
          @item-toggle-select="toggleItemSelection"
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
    <el-pagination
      v-if="totalFiles > pageSize"
      class="file-pagination"
      background
      layout="prev, pager, next, total"
      :current-page="pageNum"
      :page-size="pageSize"
      :total="totalFiles"
      @current-change="handlePageChange"
    />

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
    <el-dialog
      v-model="shareVisible"
      title="分享文件"
      width="min(460px, calc(100vw - 24px))"
      destroy-on-close
    >
      <div class="share-box">
        <p class="share-file-name ap-file-name" dir="auto" :title="shareFileName">{{ shareFileName }}</p>
        <p>通过以下链接即可访问该文件：</p>
        <el-input :model-value="shareLink" readonly class="share-input">
          <template #append>
            <el-button @click="copyShareLink">复制</el-button>
          </template>
        </el-input>
        <p class="expire-tip">有效期至：{{ shareExpireTime }}</p>
      </div>
      <template #footer>
        <div class="share-actions">
          <el-button @click="shareVisible = false">关闭</el-button>
          <el-button type="danger" plain :loading="shareCanceling" @click="cancelCurrentShare">
            取消此分享
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 移动文件对话框 -->
    <MoveFileDialog ref="moveDialogRef" @confirm="handleMoveConfirm" />

    <!-- 移动端 FAB -->
    <template v-if="isMobile">
      <transition name="fade-transform">
        <div v-if="fabOpen" class="fab-overlay" @click="fabOpen = false" />
      </transition>
      <div class="fab-container">
        <transition name="fade-transform">
          <div v-if="fabOpen" class="fab-menu">
            <div class="fab-item" @click="triggerUpload(); fabOpen = false">
              <span class="fab-label">上传文件</span>
              <div class="fab-btn mini"><el-icon><Upload /></el-icon></div>
            </div>
            <div class="fab-item" @click="triggerUploadFolder(); fabOpen = false">
              <span class="fab-label">上传文件夹</span>
              <div class="fab-btn mini"><el-icon><FolderOpened /></el-icon></div>
            </div>
            <div class="fab-item" @click="triggerCreateFolder(); fabOpen = false">
              <span class="fab-label">新建文件夹</span>
              <div class="fab-btn mini"><el-icon><FolderAdd /></el-icon></div>
            </div>
          </div>
        </transition>
        <div class="fab-btn main" @click="fabOpen = !fabOpen">
          <el-icon size="24"><Plus /></el-icon>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useFileStore } from '@/stores/file'
import { useTransferStore } from '@/stores/transfer'
import { getFilePage, deleteFile, batchDeleteFiles, renameFile, moveFile } from '@/api/file'
import { addFavorite } from '@/api/favorite'
import { createShareLink, deleteShareLink } from '@/api/share'
import { formatDate } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, FolderOpened, FolderAdd } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import { useFileWatcher } from '@/composables/useFileWatcher'

import FileToolbar from '@/components/file/FileToolbar.vue'
import FileGridView from '@/components/file/FileGridView.vue'
import FileListView from '@/components/file/FileListView.vue'
import FileContextMenu from '@/components/file/FileContextMenu.vue'
import FileUploadDialog from '@/components/file/FileUploadDialog.vue'
import FolderCreateDialog from '@/components/file/FolderCreateDialog.vue'
import FilePreviewDialog from '@/components/file/FilePreviewDialog.vue'
import MoveFileDialog from '@/components/file/MoveFileDialog.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const fileStore = useFileStore()
const transferStore = useTransferStore()
const { isMobile } = useResponsive()

const loading = ref(false)
const fabOpen = ref(false)
const files = ref([])
const selectedFiles = ref([])
const pageNum = ref(1)
const pageSize = 100
const totalFiles = ref(0)

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const rightClickedFile = ref(null)

// 对话框引用
const uploadDialogRef = ref(null)
const folderDialogRef = ref(null)
const previewDialogRef = ref(null)
const moveDialogRef = ref(null)

// 分享
const shareVisible = ref(false)
const shareLink = ref('')
const shareExpireTime = ref('')
const shareFileName = ref('')
const shareCode = ref('')
const shareCanceling = ref(false)

// 移动
const pendingMoveFile = ref(null)
let loadController = null
let loadRequestId = 0
let realtimeReloadTimer = null
let lastLoadedAt = 0

const loadData = async () => {
  const requestId = ++loadRequestId
  loadController?.abort()
  loadController = new AbortController()
  const folderId = fileStore.currentFolderId
  loading.value = true
  selectedFiles.value = []
  try {
    const result = await getFilePage(folderId, pageNum.value, pageSize, loadController.signal)
    if (requestId === loadRequestId && folderId === fileStore.currentFolderId) {
      files.value = result.list || []
      totalFiles.value = Number(result.total || 0)
      lastLoadedAt = Date.now()
    }
  } catch (e) {
    if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
      console.error('加载文件列表失败', e)
    }
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

watch(() => fileStore.currentFolderId, () => {
  pageNum.value = 1
  loadData()
}, { immediate: true })
watch(() => fileStore.refreshTrigger, () => loadData())

const handlePageChange = (page) => {
  pageNum.value = page
  loadData()
}

// 只响应当前目录相关事件，并合并短时间内的多阶段状态推送。
useFileWatcher((event) => {
  const currentFolderId = Number(fileStore.currentFolderId || 0)
  const eventParentId = Number(event?.parentId ?? -1)
  if (event?.type !== 'sync' && eventParentId !== currentFolderId) return
  if (Date.now() - lastLoadedAt < 400) return
  if (realtimeReloadTimer) clearTimeout(realtimeReloadTimer)
  realtimeReloadTimer = setTimeout(loadData, 150)
})

onBeforeUnmount(() => {
  loadRequestId++
  if (realtimeReloadTimer) clearTimeout(realtimeReloadTimer)
  loadController?.abort()
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

// 桌面端选择
const toggleItemSelection = (file) => {
  if (isMobile.value) return
  const idx = selectedFiles.value.findIndex((f) => f.id === file.id)
  if (idx > -1) {
    selectedFiles.value.splice(idx, 1)
  } else {
    selectedFiles.value.push(file)
  }
}

const handleListSelection = (selection) => {
  if (isMobile.value) return
  selectedFiles.value = selection
}

// 打开文件/文件夹
const handleItemOpen = (file) => {
  if (file.isFolder === 1) {
    fileStore.navigateTo(file.id)
  } else {
    previewDialogRef.value?.open(file)
  }
}

// 移动端不提供批量选择，切换到窄屏时清理桌面端遗留的选中项。
watch(isMobile, (mobile) => {
  if (mobile) selectedFiles.value = []
})

// 右键菜单
const openContextMenu = (event, file) => {
  rightClickedFile.value = file
  contextMenuX.value = event.clientX || 0
  contextMenuY.value = event.clientY || 0
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
      case 'download':
        transferStore.enqueueDownload(file)
        transferStore.notifyQueued(1, '下载')
        break
      case 'favorite':
        await addFavorite(file.id)
        ElMessage.success('已加入收藏')
        break
      case 'share': {
        await openShareDialog(file)
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
        pendingMoveFile.value = file
        moveDialogRef.value.open(file.parentId)
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

const triggerShare = () => {
  if (selectedFiles.value.length !== 1) return
  openShareDialog(selectedFiles.value[0])
}

const openShareDialog = async (file) => {
  const res = await createShareLink(file.id, 24)
  shareFileName.value = file.fileName
  shareCode.value = res.shareCode
  shareLink.value = `${window.location.origin}/share/${res.shareCode}`
  shareExpireTime.value = formatDate(res.expireTime)
  shareVisible.value = true
}

const handleMoveConfirm = async (targetParentId) => {
  if (!pendingMoveFile.value) return
  try {
    await moveFile(pendingMoveFile.value.id, targetParentId)
    ElMessage.success('移动成功')
    loadData()
  } catch (e) {
    console.error('移动失败', e)
    ElMessage.error('移动失败，请重试')
  } finally {
    pendingMoveFile.value = null
  }
}

const copyShareLink = async () => {
  try {
    let copied = false
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(shareLink.value)
        copied = true
      } catch {
        // 非 HTTPS、权限被拒绝等情况下继续尝试兼容复制。
      }
    }
    if (!copied) {
      const textarea = document.createElement('textarea')
      textarea.value = shareLink.value
      textarea.setAttribute('readonly', '')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      try {
        textarea.select()
        copied = document.execCommand('copy')
      } finally {
        document.body.removeChild(textarea)
      }
      if (!copied) throw new Error('复制失败')
    }
    ElMessage.success('链接已复制到剪贴板')
  } catch {
    ElMessage.error('无法自动复制，请长按链接手动复制')
  }
}

const cancelCurrentShare = async () => {
  if (!shareCode.value || shareCanceling.value) return
  shareCanceling.value = true
  try {
    await deleteShareLink(shareCode.value)
    shareVisible.value = false
    shareCode.value = ''
    shareLink.value = ''
    shareExpireTime.value = ''
    shareFileName.value = ''
    ElMessage.success('分享已取消，原链接立即失效')
  } finally {
    shareCanceling.value = false
  }
}
</script>

<style scoped>
.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  justify-content: center;
}
.share-box {
  padding: 8px 0;
}
.share-input {
  margin: 16px 0;
}
.share-file-name {
  margin: 0 0 8px;
  color: var(--ap-text-main);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
}
.expire-tip {
  font-size: 12px;
  color: var(--ap-text-sub);
}
.share-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 768px) {
  .share-actions :deep(.el-button) {
    min-height: 42px;
  }
}

/* FAB */
.fab-overlay {
  position: fixed;
  inset: 0;
  background: rgba(61, 50, 38, 0.22);
  backdrop-filter: blur(2px);
  z-index: 1200;
}
.fab-container {
  position: fixed;
  bottom: calc(72px + env(safe-area-inset-bottom, 0px));
  right: 16px;
  z-index: 1201;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}
.fab-menu {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 12px;
}
.fab-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.fab-label {
  font-size: 13px;
  color: var(--ap-text-main);
  background: var(--ap-bg-card);
  padding: 6px 12px;
  border: 1px solid var(--ap-border-color);
  border-radius: 10px;
  box-shadow: 0 4px 14px rgba(61, 50, 38, 0.1);
}
.fab-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(111, 75, 47, 0.24);
  color: #fff;
}
.fab-btn.main {
  width: 56px;
  height: 56px;
  background: var(--el-color-primary);
  transition: transform 0.2s;
}
.fab-btn.mini {
  background: var(--el-color-primary-light-3);
  width: 42px;
  height: 42px;
}

.file-pagination {
  display: flex;
  justify-content: center;
  margin-top: 22px;
}

@media (max-width: 768px) {
  .file-browser { padding-bottom: 74px; }
  .empty-actions { gap: 8px; }
  .empty-actions :deep(.el-button) { width: 100%; margin-left: 0; }
  .file-pagination { margin-top: 16px; overflow-x: auto; justify-content: flex-start; padding-bottom: 4px; }
}
</style>
