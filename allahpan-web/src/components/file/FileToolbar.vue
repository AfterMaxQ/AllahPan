<template>
  <section class="toolbar" :class="{ mobile: isMobile }" aria-label="文件操作工具栏">
    <div v-if="!isMobile" class="primary-actions">
      <el-button type="primary" :icon="Upload" @click="$emit('upload')">上传文件</el-button>
      <el-button :icon="FolderOpened" @click="$emit('upload-folder')">上传文件夹</el-button>
      <el-button :icon="FolderAdd" @click="$emit('create-folder')">新建文件夹</el-button>
    </div>

    <div v-else-if="selectedCount === 0" class="mobile-summary">
      <strong>{{ totalCount }} 项</strong>
      <span>{{ viewMode === 'grid' ? '网格视图' : '列表视图' }}</span>
    </div>

    <div class="toolbar-right">
      <span v-if="!isMobile" class="item-count">{{ totalCount }} 项</span>
      <transition name="toolbar-fade">
        <div v-if="selectedCount > 0" class="selection-actions">
          <el-button
            class="clear-selection"
            text
            :icon="Close"
            :aria-label="`取消选择的${selectedCount}项`"
            @click="$emit('clear-selection')"
          >
            <span v-if="!isMobile">取消选择</span>
          </el-button>
          <el-button
            v-if="!isMobile && selectedCount === 1"
            plain
            :icon="Share"
            @click="$emit('share')"
          >
            分享
          </el-button>
          <el-button
            type="danger"
            plain
            :icon="Delete"
            :size="isMobile ? 'small' : 'default'"
            @click="$emit('batch-delete')"
          >
            删除 {{ selectedCount }} 项
          </el-button>
        </div>
      </transition>

      <div class="view-switch" role="group" aria-label="切换文件显示模式">
        <button
          type="button"
          class="view-button"
          :class="{ active: viewMode === 'grid' }"
          :aria-pressed="viewMode === 'grid'"
          title="网格模式"
          @click="$emit('view-mode-change', 'grid')"
        >
          <el-icon><Grid /></el-icon>
          <span>网格</span>
        </button>
        <button
          type="button"
          class="view-button"
          :class="{ active: viewMode === 'list' }"
          :aria-pressed="viewMode === 'list'"
          title="列表模式"
          @click="$emit('view-mode-change', 'list')"
        >
          <el-icon><List /></el-icon>
          <span>列表</span>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { Upload, FolderAdd, FolderOpened, Delete, Grid, List, Close, Share } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'

defineProps({
  selectedCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  viewMode: { type: String, default: 'grid' },
})
defineEmits(['upload', 'upload-folder', 'create-folder', 'batch-delete', 'clear-selection', 'view-mode-change', 'share'])

const { isMobile } = useResponsive()
</script>

<style scoped>
.toolbar {
  position: relative;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 64px;
  padding: 10px 12px;
  margin-bottom: 16px;
  box-sizing: border-box;
  border: 1px solid var(--ap-border-color);
  border-radius: 16px;
  background: color-mix(in srgb, var(--ap-bg-card) 94%, var(--ap-bg-sidebar));
  box-shadow: 0 4px 16px rgba(61, 50, 38, .035);
}
.primary-actions, .toolbar-right { display: flex; align-items: center; gap: 10px; }
.selection-actions { display: flex; align-items: center; gap: 4px; }
.selection-actions :deep(.el-button + .el-button) { margin-left: 0; }
.clear-selection { color: var(--ap-text-sub); }
.toolbar-right { margin-left: auto; }
.item-count { padding-right: 4px; color: var(--ap-text-sub); font-size: 12px; white-space: nowrap; }
.view-switch { display: flex; gap: 3px; padding: 3px; border: 1px solid var(--ap-border-color); border-radius: 11px; background: var(--ap-bg-sidebar); }
.view-button { display: inline-flex; min-width: 68px; height: 34px; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: 0; border-radius: 8px; background: transparent; color: var(--ap-text-sub); font: inherit; font-size: 12px; cursor: pointer; transition: color .18s ease, background .18s ease, box-shadow .18s ease; }
.view-button:hover { color: var(--el-color-primary-dark-2); }
.view-button.active { background: var(--ap-bg-card); color: var(--el-color-primary-dark-2); font-weight: 600; box-shadow: 0 2px 7px rgba(61, 50, 38, .09); }
.toolbar-fade-enter-active, .toolbar-fade-leave-active { transition: opacity .18s ease, transform .18s ease; }
.toolbar-fade-enter-from, .toolbar-fade-leave-to { opacity: 0; transform: translateX(6px); }

@media (max-width: 768px) {
  .toolbar.mobile { position: relative; top: auto; min-height: 54px; gap: 8px; padding: 7px 8px 7px 12px; margin: -2px 0 10px; border-radius: 13px; box-shadow: 0 4px 14px rgba(61, 50, 38, .055); }
  .mobile-summary { display: flex; min-width: 0; flex-direction: column; }
  .mobile-summary strong { color: var(--ap-text-main); font-size: 13px; line-height: 1.25; }
  .mobile-summary span { color: var(--ap-text-sub); font-size: 10px; line-height: 1.35; }
  .toolbar-right { gap: 6px; }
  .selection-actions { gap: 1px; }
  .clear-selection { width: 44px; min-width: 44px; padding: 0; }
  .view-switch { padding: 2px; }
  .view-button { min-width: 48px; height: 38px; flex-direction: column; gap: 1px; padding: 2px 6px; font-size: 9px; }
  .view-button :deep(.el-icon) { font-size: 16px; }
}

@media (min-width: 769px) and (max-width: 1100px) {
  .toolbar { flex-wrap: wrap; }
  .primary-actions { flex: 1 1 auto; }
  .primary-actions :deep(.el-button) { padding-right: 11px; padding-left: 11px; }
  .toolbar-right { flex: 0 0 auto; }
}

@supports not (color: color-mix(in srgb, white, black)) {
  .toolbar { background: var(--ap-bg-card); }
}
</style>
