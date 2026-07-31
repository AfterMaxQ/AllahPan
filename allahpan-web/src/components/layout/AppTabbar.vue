<template>
  <nav class="app-tabbar safe-bottom">
    <div
      class="tab-item"
      :class="{ active: route.path === '/' }"
      @click="router.push('/')"
    >
      <el-icon size="22"><FolderOpened /></el-icon>
      <span class="tab-label">文件</span>
    </div>
    <el-radio-group
      :model-value="fileStore.viewMode"
      size="small"
      class="view-toggle"
      @change="fileStore.toggleViewMode"
    >
      <el-radio-button value="grid">
        <el-icon size="16"><Grid /></el-icon>
      </el-radio-button>
      <el-radio-button value="list">
        <el-icon size="16"><List /></el-icon>
      </el-radio-button>
    </el-radio-group>
    <div
      class="tab-item"
      :class="{ active: route.path === '/favorites' }"
      @click="router.push('/favorites')"
    >
      <el-icon size="22"><Star /></el-icon>
      <span class="tab-label">收藏</span>
    </div>
    <div
      class="tab-item"
      :class="{ active: route.path === '/trash' }"
      @click="router.push('/trash')"
    >
      <el-icon size="22"><Delete /></el-icon>
      <span class="tab-label">回收站</span>
    </div>
  </nav>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { FolderOpened, Star, Delete, Grid, List } from '@element-plus/icons-vue'
import { useFileStore } from '@/stores/file'

const route = useRoute()
const router = useRouter()
const fileStore = useFileStore()
</script>

<style scoped>
.app-tabbar {
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: 56px;
  background: var(--ap-bg-card);
  border-top: 1px solid var(--ap-border-color);
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2100;
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  color: var(--ap-text-sub);
  transition: color 0.2s;
  padding: 4px 16px;
  border-radius: 8px;
}

.tab-item.active {
  color: var(--el-color-primary);
  font-weight: 600;
}

.tab-label {
  font-size: 11px;
  line-height: 1;
}
.view-toggle {
  flex-shrink: 0;
}
</style>
