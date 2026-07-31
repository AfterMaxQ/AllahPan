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
import { ref, watch } from 'vue'
import { useFileStore } from '@/stores/file'
import { getFileTree } from '@/api/file'

const fileStore = useFileStore()
const breadcrumbs = ref([{ id: 0, fileName: '根目录' }])

const fetchPathTree = async (folderId) => {
  if (folderId === 0) {
    breadcrumbs.value = [{ id: 0, fileName: '根目录' }]
    return
  }
  try {
    const tree = await getFileTree(folderId)
    breadcrumbs.value = [{ id: 0, fileName: '根目录' }, ...tree]
  } catch (e) {
    console.error('获取面包屑失败', e)
  }
}

watch(() => fileStore.currentFolderId, fetchPathTree, { immediate: true })

const navigateTo = (folderId) => {
  fileStore.navigateTo(folderId)
}
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
