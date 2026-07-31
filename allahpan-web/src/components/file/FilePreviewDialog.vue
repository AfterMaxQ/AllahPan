<template>
  <el-dialog
    v-model="visible"
    :title="file?.fileName"
    width="75%"
    top="5vh"
    destroy-on-close
  >
    <div class="preview-body" v-loading="loading">
      <!-- 图片预览 -->
      <div v-if="file?.fileType === 'IMAGE'" class="preview-center">
        <el-image
          :src="mediaUrl"
          fit="contain"
          class="preview-img"
          :preview-src-list="[mediaUrl]"
          @load="handleMediaLoaded"
          @error="handleImageError"
        />
      </div>

      <!-- 视频预览 -->
      <div v-else-if="file?.fileType === 'VIDEO'" class="preview-center">
        <video
          :src="mediaUrl"
          controls
          autoplay
          preload="metadata"
          class="preview-video"
          @loadeddata="handleMediaLoaded"
          @error="handleMediaError"
        />
      </div>

      <!-- PDF 预览 -->
      <div v-else-if="isPdf" class="preview-center" style="background: transparent; padding: 0;">
        <iframe :src="mediaUrl" class="preview-pdf" @load="handleMediaLoaded" />
      </div>

      <!-- XLSX / CSV 表格预览 -->
      <div v-else-if="isSpreadsheet" class="spreadsheet-preview">
        <div class="spreadsheet-toolbar">
          <div class="spreadsheet-summary">
            <span class="spreadsheet-title">表格预览</span>
            <span v-if="spreadsheetTotalRows" class="spreadsheet-meta">
              {{ spreadsheetTotalRows }} 行 · {{ spreadsheetTotalColumns }} 列
            </span>
          </div>
          <el-select
            v-if="spreadsheetSheets.length > 1"
            v-model="activeSpreadsheetSheet"
            class="sheet-selector"
            size="small"
            aria-label="选择工作表"
          >
            <el-option
              v-for="sheetName in spreadsheetSheets"
              :key="sheetName"
              :label="sheetName"
              :value="sheetName"
            />
          </el-select>
          <span v-else-if="spreadsheetSheets[0]" class="sheet-name">{{ spreadsheetSheets[0] }}</span>
        </div>

        <div v-if="spreadsheetError" class="spreadsheet-message">
          <FileIcon
            :is-folder="false"
            :file-type="file?.fileType"
            :file-name="file?.fileName"
            :size="48"
          />
          <div>
            <strong>无法读取表格内容</strong>
            <p>{{ spreadsheetError }}</p>
          </div>
        </div>

        <template v-else-if="spreadsheetRows.length">
          <div class="spreadsheet-table-wrap">
            <table class="spreadsheet-table">
              <thead>
                <tr>
                  <th class="row-number corner-cell" scope="col" />
                  <th v-for="column in spreadsheetColumnLabels" :key="column" scope="col">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in spreadsheetRows" :key="rowIndex">
                  <th class="row-number" scope="row">{{ rowIndex + 1 }}</th>
                  <td v-for="(cell, columnIndex) in row" :key="columnIndex" :title="cell">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="spreadsheetPreviewLimited" class="spreadsheet-limit-note">
            为保证加载速度，当前仅显示前 {{ MAX_SPREADSHEET_ROWS }} 行和 {{ MAX_SPREADSHEET_COLUMNS }} 列。
          </div>
        </template>

        <div v-else class="spreadsheet-empty">当前工作表为空</div>

        <div class="spreadsheet-actions">
          <span>{{ file?.fileName }} ({{ formatBytes(file?.fileSize) }})</span>
          <el-button type="primary" plain @click="triggerDownload">下载原文件</el-button>
        </div>
      </div>

      <!-- 文档预览：已提取文字时直接展示文本内容 -->
      <div v-else-if="file?.fileType === 'DOCUMENT' && ocrText" class="preview-doc" style="flex-direction: column; align-items: stretch; width: 100%; padding: 0;">
        <div class="doc-text-preview">
          <div class="doc-text-header">
            <el-icon size="18" color="#C4946B"><Cpu /></el-icon>
            <span>文本内容</span>
          </div>
          <div class="doc-text-body">{{ ocrText }}</div>
        </div>
        <div class="doc-text-actions">
          <p>{{ file?.fileName }} ({{ formatBytes(file?.fileSize) }})</p>
          <el-button type="primary" @click="triggerDownload">下载到本地查看</el-button>
        </div>
      </div>

      <!-- 文档/其他 -->
      <div v-else class="preview-doc">
        <div class="doc-icon-section">
          <FileIcon
            :is-folder="false"
            :file-type="file?.fileType"
            :file-name="file?.fileName"
            :size="80"
          />
          <h3>该格式暂不支持在线预览</h3>
          <p>{{ file?.fileName }} ({{ formatBytes(file?.fileSize) }})</p>
          <el-button type="primary" @click="triggerDownload">下载到本地查看</el-button>
        </div>
      </div>

      <!-- OCR / AI 识别文字（可折叠，仅 IMAGE 等非 DOCUMENT 文件显示） -->
      <div v-if="ocrText && file?.fileType !== 'DOCUMENT'" class="ocr-section">
        <div class="ocr-header" @click="ocrExpanded = !ocrExpanded">
          <el-icon color="#C4946B"><Cpu /></el-icon>
          <span>图片内容</span>
          <el-icon class="ocr-arrow" :class="{ expanded: ocrExpanded }"><ArrowRight /></el-icon>
        </div>
        <div v-show="ocrExpanded" class="ocr-content">{{ ocrText }}</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Cpu, ArrowRight } from '@element-plus/icons-vue'
