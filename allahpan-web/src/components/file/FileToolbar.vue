<template>
  <div class="toolbar">
    <div class="left">
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
    </div>
    <div class="right">
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

defineProps({
  selectedCount: { type: Number, default: 0 },
})
defineEmits(['upload', 'upload-folder', 'create-folder', 'batch-delete'])

const fileStore = useFileStore()
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
.left {
  display: flex;
  gap: 10px;
}
</style>
