<template>
  <el-dialog
    v-model="visible"
    title="移动到..."
    width="500px"
    destroy-on-close
    @close="handleClose"
  >
    <!-- 面包屑 -->
    <div class="move-breadcrumb">
      <el-button link type="primary" @click="navigateTo(0)">根目录</el-button>
      <template v-for="(crumb, i) in breadcrumbs" :key="crumb.id">
        <span class="sep">&gt;</span>
        <el-button link type="primary" @click="navigateTo(crumb.id)">{{ crumb.fileName }}</el-button>
      </template>
    </div>

    <!-- 当前目录的文件夹列表 -->
    <div class="move-folder-list">
      <el-empty v-if="folders.length === 0 && !loading" description="当前目录下无文件夹">
        <el-button type="primary" @click="confirmMove(0)">移动到根目录</el-button>
      </el-empty>
      <div
        v-for="folder in folders"
        :key="folder.id"
        class="move-folder-item"
        @dblclick="navigateTo(folder.id)"
      >
        <el-icon :size="20" color="#409EFF"><FolderOpened /></el-icon>
        <span class="folder-name ap-file-name" dir="auto" :title="folder.fileName">{{ folder.fileName }}</span>
        <el-button size="small" type="primary" @click.stop="confirmMove(folder.id)">移动到此</el-button>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="confirmMove(currentParentId)">移动到当前目录</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { getFileList, getFileTree } from '@/api/file'
import { FolderOpened } from '@element-plus/icons-vue'

const emit = defineEmits(['confirm'])

const visible = ref(false)
const loading = ref(false)
const folders = ref([])
const currentParentId = ref(0)
const breadcrumbs = ref([])
let navigationController = null
let navigationRequestId = 0

const navigateTo = async (parentId) => {
  const requestId = ++navigationRequestId
  navigationController?.abort()
  navigationController = new AbortController()
  loading.value = true
  currentParentId.value = parentId
  try {
    let nextBreadcrumbs = []
    if (parentId > 0) {
      nextBreadcrumbs = await getFileTree(parentId, navigationController.signal)
    }
    const all = await getFileList(parentId, navigationController.signal)
    if (requestId === navigationRequestId) {
      breadcrumbs.value = nextBreadcrumbs
      folders.value = (all || []).filter(f => f.isFolder === 1 || f.isFolder === true)
    }
  } catch (e) {
    if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
      console.error('加载文件夹失败', e)
      if (requestId === navigationRequestId) folders.value = []
    }
  } finally {
    if (requestId === navigationRequestId) loading.value = false
  }
}

const confirmMove = (targetId) => {
  visible.value = false
  emit('confirm', targetId)
}

const handleClose = () => {
  navigationRequestId++
  navigationController?.abort()
  folders.value = []
  breadcrumbs.value = []
  currentParentId.value = 0
}

const open = (currentFileParentId) => {
  // 从当前文件的父目录开始，避免移动到自己所在目录
  navigateTo(currentFileParentId || 0)
  visible.value = true
}

defineExpose({ open })
</script>

<style scoped>
.move-breadcrumb {
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.move-breadcrumb .sep {
  color: #999;
}
.move-folder-list {
  max-height: 300px;
  overflow-y: auto;
}
.move-folder-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
}
.move-folder-item:hover {
  background: #f5f7fa;
}
.folder-name {
  flex: 1;
  padding-top: 5px;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
}
</style>
