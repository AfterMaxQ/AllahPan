<template>
  <div class="list-container" :class="{ mobile: isMobile }">
    <div v-if="isMobile" class="mobile-file-list">
      <article
        v-for="row in files"
        :key="row.id"
        class="mobile-file-row"
        @click="handleMobileOpen(row)"
        @contextmenu.prevent.stop="handleMobileContextMenu($event, row)"
      >
        <FileIcon
          :is-folder="row.isFolder === 1"
          :file-type="row.fileType"
          :file-name="row.fileName"
          :thumb-url="row.thumbnailUrl"
          :size="46"
        />
        <div class="mobile-file-content">
          <div class="mobile-file-name ap-file-name" dir="auto" :title="row.fileName">{{ row.fileName }}</div>
          <div class="mobile-file-meta">
            <span>{{ row.isFolder === 1 ? '文件夹' : formatBytes(row.fileSize) }}</span>
            <span class="meta-dot" aria-hidden="true" />
            <span>{{ formatDate(row.createTime) }}</span>
          </div>
          <ProcessBadge
            v-if="row.isFolder !== 1 && row.processStatus !== 3"
            :status="row.processStatus"
          />
        </div>
        <button
          type="button"
          class="mobile-more"
          :aria-label="`${row.fileName}的更多操作`"
          @click.stop="$emit('item-contextmenu', $event, row)"
        >
          <el-icon><MoreFilled /></el-icon>
        </button>
      </article>
    </div>

    <el-table
      v-else
      ref="tableRef"
      :data="files"
      row-key="id"
      style="width: 100%"
      @row-contextmenu="handleRowContextMenu"
      @row-dblclick="(row) => $emit('item-open', row)"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" :reserve-selection="true" />
      <el-table-column label="名称" min-width="300">
        <template #default="{ row }">
          <div class="name-cell" @dblclick.stop="$emit('item-open', row)">
            <FileIcon
              :is-folder="row.isFolder === 1"
              :file-type="row.fileType"
              :file-name="row.fileName"
              :thumb-url="row.thumbnailUrl"
              :size="38"
            />
            <span class="file-name ap-file-name" dir="auto" :title="row.fileName">{{ row.fileName }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="120" align="right">
        <template #default="{ row }">{{ row.isFolder === 1 ? '—' : formatBytes(row.fileSize) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110" align="center">
        <template #default="{ row }">
          <ProcessBadge v-if="row.isFolder !== 1" :status="row.processStatus" />
          <span v-else class="folder-status">文件夹</span>
        </template>
      </el-table-column>
      <el-table-column label="修改时间" width="180" align="right">
        <template #default="{ row }">{{ formatDate(row.createTime) }}</template>
      </el-table-column>
      <el-table-column width="58" align="center">
        <template #default="{ row }">
          <button
            type="button"
            class="desktop-more"
            :aria-label="`${row.fileName}的更多操作`"
            @click.stop="$emit('item-contextmenu', $event, row)"
          >
            <el-icon><MoreFilled /></el-icon>
          </button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import FileIcon from '@/components/common/FileIcon.vue'
import ProcessBadge from '@/components/common/ProcessBadge.vue'
import { formatBytes, formatDate } from '@/utils/format'

const { isMobile } = useResponsive()
const props = defineProps({
  files: { type: Array, required: true },
  selectedIds: { type: Array, default: () => [] },
})
const emit = defineEmits(['item-contextmenu', 'selection-change', 'item-toggle-select', 'item-open'])
const tableRef = ref(null)
let syncingSelection = false
let suppressMobileClickUntil = 0

const handleRowContextMenu = (row, column, event) => {
  event.preventDefault()
  emit('item-contextmenu', event, row)
}

const handleSelectionChange = (selection) => {
  if (!syncingSelection) emit('selection-change', selection)
}

const handleMobileOpen = (row) => {
  if (Date.now() < suppressMobileClickUntil) return
  emit('item-open', row)
}

const handleMobileContextMenu = (event, row) => {
  suppressMobileClickUntil = Date.now() + 700
  emit('item-contextmenu', event, row)
}

const syncDesktopSelection = async () => {
  if (isMobile.value || !tableRef.value) return
  await nextTick()
  syncingSelection = true
  tableRef.value.clearSelection()
  const selectedSet = new Set(props.selectedIds)
  props.files.forEach((file) => {
    if (selectedSet.has(file.id)) tableRef.value.toggleRowSelection(file, true)
  })
  await nextTick()
  syncingSelection = false
}

watch([() => props.files, () => props.selectedIds, isMobile], syncDesktopSelection, { deep: true, flush: 'post' })
onMounted(syncDesktopSelection)
</script>

<style scoped>
.list-container { overflow: hidden; border: 1px solid var(--ap-border-color); border-radius: 16px; background: var(--ap-bg-card); box-shadow: 0 5px 18px rgba(61, 50, 38, .035); }
.name-cell { display: flex; min-width: 0; align-items: flex-start; gap: 12px; padding: 4px 0; cursor: pointer; }
.file-name { min-width: 0; padding-top: 6px; color: var(--ap-text-main); font-size: 14px; font-weight: 550; line-height: 1.45; overflow-wrap: anywhere; word-break: normal; white-space: pre-wrap; }
.folder-status { color: var(--ap-text-sub); font-size: 11px; }
.desktop-more, .mobile-more { display: inline-flex; align-items: center; justify-content: center; border: 0; background: transparent; color: var(--ap-text-sub); cursor: pointer; transition: color .18s ease, background .18s ease; }
.desktop-more { width: 32px; height: 32px; border-radius: 9px; opacity: .5; }
.desktop-more:hover { background: var(--ap-bg-sidebar); color: var(--el-color-primary-dark-2); opacity: 1; }
:deep(.el-table) { --el-table-header-bg-color: #FBF7F2; --el-table-row-hover-bg-color: var(--el-color-primary-light-9); --el-table-border-color: var(--ap-border-color); }
:deep(.el-table th.el-table__cell) { height: 46px; color: var(--ap-text-sub); font-size: 12px; font-weight: 600; }
:deep(.el-table td.el-table__cell) { padding: 8px 0; }
:deep(.el-table__row:hover .desktop-more) { opacity: 1; }

.mobile-file-list { display: flex; flex-direction: column; }
.mobile-file-row { position: relative; display: grid; grid-template-columns: 46px minmax(0, 1fr) 44px; align-items: start; gap: 8px; min-height: 76px; padding: 13px 6px 13px 10px; border-bottom: 1px solid var(--ap-border-color); background: var(--ap-bg-card); transition: background .18s ease, transform .12s ease; }
.mobile-file-row:last-child { border-bottom: 0; }
.mobile-file-row:active { background: var(--el-color-primary-light-9); transform: scale(.995); }
.mobile-file-content { min-width: 0; padding-top: 1px; }
.mobile-file-name { color: var(--ap-text-main); font-size: 16px; font-weight: 600; line-height: 1.48; overflow-wrap: anywhere; word-break: normal; white-space: pre-wrap; }
.mobile-file-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: 6px 0; color: var(--ap-text-sub); font-size: 11px; line-height: 1.45; }
.meta-dot { width: 3px; height: 3px; border-radius: 50%; background: var(--ap-border-color); }
.mobile-more { width: 44px; min-width: 44px; height: 44px; border-radius: 11px; font-size: 18px; }

@media (max-width: 340px) {
  .mobile-file-row { grid-template-columns: 42px minmax(0, 1fr) 42px; gap: 6px; padding-left: 8px; }
}
.mobile-more:active { background: var(--ap-bg-sidebar); color: var(--el-color-primary-dark-2); }

@media (max-width: 768px) {
  .list-container.mobile { border-radius: 14px; box-shadow: none; }
}
</style>
