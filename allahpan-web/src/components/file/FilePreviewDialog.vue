<template>
  <el-dialog
    v-model="visible"
    class="file-preview-dialog"
    width="min(1120px, calc(100vw - 28px))"
    top="4vh"
    destroy-on-close
  >
    <template #header>
      <div class="preview-dialog-header">
        <FileIcon
          v-if="file"
          :is-folder="false"
          :file-type="file.fileType"
          :file-name="file.fileName"
          :size="38"
        />
        <div class="preview-heading">
          <strong class="ap-file-name" dir="auto" :title="file?.fileName">{{ file?.fileName }}</strong>
          <span>
            {{ previewTypeLabel }}
            <template v-if="file?.fileSize != null"> · {{ formatBytes(file.fileSize) }}</template>
          </span>
        </div>
      </div>
    </template>

    <div class="preview-body" v-loading="loading">
      <!-- 图片预览 -->
      <div v-if="file?.fileType === 'IMAGE'" class="preview-center image-stage">
        <el-image
          v-if="mediaUrl && !mediaError"
          :src="mediaUrl"
          fit="contain"
          class="preview-img"
          :preview-src-list="[mediaUrl]"
          @load="handleMediaLoaded"
          @error="handleImageError"
        />
        <div v-else-if="mediaError" class="media-message">
          <FileIcon :file-type="file?.fileType" :file-name="file?.fileName" :size="64" />
          <strong>图片暂时无法显示</strong>
          <span>原文件仍可正常下载，可能是图片格式不受浏览器支持。</span>
          <el-button type="primary" plain @click="triggerDownload">下载原图片</el-button>
        </div>
      </div>

      <!-- 视频预览 -->
      <div v-else-if="file?.fileType === 'VIDEO'" class="preview-center video-stage">
        <video
          v-if="mediaUrl && !mediaError"
          :src="mediaUrl"
          controls
          preload="metadata"
          playsinline
          class="preview-video"
          @loadeddata="handleMediaLoaded"
          @error="handleMediaError"
        />
        <div v-else-if="mediaError" class="media-message on-dark">
          <FileIcon :file-type="file?.fileType" :file-name="file?.fileName" :size="64" />
          <strong>视频暂时无法播放</strong>
          <span>可能是当前浏览器不支持该视频编码，可以下载原文件播放。</span>
          <el-button type="primary" @click="triggerDownload">下载原视频</el-button>
        </div>
      </div>

      <!-- 音频预览 -->
      <div v-else-if="isAudio" class="audio-preview">
        <FileIcon
          :file-type="file?.fileType"
          :file-name="file?.fileName"
          :size="88"
        />
        <div class="audio-copy">
          <strong class="ap-file-name" dir="auto" :title="file?.fileName">{{ file?.fileName }}</strong>
          <span>{{ previewTypeLabel }} · {{ formatBytes(file?.fileSize) }}</span>
        </div>
        <audio
          v-if="mediaUrl && !mediaError"
          :src="mediaUrl"
          controls
          preload="metadata"
          class="preview-audio"
          @loadedmetadata="handleMediaLoaded"
          @error="handleMediaError"
        />
        <div v-else-if="mediaError" class="audio-error">当前浏览器无法播放此音频编码</div>
        <el-button type="primary" plain @click="triggerDownload">下载原音频</el-button>
      </div>

      <!-- PDF 预览 -->
      <div v-else-if="isPdf" class="pdf-preview">
        <div class="preview-subtoolbar">
          <span>PDF 文档预览</span>
          <el-button link type="primary" @click="triggerDownload">下载原文件</el-button>
        </div>
        <iframe
          v-if="mediaUrl && !mediaError"
          :src="mediaUrl"
          class="preview-pdf"
          :title="`${file?.fileName || 'PDF'} 预览`"
          @load="handleMediaLoaded"
        />
        <div v-else-if="mediaError" class="media-message pdf-message">
          <FileIcon :file-type="file?.fileType" :file-name="file?.fileName" :size="64" />
          <strong>PDF 暂时无法显示</strong>
          <span>原文件仍可正常下载，可以在本地 PDF 阅读器中打开。</span>
          <el-button type="primary" plain @click="triggerDownload">下载 PDF</el-button>
        </div>
      </div>

      <!-- XLSX / CSV 表格预览 -->
      <div v-else-if="isSpreadsheet" class="spreadsheet-preview">
        <div class="spreadsheet-toolbar">
          <div class="spreadsheet-summary">
            <span class="spreadsheet-title">{{ spreadsheetFormatLabel }}</span>
            <span v-if="!loading && !spreadsheetError" class="spreadsheet-meta">
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
          <span v-else-if="spreadsheetSheets[0]" class="sheet-name">
            工作表：<strong>{{ spreadsheetSheets[0] }}</strong>
          </span>
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
          <span class="preview-file-summary">
            <span class="ap-file-name" dir="auto">{{ file?.fileName }}</span>
            <small>({{ formatBytes(file?.fileSize) }})</small>
          </span>
          <el-button type="primary" plain @click="triggerDownload">下载原文件</el-button>
        </div>
      </div>

      <!-- 文档预览：已提取文字时直接展示文本内容 -->
      <div v-else-if="isDocumentPreview && ocrText" class="preview-doc text-document-preview">
        <div class="doc-text-preview">
          <div class="doc-text-header">
            <el-icon size="18" color="#C4946B"><Cpu /></el-icon>
            <div>
              <strong>{{ textPreviewLabel }}</strong>
              <span>{{ textPreviewDescription }}</span>
            </div>
          </div>
          <div class="doc-text-body" :class="{ 'code-content': isCodeLike }" dir="auto">{{ ocrText }}</div>
        </div>
        <div class="doc-text-actions">
          <p class="preview-file-summary">
            <span class="ap-file-name" dir="auto">{{ file?.fileName }}</span>
            <small>({{ formatBytes(file?.fileSize) }})</small>
          </p>
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
          <h3>{{ unsupportedTitle }}</h3>
          <p class="unsupported-description">{{ unsupportedDescription }}</p>
          <p class="preview-file-summary">
            <span class="ap-file-name" dir="auto">{{ file?.fileName }}</span>
            <small>({{ formatBytes(file?.fileSize) }})</small>
          </p>
          <el-button type="primary" @click="triggerDownload">下载到本地查看</el-button>
        </div>
      </div>

      <!-- OCR / AI 识别文字（可折叠，仅 IMAGE 等非 DOCUMENT 文件显示） -->
      <div v-if="ocrText && !isDocumentPreview" class="ocr-section">
        <div class="ocr-header" @click="ocrExpanded = !ocrExpanded">
          <el-icon color="#C4946B"><Cpu /></el-icon>
          <span>识别出的文字</span>
          <small>{{ ocrExpanded ? '收起' : '展开阅读' }}</small>
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
const mediaError = ref(false)
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
const AUDIO_EXTENSIONS = new Set(['mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg', 'opus', 'wma', 'ape', 'amr'])
const CODE_EXTENSIONS = new Set([
  'js', 'jsx', 'ts', 'tsx', 'vue', 'java', 'kt', 'kts', 'py', 'go', 'rs', 'c', 'h', 'cc', 'cpp',
  'cs', 'php', 'rb', 'swift', 'scala', 'sh', 'bash', 'zsh', 'fish', 'sql', 'html', 'htm', 'css',
  'scss', 'sass', 'less', 'xml', 'json', 'yaml', 'yml', 'toml', 'ini', 'properties',
])
const WORD_EXTENSIONS = new Set(['doc', 'docx'])
const ARCHIVE_EXTENSIONS = new Set(['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tgz'])
let spreadsheetWorkbook = null
let spreadsheetXlsx = null

