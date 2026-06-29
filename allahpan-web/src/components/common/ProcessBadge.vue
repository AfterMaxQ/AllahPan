<template>
  <el-tooltip :content="config.tip" placement="top" :show-after="250" :disabled="!config.tip">
    <span class="proc-badge" :class="config.cls">
      <el-icon class="proc-icon" :class="{ spin: config.spin }">
        <component :is="config.icon" />
      </el-icon>
      <span v-if="config.label" class="proc-label">{{ config.label }}</span>
    </span>
  </el-tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, CircleCheckFilled, WarningFilled, Clock } from '@element-plus/icons-vue'

const props = defineProps({
  status: { type: Number, required: true },
})

// 把后端的技术流水线阶段，映射为普通用户能直观理解的「处理中 / 就绪 / 处理失败」
// 详细阶段仅在悬浮提示里展示，不打扰普通用户。
const config = computed(() => {
  switch (props.status) {
    case 0:
      return { cls: 'processing', icon: Clock, spin: false, label: '处理中', tip: '已加入队列，等待处理' }
    case 1:
      return { cls: 'processing', icon: Loading, spin: true, label: '处理中', tip: '正在识别内容（需本机 Ollama 服务在线）' }
    case 2:
      return { cls: 'processing', icon: Loading, spin: true, label: '处理中', tip: '正在建立搜索索引' }
    case 3:
      // 就绪：只用一个低调的绿色对勾，不显示文字，保持列表整洁
      return { cls: 'ready', icon: CircleCheckFilled, spin: false, label: '', tip: '已就绪，可预览与搜索' }
    case -1:
    default:
      return {
        cls: 'failed',
        icon: WarningFilled,
        spin: false,
        label: '处理失败',
        tip: '文件可正常下载和预览，仅内容识别/索引未完成',
      }
  }
})
</script>

<style scoped>
.proc-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  line-height: 1;
  border-radius: 999px;
  vertical-align: middle;
}
.proc-icon {
  font-size: 13px;
}
/* 处理中：琥珀色胶囊 */
.proc-badge.processing {
  padding: 3px 8px;
  color: #b5791d;
  background: rgba(230, 162, 60, 0.14);
}
/* 失败：橙红色胶囊 */
.proc-badge.failed {
  padding: 3px 8px;
  color: #d9554d;
  background: rgba(245, 108, 108, 0.14);
  cursor: help;
}
/* 就绪：仅一个低调的绿色对勾，无背景、无文字 */
.proc-badge.ready {
  color: var(--el-color-success, #67c23a);
  opacity: 0.75;
}
.proc-badge.ready .proc-icon {
  font-size: 14px;
}
.spin {
  animation: proc-spin 0.9s linear infinite;
}
@keyframes proc-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
