<template>
  <div class="result-item" @click="$emit('click')">
    <div class="item-main">
      <div class="title-section">
        <FileIcon
          :is-folder="false"
          :file-type="item.fileType"
          :size="32"
        />
        <span class="name-highlight" v-html="item.fileNameHighlight || item.fileName" />
        <span class="path">{{ item.filePath }}</span>
      </div>
      <div v-if="item.contentSnippets?.length" class="text-snippets">
        <div class="snippets-label">匹配内容</div>
        <div
          v-for="(snippet, idx) in item.contentSnippets"
          :key="idx"
          class="snippet"
          v-html="snippet"
        />
      </div>
    </div>
    <div class="item-meta">
      <span>{{ formatBytes(item.fileSize) }}</span>
      <span>{{ formatDate(item.createTime) }}</span>
    </div>
  </div>
</template>

<script setup>
import FileIcon from '@/components/common/FileIcon.vue'
import { formatBytes, formatDate } from '@/utils/format'

defineProps({
  item: { type: Object, required: true },
})
defineEmits(['click'])
</script>

<style scoped>
.result-item {
  background-color: var(--ap-bg-card);
  border: 1px solid var(--ap-border-color);
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.result-item:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 4px 12px rgba(61, 50, 38, 0.04);
}
.title-section {
  display: flex;
  align-items: center;
  gap: 12px;
}
.name-highlight {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-primary-dark-2);
}
.name-highlight :deep(mark) {
  background-color: var(--el-color-primary-light-7);
  color: var(--el-color-primary-dark-2);
  padding: 0 2px;
  border-radius: 2px;
}
.path {
  font-size: 12px;
  color: var(--ap-text-sub);
}
.text-snippets {
  background-color: var(--ap-bg-page);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.snippet {
  font-size: 13px;
  line-height: 1.6;
  color: var(--ap-text-main);
}
.snippets-label {
  font-size: 11px;
  color: var(--ap-text-sub);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}
.snippet :deep(mark) {
  background-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary-dark-2);
  padding: 0 2px;
  border-radius: 2px;
}
.item-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--ap-text-sub);
}
</style>
