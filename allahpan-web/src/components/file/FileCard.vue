<template>
  <div
    class="file-card"
    :class="{ selected: isSelected, mobile: isMobile }"
    @contextmenu.prevent="$emit('contextmenu', $event)"
    @click="handleClick"
    @dblclick="$emit('open')"
  >
    <div class="select-checkbox" @click.stop="$emit('toggle-select')">
      <el-checkbox :model-value="isSelected" @click.stop="$emit('toggle-select')" />
    </div>
    <div v-if="isMobile" class="more-btn" @click.stop="handleMore">
      <el-icon size="18"><MoreFilled /></el-icon>
    </div>

    <div class="preview-area">
      <FileIcon
        :is-folder="file.isFolder === 1"
        :file-type="file.fileType"
        :thumb-url="file.thumbnailUrl"
        :size="isMobile ? 48 : 64"
      />
    </div>

    <div class="info-area">
      <span class="file-name" :title="file.fileName">{{ file.fileName }}</span>
      <div class="meta-row">
        <ProcessBadge v-if="file.isFolder !== 1" :status="file.processStatus" />
        <span v-if="file.isFolder !== 1" class="size-label">{{ formatBytes(file.fileSize) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { MoreFilled } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import FileIcon from '@/components/common/FileIcon.vue'
import ProcessBadge from '@/components/common/ProcessBadge.vue'
import { formatBytes } from '@/utils/format'

defineProps({
  file: { type: Object, required: true },
  isSelected: { type: Boolean, default: false },
})
const emit = defineEmits(['contextmenu', 'toggle-select', 'open'])

const { isMobile } = useResponsive()

const handleClick = () => {
  if (isMobile.value) {
    emit('open')
  } else {
    emit('toggle-select')
  }
}

const handleMore = (e) => {
  emit('contextmenu', e)
}
</script>

<style scoped>
.file-card {
  background-color: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 16px;
  padding: 12px;
  position: relative;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1),
              box-shadow 0.2s ease,
              border-color 0.2s ease;
}
.file-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(61, 50, 38, 0.06);
  border-color: var(--el-color-primary-light-5);
}
.file-card.selected {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}
.select-checkbox {
  position: absolute;
  top: 2px;
  left: 2px;
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  opacity: 0;
  transition: opacity 0.2s, background-color 0.2s;
  z-index: 2;
  cursor: pointer;
}
.select-checkbox:hover {
  background-color: var(--el-color-primary-light-9);
}
.select-checkbox :deep(.el-checkbox) {
  height: auto;
}
.file-card:hover .select-checkbox,
.file-card.selected .select-checkbox {
  opacity: 1;
}
.preview-area {
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.info-area {
  width: 100%;
  text-align: center;
  margin-top: 8px;
}
.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ap-text-main);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-row {
  margin-top: 4px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--ap-text-sub);
}

/* 移动端 */
.file-card.mobile {
  padding: 8px;
  border-radius: 12px;
}
.file-card.mobile:hover {
  transform: none;
}
.file-card.mobile .select-checkbox {
  opacity: 1;
}
.file-card.mobile .preview-area {
  height: 64px;
}

.more-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  padding: 8px;
  border-radius: 8px;
  z-index: 2;
  color: var(--ap-text-sub);
  background: var(--ap-bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
}
</style>
