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
                title="返回上一个文件夹位置"
                aria-label="返回上一个文件夹位置"
                @click="fileStore.goBack()"
              >
                <el-icon :size="isMobile ? 14 : 16"><ArrowLeft /></el-icon>
              </el-button>
              <el-button
                :disabled="!fileStore.canGoForward"
                size="small"
                class="nav-arrow"
                title="前往下一个文件夹位置"
                aria-label="前往下一个文件夹位置"
                @click="fileStore.goForward()"
              >
                <el-icon :size="isMobile ? 14 : 16"><ArrowRight /></el-icon>
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
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.nav-arrows {
  display: flex;
  flex-direction: row;
  gap: 2px;
  flex-shrink: 0;
}
.nav-arrow {
  width: 32px;
  min-width: 32px;
  height: 32px;
  min-height: 32px;
  padding: 0;
  border-radius: 9px;
  color: var(--el-color-primary-dark-2);
  border: 1px solid var(--ap-border-color);
  background: var(--ap-bg-card);
  transition: all 0.15s;
}
.nav-arrow:hover:not(:disabled) {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary-dark-2);
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
  padding: clamp(16px, 2vw, 28px);
  overflow-y: auto;
  overscroll-behavior: contain;
  scroll-behavior: smooth;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  .main-container {
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    padding-bottom: calc(58px + env(safe-area-inset-bottom, 0px));
  }
  .content-body {
    flex: 1 0 auto;
    padding: 10px;
    overflow: visible;
  }
  .nav-row {
    width: 100%;
    align-items: flex-start;
    gap: 4px;
  }
  .nav-arrows {
    gap: 2px;
  }
  .nav-arrow {
    width: 28px;
    min-width: 28px;
    height: 30px;
    min-height: 30px;
    border-radius: 8px;
  }
}

/* 平板适配 */
@media (min-width: 769px) and (max-width: 1024px) {
  .content-body {
    padding: 16px;
  }
}
</style>
