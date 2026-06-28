<template>
  <div class="sidebar-wrapper" :class="{ collapsed: isCollapsed }">
    <!-- Logo -->
    <div class="logo-area">
      <el-icon size="28" color="var(--el-color-primary)"><HomeFilled /></el-icon>
      <span v-show="!isCollapsed" class="logo-title">AllahPan</span>
    </div>

    <!-- 导航菜单 -->
    <el-menu
      :default-active="activeMenu"
      router
      class="side-menu"
      :collapse="isCollapsed"
      background-color="#F5EFE6"
      text-color="#3D3226"
      active-text-color="#C4946B"
    >
      <el-menu-item index="/">
        <el-icon><FolderOpened /></el-icon>
        <template #title>全部文件</template>
      </el-menu-item>
      <el-menu-item index="/favorites">
        <el-icon><Star /></el-icon>
        <template #title>我的收藏</template>
      </el-menu-item>
      <el-menu-item index="/trash">
        <el-icon><Delete /></el-icon>
        <template #title>垃圾站</template>
      </el-menu-item>
    </el-menu>

    <div class="transfer-entry" @click="transferStore.togglePanel">
      <el-badge :value="transferStore.activeCount" :hidden="transferStore.activeCount === 0" class="transfer-badge">
        <el-icon><UploadFilled /></el-icon>
      </el-badge>
      <span v-show="!isCollapsed">传输列表</span>
    </div>

    <!-- 底部用户信息 -->
    <div class="footer-area">
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-info">
          <el-avatar :size="32" class="user-avatar">
            {{ userStore.userInfo?.nickname?.charAt(0) || 'U' }}
          </el-avatar>
          <div v-show="!isCollapsed" class="user-meta">
            <span class="user-name">{{ userStore.userInfo?.nickname || '用户' }}</span>
          </div>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useTransferStore } from '@/stores/transfer'
import { getMyInfo } from '@/api/user'
import { HomeFilled, FolderOpened, Star, Delete, UploadFilled } from '@element-plus/icons-vue'

defineProps({
  isCollapsed: { type: Boolean, default: false },
})

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const transferStore = useTransferStore()

const activeMenu = computed(() => route.path)

onMounted(async () => {
  try {
    const info = await getMyInfo()
    userStore.setUserInfo(info)
  } catch (e) {
    // 获取用户信息失败，静默处理
  }
})

const handleCommand = (cmd) => {
  if (cmd === 'logout') {
    userStore.logout()
    router.replace('/login')
  }
}
</script>

<style scoped>
.sidebar-wrapper {
  width: 200px;
  background-color: var(--ap-bg-sidebar);
  height: 100vh;
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  border-right: 1px solid var(--ap-border-color);
  flex-shrink: 0;
}
.sidebar-wrapper.collapsed {
  width: 64px;
}
.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  gap: 12px;
  border-bottom: 1px solid var(--ap-border-color);
}
.logo-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--ap-text-main);
  white-space: nowrap;
}
.side-menu {
  border-right: none;
  flex: 1;
  padding-top: 8px;
}
.transfer-entry {
  margin: 4px 8px 8px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  color: #3D3226;
  cursor: pointer;
  transition: background-color 0.2s;
}
.transfer-entry:hover {
  background-color: var(--el-color-primary-light-9);
}
.sidebar-wrapper.collapsed .transfer-entry {
  justify-content: center;
  padding: 0;
}
.transfer-badge {
  display: inline-flex;
}
:deep(.el-menu-item) {
  height: 48px;
  line-height: 48px;
  margin: 4px 8px;
  border-radius: 8px;
}
:deep(.el-menu-item.is-active) {
  background-color: var(--el-color-primary-light-8);
  font-weight: 600;
}
:deep(.el-menu-item:hover) {
  background-color: var(--el-color-primary-light-9);
}
.footer-area {
  padding: 16px;
  border-top: 1px solid var(--ap-border-color);
}
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.user-avatar {
  background-color: var(--el-color-primary);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
}
.user-meta {
  display: flex;
  flex-direction: column;
}
.user-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ap-text-main);
}
</style>
