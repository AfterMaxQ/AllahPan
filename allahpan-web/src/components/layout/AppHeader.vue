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
    <div class="right">
      <SearchBar v-if="!isMobile" />
      <el-button
        v-if="isAdmin"
        class="rebuild-index-btn"
        :loading="rebuildingIndex"
        :title="rebuildingIndex ? '正在重建搜索索引' : '重建搜索索引'"
        aria-label="重建搜索索引"
        @click="handleRebuildIndex"
      >
        <el-icon><Refresh /></el-icon>
        <span class="rebuild-index-label">重建索引</span>
      </el-button>
    </div>
  </header>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Fold, Expand, Refresh } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import { useUserStore } from '@/stores/user'
import { rebuildSearchIndex } from '@/api/searchAdmin'
import { getMyInfo } from '@/api/user'
import SearchBar from '@/components/search/SearchBar.vue'

defineProps({
  sidebarCollapsed: { type: Boolean, default: false },
})
defineEmits(['toggle-sidebar'])

const { isMobile } = useResponsive()
const userStore = useUserStore()
const rebuildingIndex = ref(false)
const isAdmin = computed(() => Number(userStore.userInfo?.id) === 1)

onMounted(async () => {
  if (userStore.userInfo || !userStore.token) return
  try {
    const info = await getMyInfo()
    userStore.setUserInfo(info)
  } catch {
    // The request interceptor handles expired sessions; keep the header quiet otherwise.
  }
})

const handleRebuildIndex = async () => {
  if (rebuildingIndex.value) return
  try {
    await ElMessageBox.confirm(
      '这会根据数据库中的全部有效文件重建搜索索引，可能需要几分钟。是否继续？',
      '重建搜索索引',
      { type: 'warning', confirmButtonText: '开始重建', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  rebuildingIndex.value = true
  try {
    const result = await rebuildSearchIndex()
    ElMessage.success(`搜索索引重建完成，共索引 ${result?.indexedCount ?? 0} 个文件`)
  } catch (error) {
    if (error?.message !== '取消') {
      ElMessage.error(error?.message || '搜索索引重建失败')
    }
  } finally {
    rebuildingIndex.value = false
  }
}
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
  gap: 8px;
}
.rebuild-index-btn {
  flex-shrink: 0;
  color: var(--el-color-primary-dark-2);
  border-color: var(--ap-border-color);
  background: var(--ap-bg-card);
}
.rebuild-index-label {
  margin-left: 4px;
}
@media (max-width: 768px) {
  .app-header.mobile .left { align-items: flex-start; padding-top: 0; }
  .rebuild-index-btn {
    width: 34px;
    min-width: 34px;
    height: 34px;
    padding: 0;
    border-radius: 9px;
  }
  .rebuild-index-label { display: none; }
}
</style>
