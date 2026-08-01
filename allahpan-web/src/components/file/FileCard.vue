<template>
  <div
    class="file-card"
    :class="{ selected: !isMobile && isSelected, mobile: isMobile }"
    @contextmenu.prevent.stop="handleContextMenu"
    @click="handleClick"
    @dblclick="handleDoubleClick"
  >
    <div v-if="!isMobile" class="select-checkbox" @click.stop="$emit('toggle-select')">
      <el-checkbox :model-value="isSelected" @click.stop="$emit('toggle-select')" />
    </div>
    <button v-if="isMobile" type="button" class="more-btn" :aria-label="`${file.fileName}的更多操作`" @click.stop="handleMore">
      <el-icon size="18"><MoreFilled /></el-icon>
    </button>

    <div class="preview-area">
      <FileIcon
        :is-folder="file.isFolder === 1"
        :file-type="file.fileType"
        :file-name="file.fileName"
        :thumb-url="file.thumbnailUrl"
        :size="isMobile ? 48 : 64"
      />
    </div>

    <div class="info-area">
      <span class="file-name ap-file-name" dir="auto" :title="file.fileName">{{ file.fileName }}</span>
      <div class="meta-row">
        <ProcessBadge
          v-if="file.isFolder !== 1 && (!isMobile || file.processStatus !== 3)"
          :status="file.processStatus"
        />
        <span class="size-label">{{ formatBytes(file.fileSize) }}</span>
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
let suppressClickUntil = 0

const handleClick = () => {
  if (isMobile.value) {
    if (Date.now() < suppressClickUntil) return
    emit('open')
  } else {
    emit('toggle-select')
  }
}

const handleMore = (e) => {
  emit('contextmenu', e)
}

const handleContextMenu = (event) => {
  if (isMobile.value) suppressClickUntil = Date.now() + 700
  emit('contextmenu', event)
}

const handleDoubleClick = () => {
  if (!isMobile.value) emit('open')
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
  min-width: 0;
  height: 100%;
  box-sizing: border-box;
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
  height: 92px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.info-area {
  width: 100%;
  text-align: center;
  margin-top: 6px;
  min-width: 0;
}
.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ap-text-main);
  display: block;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
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
  padding: 10px;
  border-radius: 14px;
}
.file-card.mobile:hover {
  transform: none;
}
.file-card.mobile .preview-area {
  height: 70px;
}
.file-card.mobile .info-area {
  min-height: 70px;
  padding-bottom: 34px;
  box-sizing: border-box;
}
.file-card.mobile .file-name {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.48;
}

.more-btn {
  position: absolute;
  bottom: 4px;
  right: 4px;
  padding: 8px;
  border-radius: 8px;
  z-index: 2;
  color: var(--ap-text-sub);
  background: var(--ap-bg-card);
  border: 0;
  font: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
}

@media (hover: none) {
  .file-card:hover { transform: none; box-shadow: none; }
}
</style>