import { getFileDetail, getPreviewUrl, getThumbnailUrl, getStreamUrl, requestBlob } from '@/api/file'
import { useTransferStore } from '@/stores/transfer'
import { formatBytes } from '@/utils/format'
import FileIcon from '@/components/common/FileIcon.vue'

const visible = ref(false)
const loading = ref(false)
const file = ref(null)
const mediaUrl = ref('')
const imageCandidates = ref([])
const imageCandidateIndex = ref(0)
const ocrText = ref('')
const ocrExpanded = ref(false)
const spreadsheetSheets = ref([])
const activeSpreadsheetSheet = ref('')
const spreadsheetRows = ref([])
const spreadsheetTotalRows = ref(0)
const spreadsheetTotalColumns = ref(0)
const spreadsheetError = ref('')
const transferStore = useTransferStore()
const MAX_SPREADSHEET_BYTES = 10 * 1024 * 1024
const MAX_SPREADSHEET_ROWS = 200
const MAX_SPREADSHEET_COLUMNS = 50
let spreadsheetWorkbook = null
let spreadsheetXlsx = null

const isPdf = computed(() => {
  return file.value?.fileName?.toLowerCase().endsWith('.pdf')
})
const isSpreadsheet = computed(() => isSpreadsheetFile(file.value?.fileName))
const spreadsheetColumnLabels = computed(() => Array.from(
  { length: Math.min(spreadsheetTotalColumns.value, MAX_SPREADSHEET_COLUMNS) },
  (_, index) => columnLabel(index),
))
const spreadsheetPreviewLimited = computed(() => (
  spreadsheetTotalRows.value > MAX_SPREADSHEET_ROWS
  || spreadsheetTotalColumns.value > MAX_SPREADSHEET_COLUMNS
))
let previewController = null
let previewRequestId = 0

function isSpreadsheetFile(fileName) {
  const extension = fileName?.split('.').pop()?.toLowerCase()
  return extension === 'xlsx' || extension === 'csv'
}

function columnLabel(index) {
  let value = index + 1
  let label = ''
  while (value > 0) {
    const remainder = (value - 1) % 26
    label = String.fromCharCode(65 + remainder) + label
    value = Math.floor((value - 1) / 26)
  }
  return label
}

const clearMedia = () => {
  mediaUrl.value = ''
  imageCandidates.value = []
  imageCandidateIndex.value = 0
}

const clearSpreadsheet = () => {
  spreadsheetWorkbook = null
  spreadsheetXlsx = null
  spreadsheetSheets.value = []
  activeSpreadsheetSheet.value = ''
  spreadsheetRows.value = []
  spreadsheetTotalRows.value = 0
  spreadsheetTotalColumns.value = 0
  spreadsheetError.value = ''
}

const displaySpreadsheetSheet = (sheetName) => {
  if (!spreadsheetWorkbook || !spreadsheetXlsx || !sheetName) return
  const worksheet = spreadsheetWorkbook.Sheets[sheetName]
  const matrix = spreadsheetXlsx.utils.sheet_to_json(worksheet, {
    header: 1,
    raw: false,
    defval: '',
    blankrows: false,
  })
  const totalColumns = matrix.reduce((maximum, row) => Math.max(maximum, row.length), 0)
  spreadsheetTotalRows.value = matrix.length
  spreadsheetTotalColumns.value = totalColumns
  spreadsheetRows.value = matrix.slice(0, MAX_SPREADSHEET_ROWS).map((row) => (
    Array.from({ length: Math.min(totalColumns, MAX_SPREADSHEET_COLUMNS) }, (_, index) => String(row[index] ?? ''))
  ))
}

