<template>
  <header class="app-header" :class="{ mobile: isMobile }">
    <div class="left">
      <el-button v-if="!isMobile" class="fold-btn" text @click="$emit('toggle-sidebar')">
        <el-icon size="20">
          <Fold v-if="!sidebarCollapsed" />
          <Expand v-else />
        </el-icon>
      </el-button>
      <slot name="breadcrumb" />
    </div>
    <div v-if="!isMobile" class="right"><SearchBar /></div>
  </header>
</template>

<script setup>
import { Fold, Expand } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import SearchBar from '@/components/search/SearchBar.vue'

defineProps({
  sidebarCollapsed: { type: Boolean, default: false },
})
defineEmits(['toggle-sidebar'])

const { isMobile } = useResponsive()
</script>

<style scoped>
.app-header {
  min-height: 58px;
  background-color: var(--ap-bg-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 7px 16px;
  border-bottom: 1px solid var(--ap-border-color);
  flex-shrink: 0;
}
.app-header.mobile {
  min-height: 50px;
  align-items: flex-start;
  padding: 5px 10px;
}
.left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}
.fold-btn {
  padding: 8px;
}
.right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
@media (max-width: 768px) {
  .app-header.mobile .left { align-items: flex-start; padding-top: 0; }
}
</style>
