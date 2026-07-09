<template>
  <nav class="app-tabbar safe-bottom">
    <div
      v-for="tab in tabs"
      :key="tab.path"
      class="tab-item"
      :class="{ active: route.path === tab.path }"
      @click="router.push(tab.path)"
    >
      <el-icon size="22"><component :is="tab.icon" /></el-icon>
      <span class="tab-label">{{ tab.label }}</span>
    </div>
  </nav>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { FolderOpened, Star, Delete } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/', label: '文件', icon: FolderOpened },
  { path: '/favorites', label: '收藏', icon: Star },
  { path: '/trash', label: '回收站', icon: Delete },
]
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
</style>
