<template>
  <div class="list-container">
    <el-table
      :data="files"
      style="width: 100%"
      @row-contextmenu="handleRowContextMenu"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" />
      <el-table-column label="名称">
        <template #default="{ row }">
          <div class="name-cell" @dblclick="$emit('item-open', row)">
            <FileIcon
              :is-folder="row.isFolder === 1"
              :file-type="row.fileType"
              :thumb-url="row.thumbnailUrl"
              :size="32"
            />
            <span class="file-name" :title="row.fileName">{{ row.fileName }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="110">
        <template #default="{ row }">
          {{ row.isFolder === 1 ? '-' : formatBytes(row.fileSize) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <ProcessBadge v-if="row.isFolder !== 1" :status="row.processStatus" />
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          {{ formatDate(row.createTime) }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import FileIcon from '@/components/common/FileIcon.vue'
import ProcessBadge from '@/components/common/ProcessBadge.vue'
import { formatBytes, formatDate } from '@/utils/format'

defineProps({
  files: { type: Array, required: true },
})
const emit = defineEmits(['item-contextmenu', 'selection-change', 'item-open'])

const handleRowContextMenu = (row, column, event) => {
  event.preventDefault()
  emit('item-contextmenu', event, row)
}

const handleSelectionChange = (selection) => {
  emit('selection-change', selection)
}
</script>

<style scoped>
.list-container {
  background-color: var(--ap-bg-card);
  border-radius: 16px;
  border: 1px solid var(--ap-border-color);
  overflow: hidden;
}
.name-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.file-name {
  font-weight: 500;
  color: var(--ap-text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
