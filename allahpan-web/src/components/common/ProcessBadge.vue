<template>
  <el-tag :type="config.type" size="small" class="badge" effect="light">
    {{ config.text }}
  </el-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: Number, required: true },
})

const config = computed(() => {
  switch (props.status) {
    case 0: return { text: '排队中', type: 'info' }
    case 1: return { text: '已缩略', type: 'warning' }
    case 2: return { text: '识别中', type: '' /* primary */ }
    case 3: return { text: '可用', type: 'success' }
    case -1:
    default: return { text: '失败', type: 'danger' }
  }
})
</script>

<style scoped>
.badge {
  border-radius: 6px;
  font-size: 11px;
}
</style>
