<template>
  <div class="app-layout">
    <AppSidebar :is-collapsed="sidebarCollapsed" />
    <div class="main-container">
      <AppHeader
        :sidebar-collapsed="sidebarCollapsed"
        @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
      >
        <template #breadcrumb>
          <BreadcrumbNav />
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
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import BreadcrumbNav from '@/components/file/BreadcrumbNav.vue'
import TransferPanel from '@/components/transfer/TransferPanel.vue'

const sidebarCollapsed = ref(false)
</script>

<style scoped>
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
</style>
