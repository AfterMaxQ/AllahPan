<template>
  <nav class="breadcrumb">
    <template v-for="(node, index) in breadcrumbs" :key="node.id">
      <span v-if="index > 0" class="sep">/</span>
      <a
        href="javascript:void(0)"
        :class="{ active: index === breadcrumbs.length - 1 }"
        @click="navigateTo(node.id)"
      >
        {{ index === 0 ? '根目录' : node.fileName }}
      </a>
    </template>
  </nav>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useFileStore } from '@/stores/file'
import { getFileTree } from '@/api/file'

const fileStore = useFileStore()
const breadcrumbs = ref([{ id: 0, fileName: '根目录' }])
let treeController = null
let treeRequestId = 0

const fetchPathTree = async (folderId) => {
  const requestId = ++treeRequestId
  treeController?.abort()
  if (folderId === 0) {
    breadcrumbs.value = [{ id: 0, fileName: '根目录' }]
    return
  }
  treeController = new AbortController()
  try {
    const tree = await getFileTree(folderId, treeController.signal)
    if (requestId === treeRequestId && folderId === fileStore.currentFolderId) {
      breadcrumbs.value = [{ id: 0, fileName: '根目录' }, ...tree]
    }
  } catch (e) {
    if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
      console.error('获取面包屑失败', e)
    }
  }
}

watch(() => fileStore.currentFolderId, fetchPathTree, { immediate: true })

const navigateTo = (folderId) => {
  fileStore.navigateTo(folderId)
}

onBeforeUnmount(() => {
  treeRequestId++
  treeController?.abort()
})
</script>

<style scoped>
.breadcrumb {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-all;
}
.breadcrumb .sep {
  color: #e74c3c;
  user-select: none;
}
.breadcrumb a {
  color: var(--ap-text-sub);
  text-decoration: none;
  font-weight: normal;
  transition: color 0.2s;
}
.breadcrumb a:hover {
  color: var(--el-color-primary);
}
.breadcrumb a.active {
  color: var(--ap-text-main);
  font-weight: 600;
  cursor: default;
}
</style>
