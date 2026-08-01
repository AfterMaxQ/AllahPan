<template>
  <!-- 桌面端：跟随鼠标位置 -->
  <div
    v-if="visible && !isMobile"
    class="context-menu desktop"
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

  <!-- 移动端：底部弹出 ActionSheet -->
  <transition name="sheet-slide">
    <div v-if="visible && isMobile" class="action-sheet-overlay" @click.self="$emit('close')">
      <div class="action-sheet">
        <div class="sheet-title ap-file-name" dir="auto">{{ activeFile?.fileName || '操作' }}</div>
        <div class="sheet-item" @click="doAction('open')">
          <el-icon><FolderOpened /></el-icon>
          <span>{{ activeFile?.isFolder ? '打开文件夹' : '预览文件' }}</span>
        </div>
        <div v-if="!activeFile?.isFolder" class="sheet-item" @click="doAction('download')">
          <el-icon><Download /></el-icon>
          <span>下载</span>
        </div>
        <div class="sheet-item" @click="doAction('favorite')">
          <el-icon><Star /></el-icon>
          <span>收藏</span>
        </div>
        <div v-if="!activeFile?.isFolder" class="sheet-item" @click="doAction('share')">
          <el-icon><Share /></el-icon>
          <span>分享</span>
        </div>
        <div class="sheet-item" @click="doAction('rename')">
          <el-icon><Edit /></el-icon>
          <span>重命名</span>
        </div>
        <div class="sheet-item" @click="doAction('move')">
          <el-icon><Rank /></el-icon>
          <span>移动到</span>
        </div>
        <div class="sheet-item danger" @click="doAction('delete')">
          <el-icon><Delete /></el-icon>
          <span>删除</span>
        </div>
        <div class="sheet-cancel" @click="$emit('close')">取消</div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { FolderOpened, Download, Star, Share, Edit, Rank, Delete } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'

const { isMobile } = useResponsive()

const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  activeFile: { type: Object, default: null },
})

const emit = defineEmits(['action', 'close'])

const doAction = (action) => {
  emit('action', action)
}

const handleGlobalClick = () => {
  if (props.visible && !isMobile.value) {
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
.context-menu.desktop {
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

/* 移动端 ActionSheet */
.action-sheet-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 9999;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.action-sheet {
  width: 100%;
  max-width: 500px;
  background: var(--ap-bg-card);
  border-radius: 16px 16px 0 0;
  padding: 8px 16px calc(16px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sheet-title {
  text-align: center;
  font-size: 13px;
  color: var(--ap-text-sub);
  padding: 14px 0;
  border-bottom: 1px solid var(--ap-border-color);
  margin-bottom: 4px;
  max-height: 88px;
  overflow-y: auto;
  line-height: 1.45;
  overflow-wrap: anywhere;
  white-space: normal;
}
.sheet-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 8px;
  font-size: 15px;
  color: var(--ap-text-main);
  border-radius: 10px;
  cursor: pointer;
}
.sheet-item:active {
  background-color: var(--el-color-primary-light-9);
}
.sheet-item.danger {
  color: #f56c6c;
}
.sheet-cancel {
  text-align: center;
  font-size: 15px;
  color: var(--ap-text-sub);
  padding: 14px 0;
  border-top: 6px solid var(--ap-bg-page);
  margin: 4px -16px 0;
  cursor: pointer;
}
.sheet-cancel:active {
  background-color: var(--ap-bg-sidebar);
}

.sheet-slide-enter-active,
.sheet-slide-leave-active {
  transition: opacity 0.2s ease;
}
.sheet-slide-enter-active .action-sheet,
.sheet-slide-leave-active .action-sheet {
  transition: transform 0.2s ease;
}
.sheet-slide-enter-from,
.sheet-slide-leave-to {
  opacity: 0;
}
.sheet-slide-enter-from .action-sheet,
.sheet-slide-leave-to .action-sheet {
  transform: translateY(100%);
}
</style>