const loadSpreadsheet = async (fileId, fileName, signal, requestId) => {
  try {
    if (file.value?.fileSize > MAX_SPREADSHEET_BYTES) {
      throw new Error(`文件超过 ${MAX_SPREADSHEET_BYTES / 1024 / 1024} MB，暂不支持在线预览`)
    }
    const blob = await requestBlob(`/file/${fileId}/stream`, null, signal)
    if (blob.size > MAX_SPREADSHEET_BYTES) {
      throw new Error(`文件超过 ${MAX_SPREADSHEET_BYTES / 1024 / 1024} MB，暂不支持在线预览`)
    }
    const [buffer, XLSX] = await Promise.all([blob.arrayBuffer(), import('xlsx')])
    if (requestId !== previewRequestId) return
    const workbook = XLSX.read(buffer, { type: 'array', cellText: true })
    if (!workbook.SheetNames.length) throw new Error('文件中没有可读取的工作表')
    spreadsheetWorkbook = workbook
    spreadsheetXlsx = XLSX
    spreadsheetSheets.value = workbook.SheetNames
    activeSpreadsheetSheet.value = workbook.SheetNames[0]
    displaySpreadsheetSheet(activeSpreadsheetSheet.value)
  } catch (error) {
    if (requestId !== previewRequestId || error?.code === 'ERR_CANCELED' || error?.name === 'AbortError') return
    console.error(`加载表格预览失败: ${fileName}`, error)
    spreadsheetError.value = error?.message || '文件格式不正确或内容已损坏'
  } finally {
    if (requestId === previewRequestId) loading.value = false
  }
}

const handleMediaLoaded = () => {
  loading.value = false
}

const handleMediaError = () => {
  loading.value = false
}

const handleImageError = () => {
  const nextIndex = imageCandidateIndex.value + 1
  if (nextIndex < imageCandidates.value.length) {
    imageCandidateIndex.value = nextIndex
    mediaUrl.value = imageCandidates.value[nextIndex]
  } else {
    loading.value = false
  }
}

const open = async (targetFile) => {
  const requestId = ++previewRequestId
  previewController?.abort()
  previewController = new AbortController()
  clearMedia()
  clearSpreadsheet()
  file.value = targetFile
  visible.value = true
  loading.value = true
  ocrText.value = ''
  ocrExpanded.value = false

  try {
    const detail = await getFileDetail(targetFile.id, previewController.signal)
    if (requestId !== previewRequestId) return
    file.value = { ...targetFile, ...detail }
    if (detail.processStatus >= 2) {
      ocrText.value = detail.originText || ''
    }

    if (detail.fileType === 'IMAGE') {
      imageCandidates.value = [
        detail.previewUrl ? getPreviewUrl(targetFile.id) : '',
        detail.thumbnailUrl ? getThumbnailUrl(targetFile.id) : '',
        getStreamUrl(targetFile.id),
      ].filter(Boolean)
      mediaUrl.value = imageCandidates.value[0] || ''
    } else if (detail.fileType === 'VIDEO') {
      mediaUrl.value = getStreamUrl(targetFile.id)
    } else if (detail.fileName?.toLowerCase().endsWith('.pdf')) {
      mediaUrl.value = getStreamUrl(targetFile.id)
    } else if (isSpreadsheetFile(detail.fileName)) {
      await loadSpreadsheet(targetFile.id, detail.fileName, previewController.signal, requestId)
    } else {
      loading.value = false
    }
  } catch (e) {
    if (requestId === previewRequestId
        && e?.code !== 'ERR_CANCELED' && e?.name !== 'AbortError') {
      console.error('加载预览失败', e)
      loading.value = false
    }
  }
  if (requestId === previewRequestId && !mediaUrl.value) {
    loading.value = false
  }
}

const triggerDownload = () => {
  if (file.value) {
    transferStore.enqueueDownload(file.value)
    transferStore.notifyQueued(1, '下载')
  }
}

watch(visible, (value) => {
  if (!value) {
    previewRequestId++
    previewController?.abort()
    clearMedia()
    clearSpreadsheet()
    loading.value = false
  }
})

watch(activeSpreadsheetSheet, (sheetName) => {
  displaySpreadsheetSheet(sheetName)
})

onBeforeUnmount(() => {
  previewRequestId++
  previewController?.abort()
  clearMedia()
  clearSpreadsheet()
})

