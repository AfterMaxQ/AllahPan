<template>
  <form class="search-bar" role="search" @submit.prevent="triggerSearch">
    <el-input
      v-model="keyword"
      placeholder="搜索文件或内容..."
      :prefix-icon="Search"
      clearable
    />
  </form>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Search } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const keyword = ref('')

watch(() => route.query.q, (val) => { keyword.value = val || '' }, { immediate: true })

const triggerSearch = () => {
  const q = keyword.value.trim()
  if (!q) return
  router.push({ path: '/search', query: { q } })
}
</script>

<style scoped>
.search-bar {
  width: 320px;
}
</style>
