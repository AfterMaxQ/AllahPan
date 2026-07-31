<template>
  <div class="app-layout">
    <AppSidebar :is-collapsed="sidebarCollapsed" />
    <div class="main-container">
      <AppHeader
        :sidebar-collapsed="sidebarCollapsed"
        @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
      >
        <template #breadcrumb>
          <div class="nav-row">
            <div class="nav-arrows">
              <el-button
                :disabled="!fileStore.canGoBack"
                size="small"
                class="nav-arrow"
                @click="fileStore.goBack()"
              >
                <el-icon size="14"><ArrowLeft /></el-icon>
              </el-button>
              <el-button
                :disabled="!fileStore.canGoForward"
                size="small"
                class="nav-arrow"
                @click="fileStore.goForward()"
              >
                <el-icon size="14"><ArrowRight /></el-icon>
              </el-button>
            </div>
            <BreadcrumbNav />
          </div>
        </template>
      </AppHeader>
      <div class="content-body">
        <router-view v-slot="{ Component }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
    <TransferPanel />
    <AppTabbar v-if="isMobile" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import { useFileStore } from '@/stores/file'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import AppTabbar from './AppTabbar.vue'
import BreadcrumbNav from '@/components/file/BreadcrumbNav.vue'
import TransferPanel from '@/components/transfer/TransferPanel.vue'

const { isMobile } = useResponsive()
const fileStore = useFileStore()
const sidebarCollapsed = ref(false)
</script>

<style scoped>
.nav-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
}
.nav-arrows {
  display: flex;
  flex-direction: row;
  gap: 2px;
  flex-shrink: 0;
}
.nav-arrow {
  padding: 2px;
  min-width: auto;
  border-radius: 4px;
  color: #e74c3c;
  border: 1px solid var(--ap-border-color);
  background: var(--ap-bg-card);
  transition: all 0.15s;
}
.nav-arrow:hover:not(:disabled) {
  background: #fde8e5;
  border-color: #e74c3c;
  color: #c0392b;
}
.nav-arrow:disabled {
  opacity: 0.25;
  cursor: not-allowed;
  color: #ccc;
}
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}
.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--ap-bg-page);
}
.content-body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  .main-container {
    padding-bottom: 56px;
  }
  .content-body {
    padding: 12px;
  }
}

/* 平板适配 */
@media (min-width: 769px) and (max-width: 1024px) {
  .content-body {
    padding: 16px;
  }
}
</style>