defineExpose({ open })
</script>

<style scoped>
.preview-body {
  min-height: 300px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.preview-center {
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #1e1e1e;
  border-radius: 12px;
  overflow: hidden;
  padding: 12px;
  max-height: 60vh;
}
.preview-img {
  max-width: 100%;
  max-height: 55vh;
}
.preview-video {
  width: 100%;
  max-height: 55vh;
  outline: none;
}
.preview-pdf {
  width: 100%;
  height: 70vh;
  border: none;
  border-radius: 8px;
}
.spreadsheet-preview {
  display: flex;
  min-height: 300px;
  flex-direction: column;
  border: 1px solid var(--ap-border-color);
  border-radius: 12px;
  overflow: hidden;
  background: var(--ap-bg-card);
}
.spreadsheet-toolbar,
.spreadsheet-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--ap-bg-sidebar);
}
.spreadsheet-toolbar { border-bottom: 1px solid var(--ap-border-color); }
.spreadsheet-summary { display: flex; min-width: 0; align-items: baseline; gap: 8px; }
.spreadsheet-title { color: var(--ap-text-main); font-weight: 600; }
.spreadsheet-meta, .sheet-name, .spreadsheet-actions { color: var(--ap-text-sub); font-size: 12px; }
.sheet-selector { width: min(220px, 42vw); }
.sheet-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.spreadsheet-table-wrap { max-height: 58vh; overflow: auto; background: var(--ap-bg-card); }
.spreadsheet-table { width: max-content; min-width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; font-size: 13px; color: var(--ap-text-main); }
.spreadsheet-table th, .spreadsheet-table td { min-width: 112px; max-width: 280px; height: 34px; padding: 0 10px; overflow: hidden; border-right: 1px solid var(--ap-border-color); border-bottom: 1px solid var(--ap-border-color); text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.spreadsheet-table thead th { position: sticky; top: 0; z-index: 2; background: #F7F0E8; color: var(--ap-text-sub); font-weight: 600; text-align: center; }
.spreadsheet-table tbody tr:hover td, .spreadsheet-table tbody tr:hover .row-number { background: var(--el-color-primary-light-9); }
.spreadsheet-table .row-number { position: sticky; left: 0; z-index: 1; min-width: 44px; width: 44px; padding: 0; background: var(--ap-bg-sidebar); color: var(--ap-text-sub); font-size: 11px; font-weight: 500; text-align: center; }
.spreadsheet-table .corner-cell { z-index: 3; }
.spreadsheet-limit-note { padding: 10px 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary-dark-2); font-size: 12px; }
.spreadsheet-empty { display: grid; min-height: 200px; place-items: center; color: var(--ap-text-sub); font-size: 13px; }
.spreadsheet-message { display: flex; min-height: 230px; align-items: center; justify-content: center; gap: 16px; padding: 24px; color: var(--ap-text-main); }
.spreadsheet-message strong { display: block; margin-bottom: 6px; }
.spreadsheet-message p { max-width: 360px; margin: 0; color: var(--ap-text-sub); font-size: 13px; line-height: 1.6; }
.spreadsheet-actions { border-top: 1px solid var(--ap-border-color); }
.spreadsheet-actions span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-doc {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.doc-icon-section {
  text-align: center;
}
.doc-icon-section h3 {
  margin: 16px 0 8px 0;
  color: var(--ap-text-main);
}
.doc-icon-section p {
  color: var(--ap-text-sub);
  margin-bottom: 24px;
}
.ocr-section {
  background-color: var(--ap-bg-sidebar);
  border-radius: 10px;
  padding: 12px 16px;
  border-left: 4px solid var(--el-color-primary);
}
.ocr-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 8px;
  cursor: pointer;
  user-select: none;
}
.ocr-arrow {
  margin-left: auto;
  transition: transform 0.25s;
}
.ocr-arrow.expanded {
  transform: rotate(90deg);
}
.ocr-content {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  color: var(--ap-text-main);
  max-height: 120px;
  overflow-y: auto;
}
.doc-text-preview {
  background-color: var(--ap-bg-sidebar);
  border-radius: 10px;
  border-left: 4px solid var(--el-color-primary);
  overflow: hidden;
}
.doc-text-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-weight: 600;
  font-size: 13px;
  color: #C4946B;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.doc-text-body {
  padding: 16px;
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--ap-text-main);
  max-height: 50vh;
  overflow-y: auto;
}
.doc-text-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}
.doc-text-actions p {
  color: var(--ap-text-sub);
  font-size: 13px;
  margin: 0;
}
</style>
