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
      <template v-if="isMobile">
        <el-button v-if="!searchVisible" class="search-toggle" text @click="searchVisible = true">
          <el-icon size="20"><Search /></el-icon>
        </el-button>
        <div v-else class="mobile-search-bar">
          <el-input
            ref="mobileSearchRef"
            v-model="mobileKeyword"
            placeholder="搜索文件..."
            :prefix-icon="Search"
            clearable
            size="small"
            @keyup.enter="doMobileSearch"
            @blur="onSearchBlur"
          />
        </div>
      </template>
      <SearchBar v-else />
    </div>
  </header>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Fold, Expand, Search } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import SearchBar from '@/components/search/SearchBar.vue'

defineProps({
  sidebarCollapsed: { type: Boolean, default: false },
})
defineEmits(['toggle-sidebar'])

const { isMobile } = useResponsive()
const router = useRouter()
const searchVisible = ref(false)
const mobileKeyword = ref('')
const mobileSearchRef = ref(null)

watch(searchVisible, async (val) => {
  if (val) {
    await nextTick()
    mobileSearchRef.value?.focus()
  }
})

const doMobileSearch = () => {
  const q = mobileKeyword.value.trim()
  if (!q) return
  router.push({ path: '/search', query: { q } })
  searchVisible.value = false
  mobileKeyword.value = ''
}

const onSearchBlur = () => {
  setTimeout(() => {
    if (mobileKeyword.value.trim() === '') {
      searchVisible.value = false
    }
  }, 150)
}
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
.app-header.mobile {
  height: 48px;
  padding: 0 12px;
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
}
.search-toggle {
  padding: 8px;
}
.mobile-search-bar {
  width: 180px;
}
</style>
