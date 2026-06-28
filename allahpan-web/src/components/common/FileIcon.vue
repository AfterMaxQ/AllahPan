<template>
  <div class="file-icon-wrapper" :style="{ width: size + 'px', height: size + 'px' }">
    <!-- 文件夹 -->
    <template v-if="isFolder">
      <el-icon :size="size" color="#C4946B"><Folder /></el-icon>
    </template>
    <!-- 图片缩略图 -->
    <template v-else-if="fileType === 'IMAGE' && displayThumbUrl">
      <el-image :src="displayThumbUrl" fit="cover" class="img-thumb" lazy>
        <template #error>
          <el-icon :size="size" color="#A89F91"><Picture /></el-icon>
        </template>
      </el-image>
    </template>
    <!-- 其他类型图标 -->
    <template v-else>
      <el-icon :size="size" :color="iconStyle.color">
        <component :is="iconStyle.icon" />
      </el-icon>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Folder, Picture, VideoCamera, Document, Files } from '@element-plus/icons-vue'
import { createObjectUrlFromApi } from '@/api/file'

const props = defineProps({
  isFolder: { type: [Boolean, Number], default: false },
  fileType: { type: String, default: 'OTHER' },
  thumbUrl: { type: String, default: '' },
  size: { type: Number, default: 48 },
})

const displayThumbUrl = ref('')
let controller = null

function revokeThumb() {
  if (displayThumbUrl.value?.startsWith('blob:')) {
    window.URL.revokeObjectURL(displayThumbUrl.value)
  }
  displayThumbUrl.value = ''
}

watch(
  () => props.thumbUrl,
  async (url) => {
    controller?.abort()
    revokeThumb()
    if (!url || props.fileType !== 'IMAGE') return
    controller = new AbortController()
    try {
      displayThumbUrl.value = await createObjectUrlFromApi(url, controller.signal)
    } catch (e) {
      if (e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
        displayThumbUrl.value = ''
      }
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  controller?.abort()
  revokeThumb()
})

const iconStyle = computed(() => {
  const map = {
    IMAGE: { icon: Picture, color: '#D2A280' },
    VIDEO: { icon: VideoCamera, color: '#B38B6D' },
    DOCUMENT: { icon: Document, color: '#88A2B9' },
    FOLDER: { icon: Folder, color: '#C4946B' },
    OTHER: { icon: Files, color: '#A59B8F' },
  }
  return map[props.fileType] || map.OTHER
})
</script>

<style scoped>
.file-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}
.img-thumb {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  border: 1px solid var(--ap-border-color);
}
</style>
