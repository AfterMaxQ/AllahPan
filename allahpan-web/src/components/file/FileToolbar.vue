<template>
  <div class="toolbar" :class="{ mobile: isMobile }">
    <div class="left">
      <template v-if="!isMobile">
        <el-button type="primary" :icon="Upload" @click="$emit('upload')">
          上传文件
        </el-button>
        <el-button :icon="FolderOpened" @click="$emit('upload-folder')">
          上传文件夹
        </el-button>
        <el-button :icon="FolderAdd" @click="$emit('create-folder')">
          新建文件夹
        </el-button>
        <el-button
          v-if="selectedCount > 0"
          type="danger"
          plain
          :icon="Delete"
          @click="$emit('batch-delete')"
        >
          批量删除 ({{ selectedCount }})
        </el-button>
      </template>
      <template v-else>
        <span class="mobile-title">文件</span>
        <el-button
          v-if="selectedCount > 0"
          type="danger"
          size="small"
          plain
          :icon="Delete"
          @click="$emit('batch-delete')"
        >
          {{ selectedCount }}
        </el-button>
      </template>
    </div>
    <div v-if="!isMobile" class="right">
      <el-radio-group
        :model-value="fileStore.viewMode"
        size="small"
        @change="fileStore.toggleViewMode"
      >
        <el-radio-button value="grid">
          <el-icon><Grid /></el-icon>
        </el-radio-button>
        <el-radio-button value="list">
          <el-icon><List /></el-icon>
        </el-radio-button>
      </el-radio-group>
    </div>
  </div>
</template>

<script setup>
import { Upload, FolderAdd, FolderOpened, Delete, Grid, List } from '@element-plus/icons-vue'
import { useFileStore } from '@/stores/file'
import { useResponsive } from '@/composables/useResponsive'

defineProps({
  selectedCount: { type: Number, default: 0 },
})
defineEmits(['upload', 'upload-folder', 'create-folder', 'batch-delete'])

const fileStore = useFileStore()
const { isMobile } = useResponsive()
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--ap-bg-card);
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 16px;
  border: 1px solid var(--ap-border-color);
}
.toolbar.mobile {
  padding: 8px 12px;
  margin-bottom: 10px;
}
.left {
  display: flex;
  gap: 10px;
  align-items: center;
}
.mobile-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--ap-text-main);
}
</style>