const fileExtension = computed(() => {
  const name = file.value?.fileName || ''
  const dotIndex = name.lastIndexOf('.')
  return dotIndex > -1 && dotIndex < name.length - 1 ? name.slice(dotIndex + 1).toLowerCase() : ''
})
const isPdf = computed(() => fileExtension.value === 'pdf')
const isSpreadsheet = computed(() => isSpreadsheetFile(file.value?.fileName))
const isWordDocument = computed(() => WORD_EXTENSIONS.has(fileExtension.value))
// 兼容历史记录：旧数据可能因客户端没有上报正确 MIME 类型而保存成 OTHER，
// 只要文件名是 DOC/DOCX，仍然按 Word 文档展示其已提取内容。
const isDocumentPreview = computed(() => file.value?.fileType === 'DOCUMENT' || isWordDocument.value)
const isAudio = computed(() => (
  AUDIO_EXTENSIONS.has(fileExtension.value)
  || file.value?.contentType?.toLowerCase().startsWith('audio/')
))
const isCodeLike = computed(() => CODE_EXTENSIONS.has(fileExtension.value))
const spreadsheetFormatLabel = computed(() => (
  fileExtension.value === 'csv' ? 'CSV 数据预览' : 'Excel 表格预览'
))
const previewTypeLabel = computed(() => {
  const extension = fileExtension.value.toUpperCase()
  if (isPdf.value) return 'PDF 文档'
  if (fileExtension.value === 'xlsx') return 'Excel 工作簿'
  if (fileExtension.value === 'csv') return 'CSV 表格'
  if (isAudio.value) return `${extension || '音频'} 音频`
  if (file.value?.fileType === 'IMAGE') return `${extension || '图片'} 图片`
  if (file.value?.fileType === 'VIDEO') return `${extension || '视频'} 视频`
  if (isCodeLike.value) return `${extension || '代码'} 源代码`
  if (['md', 'markdown'].includes(fileExtension.value)) return 'Markdown 文本'
  if (fileExtension.value === 'txt') return '纯文本'
  if (isWordDocument.value) return `${fileExtension.value.toUpperCase()} Word 文档`
  if (['ppt', 'pptx'].includes(fileExtension.value)) return '演示文稿'
  return extension ? `${extension} 文件` : '文件'
})
const textPreviewLabel = computed(() => {
  if (isWordDocument.value) return `${fileExtension.value.toUpperCase()} 文档内容`
  if (isCodeLike.value) return '代码内容'
  if (['md', 'markdown'].includes(fileExtension.value)) return 'Markdown 内容'
  if (fileExtension.value === 'txt') return '文本内容'
  return '提取出的文档文字'
})
const textPreviewDescription = computed(() => (
  isWordDocument.value
    ? '已提取正文内容；字体、图片和复杂排版请下载原文件查看'
    : (isCodeLike.value ? '保留原始换行与缩进' : '以纯文字形式展示，排版可能与原文略有差异')
))
const unsupportedTitle = computed(() => {
  if (ARCHIVE_EXTENSIONS.has(fileExtension.value)) return '暂不支持在线展开压缩包'
  if (isWordDocument.value && Number(file.value?.processStatus || 0) < 2) return '正在准备 Word 文档预览'
  if (isWordDocument.value) return '暂未提取到可预览的文档文字'
  if (['ppt', 'pptx'].includes(fileExtension.value)) return '暂不支持在线播放演示文稿'
  return '该格式暂不支持在线预览'
})
const unsupportedDescription = computed(() => {
  if (ARCHIVE_EXTENSIONS.has(fileExtension.value)) return '下载后解压即可查看其中的文件。'
  if (isWordDocument.value && Number(file.value?.processStatus || 0) < 2) {
    return '文件正在后台解析，稍后重新打开即可查看提取出的正文内容。'
  }
  if (isWordDocument.value) return '当前未提取到正文，或文件内容为空；下载原文件可查看完整排版。'
  if (['ppt', 'pptx'].includes(fileExtension.value)) return '下载原文件可保留动画、字体与页面布局。'
  return '原文件不会受到影响，可以下载到本地使用相应应用打开。'
})
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
  mediaError.value = false
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
  mediaError.value = false
  loading.value = false
}

