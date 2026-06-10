<template>
  <div class="empty-container">
    <div class="icon-box">
      <el-icon size="64" color="#D5CDC3"><FolderOpened /></el-icon>
    </div>
    <p class="title">{{ title }}</p>
    <p class="subtitle">{{ description }}</p>
    <slot name="action" />
  </div>
</template>

<script setup>
import { FolderOpened } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '这里空荡荡的' },
  description: { type: String, default: '来上传第一个温暖的记忆吧' },
})
</script>

<style scoped>
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
}
.icon-box {
  background-color: var(--ap-bg-sidebar);
  border-radius: 50%;
  padding: 24px;
  margin-bottom: 20px;
}
.title {
  font-size: 18px;
  font-weight: 600;
  color: var(--ap-text-main);
  margin: 0 0 10px 0;
}
.subtitle {
  font-size: 15px;
  color: var(--ap-text-sub);
  margin: 0 0 32px 0;
}
</style>
