<template>
  <div class="transfer-task" :class="task.status">
    <div class="task-head">
      <div class="task-name ap-file-name" dir="auto" :title="task.name">{{ task.name }}</div>
      <span class="task-status">{{ statusText }}</span>
    </div>

    <el-progress
      :percentage="Math.min(100, Math.max(0, task.progress || 0))"
      :status="progressStatus"
      :stroke-width="5"
    />

    <div class="task-meta">
      <template v-if="task.status === 'running'">
        <span class="speed">{{ formatSpeed(task.speed || 0) }}</span>
        <span class="sep">·</span>
        <span>剩余 {{ formatETA(task.eta) }}</span>
      </template>
      <span v-else-if="task.error" class="task-error" :title="task.error">{{ task.error }}</span>
      <span v-else>{{ formatBytes(task.total) }}</span>
    </div>

    <div class="task-actions">
      <el-button
        v-if="task.status === 'queued' || task.status === 'running'"
        text
        size="small"
        :icon="CircleClose"
        @click="$emit('cancel', task)"
      >
        取消
      </el-button>
      <el-button
        v-if="task.status === 'exception' || task.status === 'canceled'"
        text
        size="small"
        :icon="RefreshRight"
        @click="$emit('retry', task)"
      >
        重试
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { CircleClose, RefreshRight } from '@element-plus/icons-vue'
import { formatBytes } from '@/utils/format'
import { formatSpeed, formatETA } from '@/utils/transfer'

const props = defineProps({
  task: { type: Object, required: true },
})

defineEmits(['cancel', 'retry'])

const statusText = computed(() => {
  if (props.task.status === 'running') {
    return props.task.statusText || (props.task.type === 'download' ? '下载中' : '上传中')
  }
  const map = {
    queued: '等待中',
    success: '已完成',
    exception: '失败',
    canceled: '已取消',
  }
  return map[props.task.status] || '-'
})

const progressStatus = computed(() => {
  if (props.task.status === 'success') return 'success'
  if (props.task.status === 'exception') return 'exception'
  return ''
})
</script>

<style scoped>
.transfer-task {
  border: 1px solid var(--ap-border-color);
  border-radius: 12px;
  padding: 12px;
  background: var(--ap-bg-card);
}
.task-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.task-name {
  min-width: 0;
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--ap-text-main);
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: normal;
  white-space: pre-wrap;
}
.task-status {
  font-size: 12px;
  color: var(--ap-text-sub);
  flex-shrink: 0;
}
.transfer-task.success .task-status {
  color: #67c23a;
}
.transfer-task.exception .task-status {
  color: #f56c6c;
}
.task-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 6px;
  font-size: 11px;
  color: var(--ap-text-sub);
  min-height: 18px;
}
.task-meta .speed {
  font-variant-numeric: tabular-nums;
  color: var(--ap-text-main);
}
.task-meta .sep {
  opacity: 0.5;
}
.task-error {
  color: #f56c6c;
  min-width: 0;
  line-height: 1.4;
  overflow-wrap: anywhere;
  white-space: normal;
}
.task-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
  min-height: 24px;
}
</style>
