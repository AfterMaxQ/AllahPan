<template>
  <div
    v-if="visible"
    class="context-menu"
    :style="{ top: y + 'px', left: x + 'px' }"
  >
    <div class="menu-item" @click="$emit('action', 'open')">
      <el-icon><FolderOpened /></el-icon>
      <span>{{ activeFile?.isFolder ? '打开' : '预览' }}</span>
    </div>
    <div v-if="!activeFile?.isFolder" class="menu-item" @click="$emit('action', 'download')">
      <el-icon><Download /></el-icon>
      <span>下载</span>
    </div>
    <div class="menu-item" @click="$emit('action', 'favorite')">
      <el-icon><Star /></el-icon>
      <span>收藏</span>
    </div>
    <div v-if="!activeFile?.isFolder" class="menu-item" @click="$emit('action', 'share')">
      <el-icon><Share /></el-icon>
      <span>分享</span>
    </div>
    <div class="menu-item" @click="$emit('action', 'rename')">
      <el-icon><Edit /></el-icon>
      <span>重命名</span>
    </div>
    <div class="menu-item" @click="$emit('action', 'move')">
      <el-icon><Rank /></el-icon>
      <span>移动到</span>
    </div>
    <div class="divider" />
    <div class="menu-item danger" @click="$emit('action', 'delete')">
      <el-icon><Delete /></el-icon>
      <span>删除</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { FolderOpened, Download, Star, Share, Edit, Rank, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  activeFile: { type: Object, default: null },
})

const emit = defineEmits(['action', 'close'])

const handleGlobalClick = () => {
  if (props.visible) {
    emit('close')
  }
}

onMounted(() => {
  document.addEventListener('click', handleGlobalClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
})
</script>

<style scoped>
.context-menu {
  position: fixed;
  background-color: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(61, 50, 38, 0.1);
  padding: 6px;
  z-index: 9999;
  min-width: 150px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--ap-text-main);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.menu-item:hover {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.menu-item.danger {
  color: #f56c6c;
}
.menu-item.danger:hover {
  background-color: #fef0f0;
  color: #f56c6c;
}
.divider {
  height: 1px;
  background-color: var(--ap-border-color);
  margin: 4px 8px;
}
</style>
