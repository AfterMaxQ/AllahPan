<template>
  <nav class="breadcrumb">
    <span
      v-for="(node, index) in breadcrumbs"
      :key="node.id"
      class="crumb-group"
      :class="{ current: index === breadcrumbs.length - 1 }"
    >
      <a
        href="javascript:void(0)"
        :class="{ active: index === breadcrumbs.length - 1 }"
        dir="auto"
        :title="index === 0 ? '根目录' : node.fileName"
        @click="navigateTo(node.id)"
      >
        <span v-if="index > 0" class="sep" aria-hidden="true">/</span>{{ index === 0 ? '根目录' : node.fileName }}
      </a>
    </span>
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
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
  scrollbar-width: none;
  white-space: nowrap;
}
.breadcrumb::-webkit-scrollbar { display: none; }
.crumb-group {
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  flex: 0 0 auto;
  align-items: baseline;
  gap: 5px;
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
  white-space: nowrap;
}
.breadcrumb a:hover {
  color: var(--el-color-primary);
}
.breadcrumb a.active {
  color: var(--ap-text-main);
  font-weight: 600;
  cursor: default;
}
@media (max-width: 768px) {
  .breadcrumb {
    display: block;
    flex: 1;
    overflow: visible;
    font-size: 12.5px;
    line-height: 17px;
    white-space: normal;
  }
  .crumb-group {
    display: inline;
    min-width: 0;
    min-height: 0;
    max-width: none;
  }
  .crumb-group.current {
    min-width: 0;
    max-width: none;
  }
  .breadcrumb a {
    display: inline;
    min-width: 0;
    min-height: 0;
    max-width: none;
    overflow: visible;
    overflow-wrap: anywhere;
    white-space: normal;
    line-height: inherit;
    unicode-bidi: isolate;
  }
  .breadcrumb .sep {
    display: inline;
    margin: 0 3px;
    line-height: inherit;
  }
}
</style>