const handleMediaError = () => {
  mediaError.value = true
  loading.value = false
}

const handleImageError = () => {
  const nextIndex = imageCandidateIndex.value + 1
  if (nextIndex < imageCandidates.value.length) {
    imageCandidateIndex.value = nextIndex
    mediaUrl.value = imageCandidates.value[nextIndex]
  } else {
    mediaError.value = true
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
    ocrText.value = detail.originText || ''

    if (detail.fileType === 'IMAGE') {
      imageCandidates.value = [
        detail.previewUrl ? getPreviewUrl(targetFile.id) : '',
        detail.thumbnailUrl ? getThumbnailUrl(targetFile.id) : '',
        getStreamUrl(targetFile.id),
      ].filter(Boolean)
      mediaUrl.value = imageCandidates.value[0] || ''
    } else if (detail.fileType === 'VIDEO') {
      mediaUrl.value = getStreamUrl(targetFile.id)
    } else if (isAudio.value) {
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
      if (targetFile.fileType === 'IMAGE'
          || targetFile.fileType === 'VIDEO'
          || isAudio.value
          || isPdf.value) {
        mediaError.value = true
      }
      loading.value = false
    }
  }
  if (requestId === previewRequestId && !mediaUrl.value) {
    if (file.value?.fileType === 'IMAGE'
        || file.value?.fileType === 'VIDEO'
        || isAudio.value
        || isPdf.value) {
      mediaError.value = true
    }
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
:global(.file-preview-dialog) {
  max-height: 92vh;
  max-height: 92dvh;
  overflow: hidden;
  border-radius: 18px;
}
:global(.file-preview-dialog .el-dialog__header) {
  margin: 0;
  padding: 14px 52px 12px 18px;
  border-bottom: 1px solid var(--ap-border-color);
}
:global(.file-preview-dialog .el-dialog__body) {
  max-height: calc(92vh - 68px);
  max-height: calc(92dvh - 68px);
  padding: 16px 18px 18px;
  overflow-y: auto;
}
.preview-dialog-header {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 11px;
}
.preview-heading {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}
.preview-heading strong {
  overflow: hidden;
  color: var(--ap-text-main);
  font-size: 15px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-heading > span {
  color: var(--ap-text-sub);
  font-size: 11px;
  line-height: 1.4;
}
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
.image-stage {
  min-height: min(52vh, 480px);
  background-color: #282522;
  background-image:
    linear-gradient(45deg, rgba(255, 255, 255, .025) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(255, 255, 255, .025) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(255, 255, 255, .025) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(255, 255, 255, .025) 75%);
  background-position: 0 0, 0 8px, 8px -8px, -8px 0;
  background-size: 16px 16px;
}
.video-stage { min-height: min(48vh, 440px); }
.preview-img {
  max-width: 100%;
  max-height: 55vh;
}
.preview-video {
  width: 100%;
  max-height: 55vh;
  outline: none;
}
.media-message {
  display: flex;
  max-width: 380px;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: var(--ap-text-main);
  text-align: center;
}
.media-message strong { font-size: 15px; }
.media-message span { color: var(--ap-text-sub); font-size: 12px; line-height: 1.6; }
.media-message.on-dark strong { color: #fff; }
.media-message.on-dark span { color: rgba(255, 255, 255, .72); }
.audio-preview {
  display: flex;
  min-height: 300px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 30px clamp(16px, 5vw, 56px);
  border: 1px solid var(--ap-border-color);
  border-radius: 16px;
  background:
    radial-gradient(circle at 50% 24%, rgba(155, 131, 160, .14), transparent 42%),
    var(--ap-bg-card);
  text-align: center;
}
.audio-copy {
  display: flex;
  width: 100%;
  min-width: 0;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.audio-copy strong {
  max-width: min(680px, 100%);
  color: var(--ap-text-main);
  font-size: 16px;
  line-height: 1.45;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.audio-copy span, .audio-error { color: var(--ap-text-sub); font-size: 12px; }
.preview-audio { width: min(680px, 100%); height: 42px; }
.pdf-preview {
  overflow: hidden;
  border: 1px solid var(--ap-border-color);
  border-radius: 12px;
  background: var(--ap-bg-card);
}
.preview-subtoolbar {
  display: flex;
  min-height: 42px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 12px 0 15px;
  border-bottom: 1px solid var(--ap-border-color);
  background: var(--ap-bg-sidebar);
  color: var(--ap-text-main);
  font-size: 12px;
  font-weight: 600;
}
.preview-pdf {
  width: 100%;
  height: 68vh;
  display: block;
  border: none;
}
.pdf-message { min-height: 340px; margin: 0 auto; justify-content: center; padding: 24px; }
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
.sheet-name strong { color: var(--ap-text-main); font-weight: 600; }
.spreadsheet-table-wrap { max-height: 58vh; overflow: auto; background: var(--ap-bg-card); }
.spreadsheet-table { width: max-content; min-width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; font-size: 13px; color: var(--ap-text-main); }
.spreadsheet-table th, .spreadsheet-table td { min-width: 112px; max-width: 280px; height: 34px; padding: 0 10px; overflow: hidden; border-right: 1px solid var(--ap-border-color); border-bottom: 1px solid var(--ap-border-color); text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.spreadsheet-table thead th { position: sticky; top: 0; z-index: 2; background: #F7F0E8; color: var(--ap-text-sub); font-weight: 600; text-align: center; }
.spreadsheet-table tbody tr:nth-child(even) td { background: color-mix(in srgb, var(--ap-bg-sidebar) 48%, transparent); }
.spreadsheet-table tbody tr:hover td, .spreadsheet-table tbody tr:hover .row-number { background: var(--el-color-primary-light-9); }
.spreadsheet-table .row-number { position: sticky; left: 0; z-index: 1; min-width: 44px; width: 44px; padding: 0; background: var(--ap-bg-sidebar); color: var(--ap-text-sub); font-size: 11px; font-weight: 500; text-align: center; }
.spreadsheet-table .corner-cell { z-index: 3; }
.spreadsheet-limit-note { padding: 10px 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary-dark-2); font-size: 12px; }
.spreadsheet-empty { display: grid; min-height: 200px; place-items: center; color: var(--ap-text-sub); font-size: 13px; }
.spreadsheet-message { display: flex; min-height: 230px; align-items: center; justify-content: center; gap: 16px; padding: 24px; color: var(--ap-text-main); }
.spreadsheet-message strong { display: block; margin-bottom: 6px; }
.spreadsheet-message p { max-width: 360px; margin: 0; color: var(--ap-text-sub); font-size: 13px; line-height: 1.6; }
.spreadsheet-actions { border-top: 1px solid var(--ap-border-color); }
.preview-file-summary { display: flex; min-width: 0; flex: 1; flex-wrap: wrap; align-items: baseline; gap: 4px 7px; }
.preview-file-summary .ap-file-name { color: var(--ap-text-main); }
.preview-file-summary small { flex-shrink: 0; color: var(--ap-text-sub); font-size: 11px; }
.preview-doc {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.text-document-preview {
  width: 100%;
  flex-direction: column;
  align-items: stretch;
  padding: 0;
}
.doc-icon-section {
  width: min(520px, 100%);
  text-align: center;
}
.doc-icon-section h3 {
  margin: 16px 0 8px 0;
  color: var(--ap-text-main);
}
.doc-icon-section .unsupported-description {
  max-width: 420px;
  color: var(--ap-text-sub);
  margin: 0 auto 14px;
  font-size: 13px;
  line-height: 1.65;
}
.doc-icon-section .preview-file-summary {
  justify-content: center;
  margin: 0 auto 22px;
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
  cursor: pointer;
  user-select: none;
}
.ocr-header small { color: var(--ap-text-sub); font-size: 11px; font-weight: 400; }
.ocr-arrow {
  margin-left: auto;
  transition: transform 0.25s;
}
.ocr-arrow.expanded {
  transform: rotate(90deg);
}
.ocr-content {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--ap-border-color);
  font-size: 13px;
  line-height: 1.72;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--ap-text-main);
  max-height: 220px;
  overflow-y: auto;
  user-select: text;
}
.doc-text-preview {
  background-color: var(--ap-bg-sidebar);
  border-radius: 10px;
  border-left: 4px solid var(--el-color-primary);
  overflow: hidden;
}
.doc-text-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
  color: #C4946B;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.doc-text-header > div { display: flex; flex-direction: column; gap: 2px; }
.doc-text-header strong { font-size: 13px; line-height: 1.4; }
.doc-text-header span { color: var(--ap-text-sub); font-size: 11px; line-height: 1.45; font-weight: 400; }
.doc-text-body {
  padding: clamp(16px, 2.4vw, 28px);
  font-size: 14px;
  line-height: 1.82;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--ap-text-main);
  max-height: 54vh;
  overflow-y: auto;
  user-select: text;
}
.doc-text-body.code-content {
  background: #FCFAF7;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 13px;
  line-height: 1.65;
  tab-size: 2;
  direction: ltr;
  text-align: left;
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

@media (max-width: 768px) {
  :global(.file-preview-dialog) {
    margin-top: 8px;
    max-height: calc(100dvh - 16px);
    border-radius: 15px;
  }
  :global(.file-preview-dialog .el-dialog__header) { padding: 11px 46px 10px 12px; }
  :global(.file-preview-dialog .el-dialog__body) {
    max-height: calc(100dvh - 76px);
    padding: 10px 10px 14px;
  }
  .preview-heading strong {
    display: -webkit-box;
    overflow: hidden;
    white-space: normal;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
  .preview-body { min-height: 220px; gap: 10px; }
  .preview-center { max-height: 64vh; padding: 6px; border-radius: 10px; }
  .image-stage, .video-stage { min-height: 45vh; }
  .preview-img, .preview-video { max-height: 62vh; }
  .preview-pdf { height: 70vh; }
  .preview-subtoolbar { min-height: 40px; padding-left: 12px; }
  .audio-preview { min-height: 270px; gap: 14px; padding: 24px 14px; }
  .preview-doc { padding: 24px 0; }
  .text-document-preview { padding: 0; }
  .spreadsheet-toolbar, .spreadsheet-actions { align-items: flex-start; flex-direction: column; padding: 10px 12px; }
  .sheet-selector { width: 100%; }
  .spreadsheet-table-wrap { max-height: 60vh; }
  .spreadsheet-table { font-size: 12px; }
  .spreadsheet-table th, .spreadsheet-table td { min-width: 104px; height: 36px; padding: 0 8px; }
  .spreadsheet-actions :deep(.el-button) { width: 100%; }
  .doc-text-body { max-height: 58vh; padding: 16px 14px; font-size: 14px; line-height: 1.78; }
  .doc-text-actions { align-items: stretch; flex-direction: column; gap: 10px; }
  .doc-text-actions :deep(.el-button) { width: 100%; }
}
</style>
