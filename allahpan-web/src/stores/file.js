import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useFileStore = defineStore('file', () => {
  const currentFolderId = ref(0)
  const viewMode = ref(localStorage.getItem('allahpan_viewMode') || 'grid')
  const refreshTrigger = ref(0)  // SSE 事件触发刷新

  // 文件夹导航历史
  const folderHistory = ref([0])
  const historyIndex = ref(0)

  const canGoBack = computed(() => historyIndex.value > 0)
  const canGoForward = computed(() => historyIndex.value < folderHistory.value.length - 1)

  const navigateTo = (id) => {
    if (historyIndex.value < folderHistory.value.length - 1) {
      folderHistory.value = folderHistory.value.slice(0, historyIndex.value + 1)
    }
    if (folderHistory.value[historyIndex.value] !== id) {
      folderHistory.value.push(id)
      historyIndex.value = folderHistory.value.length - 1
    }
    currentFolderId.value = id
  }

  const goBack = () => {
    if (!canGoBack.value) return
    historyIndex.value--
    currentFolderId.value = folderHistory.value[historyIndex.value]
  }

  const goForward = () => {
    if (!canGoForward.value) return
    historyIndex.value++
    currentFolderId.value = folderHistory.value[historyIndex.value]
  }

  const setCurrentFolder = (id) => {
    currentFolderId.value = id
  }

  const toggleViewMode = () => {
    setViewMode(viewMode.value === 'grid' ? 'list' : 'grid')
  }

  const setViewMode = (mode) => {
    if (mode !== 'grid' && mode !== 'list') return
    viewMode.value = mode
    localStorage.setItem('allahpan_viewMode', viewMode.value)
  }

  const triggerRefresh = () => {
    refreshTrigger.value++
  }

  return {
    currentFolderId, viewMode, refreshTrigger,
    canGoBack, canGoForward, navigateTo, goBack, goForward,
    setCurrentFolder, toggleViewMode, setViewMode, triggerRefresh,
  }
})
