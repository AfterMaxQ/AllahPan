import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFileStore = defineStore('file', () => {
  const currentFolderId = ref(0)
  const viewMode = ref(localStorage.getItem('allahpan_viewMode') || 'grid')
  const refreshTrigger = ref(0)  // SSE 事件触发刷新

  const setCurrentFolder = (id) => {
    currentFolderId.value = id
  }

  const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid'
    localStorage.setItem('allahpan_viewMode', viewMode.value)
  }

  const triggerRefresh = () => {
    refreshTrigger.value++
  }

  return { currentFolderId, viewMode, refreshTrigger, setCurrentFolder, toggleViewMode, triggerRefresh }
})
