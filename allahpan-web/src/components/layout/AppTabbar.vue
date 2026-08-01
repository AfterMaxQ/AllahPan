<template>
  <transition name="search-rise">
    <div v-if="searchVisible" class="mobile-search-layer" @click.self="closeSearch">
      <form class="mobile-search-panel" role="search" @submit.prevent="submitSearch">
        <el-input
          ref="searchInputRef"
          v-model="keyword"
          placeholder="搜索文件或内容..."
          :prefix-icon="Search"
          clearable
          size="large"
          aria-label="搜索文件或内容"
          @keyup.esc="closeSearch"
        />
        <el-button
          type="primary"
          class="search-submit"
          native-type="submit"
          :disabled="!keyword.trim()"
          aria-label="开始搜索"
        >
          <el-icon><Search /></el-icon>
        </el-button>
      </form>
    </div>
  </transition>

  <nav class="app-tabbar safe-bottom" aria-label="移动端主导航">
    <button type="button" class="tab-item" :class="{ active: route.path === '/' }" @click="navigateTo('/')">
      <el-icon><FolderOpened /></el-icon>
      <span class="tab-label">文件</span>
    </button>
    <button type="button" class="tab-item" :class="{ active: route.path === '/favorites' }" @click="navigateTo('/favorites')">
      <el-icon><Star /></el-icon>
      <span class="tab-label">收藏</span>
    </button>
    <button
      type="button"
      class="tab-item"
      :class="{ active: searchVisible || route.path === '/search' }"
      aria-label="搜索文件"
      @click="toggleSearch"
    >
      <el-icon><Search /></el-icon>
      <span class="tab-label">搜索</span>
    </button>
    <button type="button" class="tab-item" :class="{ active: transferStore.panelVisible }" @click="toggleTransfer">
      <el-badge :value="transferStore.activeCount" :hidden="transferStore.activeCount === 0" :max="99">
        <el-icon><UploadFilled /></el-icon>
      </el-badge>
      <span class="tab-label">传输</span>
    </button>
    <button type="button" class="tab-item" :class="{ active: route.path === '/trash' }" @click="navigateTo('/trash')">
      <el-icon><Delete /></el-icon>
      <span class="tab-label">垃圾站</span>
    </button>
  </nav>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FolderOpened, Star, Search, Delete, UploadFilled } from '@element-plus/icons-vue'
import { useTransferStore } from '@/stores/transfer'

const route = useRoute()
const router = useRouter()
const transferStore = useTransferStore()
const searchVisible = ref(false)
const keyword = ref('')
const searchInputRef = ref(null)

const toggleSearch = async () => {
  if (searchVisible.value) {
    closeSearch()
    return
  }
  keyword.value = String(route.query.q || '')
  searchVisible.value = true
  await nextTick()
  searchInputRef.value?.focus()
}

const closeSearch = () => {
  searchVisible.value = false
}

const navigateTo = (path) => {
  closeSearch()
  router.push(path)
}

const toggleTransfer = () => {
  closeSearch()
  transferStore.togglePanel()
}

const submitSearch = () => {
  const q = keyword.value.trim()
  if (!q) return
  closeSearch()
  router.push({ path: '/search', query: { q } })
}
</script>

<style scoped>
.app-tabbar { position: fixed; right: 0; bottom: 0; left: 0; z-index: 1300; display: grid; grid-template-columns: repeat(5, 1fr); min-height: 58px; border-top: 1px solid var(--ap-border-color); background: color-mix(in srgb, var(--ap-bg-card) 94%, transparent); box-shadow: 0 -7px 24px rgba(61, 50, 38, .06); backdrop-filter: blur(14px); }
.tab-item { position: relative; display: flex; min-width: 0; min-height: 58px; flex-direction: column; align-items: center; justify-content: center; gap: 3px; padding: 5px 4px; border: 0; background: transparent; color: var(--ap-text-sub); font: inherit; cursor: pointer; transition: color .18s ease, background .18s ease; }
.tab-item::before { position: absolute; top: 4px; left: 50%; width: 24px; height: 3px; border-radius: 3px; background: var(--el-color-primary); content: ''; opacity: 0; transform: translateX(-50%) scaleX(.5); transition: opacity .18s ease, transform .18s ease; }
.tab-item.active { color: var(--el-color-primary-dark-2); font-weight: 600; }
.tab-item.active::before { opacity: 1; transform: translateX(-50%) scaleX(1); }
.tab-item:active { background: var(--el-color-primary-light-9); }
.tab-item :deep(.el-icon) { font-size: 21px; }
.tab-item :deep(.el-badge__content) { transform: translate(68%, -45%) scale(.82); }
.tab-label { font-size: 10px; line-height: 1; }
.mobile-search-layer { position: fixed; inset: 0 0 calc(58px + env(safe-area-inset-bottom, 0px)); z-index: 1299; display: flex; align-items: flex-end; padding: 14px 12px; background: linear-gradient(to top, rgba(61, 50, 38, .18), rgba(61, 50, 38, .03) 36%, transparent 70%); backdrop-filter: blur(1px); }
.mobile-search-panel { display: grid; width: 100%; grid-template-columns: minmax(0, 1fr) 44px; align-items: center; gap: 8px; padding: 10px; border: 1px solid var(--ap-border-color); border-radius: 15px; background: var(--ap-bg-card); box-shadow: 0 10px 28px rgba(61, 50, 38, .16); }
.search-submit { width: 44px; min-width: 44px; height: 40px; min-height: 40px; padding: 0; border-radius: 11px; }
.search-rise-enter-active, .search-rise-leave-active { transition: opacity .18s ease; }
.search-rise-enter-active .mobile-search-panel, .search-rise-leave-active .mobile-search-panel { transition: transform .18s ease, opacity .18s ease; }
.search-rise-enter-from, .search-rise-leave-to { opacity: 0; }
.search-rise-enter-from .mobile-search-panel, .search-rise-leave-to .mobile-search-panel { opacity: 0; transform: translateY(10px); }
@supports not (color: color-mix(in srgb, white, transparent)) { .app-tabbar { background: var(--ap-bg-card); } }
</style>
