<template>
  <header class="app-header">
    <div class="left">
      <el-button class="fold-btn" text @click="$emit('toggle-sidebar')">
        <el-icon size="20">
          <Fold v-if="!sidebarCollapsed" />
          <Expand v-else />
        </el-icon>
      </el-button>
      <slot name="breadcrumb" />
    </div>
    <div class="right">
      <SearchBar />
    </div>
  </header>
</template>

<script setup>
import { Fold, Expand } from '@element-plus/icons-vue'
import SearchBar from '@/components/search/SearchBar.vue'

defineProps({
  sidebarCollapsed: { type: Boolean, default: false },
})
defineEmits(['toggle-sidebar'])
</script>

<style scoped>
.app-header {
  height: 60px;
  background-color: var(--ap-bg-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid var(--ap-border-color);
  flex-shrink: 0;
}
.left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.fold-btn {
  padding: 8px;
}
.right {
  flex-shrink: 0;
}
</style>
