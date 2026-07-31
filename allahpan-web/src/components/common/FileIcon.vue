<template>
  <div
    class="file-icon-wrapper"
    :style="{ width: `${size}px`, height: `${size}px`, '--icon-size': `${size}px` }"
    role="img"
    :aria-label="typeMeta.description"
    :title="typeMeta.description"
  >
    <div v-if="isFolder" class="folder-icon">
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path class="folder-back" d="M7 18c0-3.3 2.7-6 6-6h15l5.5 6H51c3.3 0 6 2.7 6 6v25c0 3.3-2.7 6-6 6H13c-3.3 0-6-2.7-6-6V18Z" />
        <path class="folder-front" d="M7 26c0-3.3 2.7-6 6-6h38c3.3 0 6 2.7 6 6v23c0 3.3-2.7 6-6 6H13c-3.3 0-6-2.7-6-6V26Z" />
      </svg>
      <span class="format-label">文件夹</span>
    </div>

    <div v-else-if="displayThumbUrl" class="thumbnail-icon">
      <el-image :src="displayThumbUrl" fit="cover" class="img-thumb" lazy>
        <template #error>
          <div class="thumbnail-fallback" :style="{ '--file-accent': typeMeta.color, '--file-soft': typeMeta.soft }">
            <FileGlyph :category="typeMeta.category" />
          </div>
        </template>
      </el-image>
      <span class="format-label">{{ typeMeta.label }}</span>
    </div>

    <div v-else class="document-icon" :style="{ '--file-accent': typeMeta.color, '--file-soft': typeMeta.soft }">
      <div class="document-paper">
        <span class="document-fold" />
        <FileGlyph :category="typeMeta.category" />
        <span class="format-label">{{ typeMeta.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h } from 'vue'
import { authenticatedMediaUrl } from '@/api/file'

const TYPE_STYLES = {
  folder: { color: '#B98256', soft: '#F7E4CF', description: '文件夹' },
  pdf: { color: '#C87870', soft: '#F6DEDA', description: 'PDF 文档' },
  word: { color: '#7899B8', soft: '#DDE9F2', description: '文档文件' },
  sheet: { color: '#729F85', soft: '#DAEBDD', description: '表格文件' },
  slide: { color: '#D19367', soft: '#F7E2D0', description: '演示文件' },
  text: { color: '#9A9187', soft: '#EBE7E1', description: '文本文件' },
  code: { color: '#8B80B0', soft: '#E5E0F2', description: '代码文件' },
  image: { color: '#CD9187', soft: '#F3DDD8', description: '图片文件' },
  video: { color: '#857AAD', soft: '#E3DDF0', description: '视频文件' },
  audio: { color: '#9B83A0', soft: '#EADDEB', description: '音频文件' },
  archive: { color: '#AD8A6C', soft: '#EEE2D7', description: '压缩文件' },
  design: { color: '#B284A8', soft: '#F0DDEB', description: '设计文件' },
  font: { color: '#9A89B5', soft: '#E8E0F1', description: '字体文件' },
  book: { color: '#A5886C', soft: '#EFE2D5', description: '电子书' },
  data: { color: '#6E98A7', soft: '#D9E9EC', description: '数据文件' },
  app: { color: '#948875', soft: '#E9E2D9', description: '安装包' },
  file: { color: '#9E968B', soft: '#ECE8E2', description: '文件' },
}

const extensionGroups = {
  pdf: ['pdf'],
  word: ['doc', 'docx', 'odt', 'rtf', 'wps'],
  sheet: ['xls', 'xlsx', 'xlsm', 'xlsb', 'csv', 'ods', 'et'],
  slide: ['ppt', 'pptx', 'pps', 'ppsx', 'odp', 'key'],
  text: ['txt', 'md', 'markdown', 'log', 'json', 'xml', 'yaml', 'yml', 'ini', 'conf', 'properties'],
  code: ['js', 'mjs', 'cjs', 'ts', 'jsx', 'tsx', 'vue', 'html', 'htm', 'css', 'scss', 'sass', 'less', 'java', 'py', 'go', 'rs', 'c', 'cc', 'cpp', 'h', 'hpp', 'cs', 'php', 'rb', 'swift', 'kt', 'kts', 'sh', 'bash', 'zsh', 'sql'],
  image: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'avif', 'heic', 'raw', 'cr2', 'nef'],
  video: ['mp4', 'mov', 'mkv', 'avi', 'webm', 'flv', 'wmv', 'm4v', '3gp', 'mpeg', 'mpg'],
  audio: ['mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg', 'opus', 'wma', 'ape', 'amr'],
  archive: ['zip', 'rar', '7z', 'tar', 'gz', 'tgz', 'bz2', 'xz', 'iso', 'cab', 'jar', 'war'],
  design: ['psd', 'ai', 'sketch', 'fig', 'xd', 'eps'],
  font: ['ttf', 'otf', 'woff', 'woff2', 'eot'],
  book: ['epub', 'mobi', 'azw', 'azw3'],
  data: ['db', 'sqlite', 'sqlite3', 'db3', 'parquet', 'dbf'],
  app: ['apk', 'exe', 'msi', 'dmg', 'pkg', 'deb', 'rpm'],
}

const categoryByExtension = Object.entries(extensionGroups).reduce((result, [category, extensions]) => {
  extensions.forEach((extension) => { result[extension] = category })
  return result
}, {})

const labelOverrides = {
  jpeg: 'JPG', markdown: 'MD', mjs: 'JS', cjs: 'JS', htm: 'HTML', cc: 'C++', cpp: 'C++',
  sqlite: 'DB', sqlite3: 'DB', db3: 'DB', properties: 'CFG', yaml: 'YAML', yml: 'YAML',
}

const props = defineProps({
  isFolder: { type: [Boolean, Number], default: false },
  fileType: { type: String, default: 'OTHER' },
  fileName: { type: String, default: '' },
  thumbUrl: { type: String, default: '' },
  size: { type: Number, default: 48 },
})

const extension = computed(() => {
  const name = props.fileName.trim()
  const dotIndex = name.lastIndexOf('.')
  if (dotIndex <= 0 || dotIndex === name.length - 1) return ''
  return name.slice(dotIndex + 1).toLowerCase()
})

const typeMeta = computed(() => {
  const fallback = { IMAGE: 'image', VIDEO: 'video', DOCUMENT: 'word' }[props.fileType] || 'file'
  const category = categoryByExtension[extension.value] || fallback
  const style = TYPE_STYLES[category]
  const rawLabel = labelOverrides[extension.value] || extension.value.toUpperCase()
  const label = rawLabel && rawLabel.length <= 5 ? rawLabel : ({ image: 'IMG', video: 'VIDEO', word: 'DOC', file: 'FILE' }[category] || 'FILE')
  return { category, label, ...style, description: `${label} · ${style.description}` }
})

const displayThumbUrl = computed(() => {
  if (!props.thumbUrl || props.fileType !== 'IMAGE') return ''
  return authenticatedMediaUrl(props.thumbUrl)
})

const FileGlyph = defineComponent({
  name: 'FileGlyph',
  props: { category: { type: String, required: true } },
  setup(glyphProps) {
    const stroke = { fill: 'none', stroke: 'currentColor', 'stroke-width': '3.4', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }
    const draw = () => {
      switch (glyphProps.category) {
        case 'pdf': return [h('path', { ...stroke, d: 'M21 38c4-10 6-18 8-22 2 5 4 11 10 13-5 2-11 2-16 1-3 3-5 5-7 7' })]
        case 'sheet': return [h('rect', { ...stroke, x: '17', y: '16', width: '30', height: '26', rx: '3' }), h('path', { ...stroke, d: 'M17 25h30M27 16v26M37 16v26' })]
        case 'slide': return [h('rect', { ...stroke, x: '15', y: '17', width: '34', height: '23', rx: '3' }), h('path', { ...stroke, d: 'M27 46h10M32 40v6M23 24h18' })]
        case 'image': return [h('rect', { ...stroke, x: '16', y: '17', width: '32', height: '27', rx: '4' }), h('circle', { fill: 'currentColor', cx: '39', cy: '25', r: '3' }), h('path', { ...stroke, d: 'm19 40 9-9 6 6 5-5 6 8' })]
        case 'video': return [h('rect', { ...stroke, x: '15', y: '18', width: '29', height: '25', rx: '4' }), h('path', { fill: 'currentColor', d: 'm29 25 9 5.5-9 5.5V25Z' }), h('path', { ...stroke, d: 'm44 26 5-3v15l-5-3' })]
        case 'audio': return [h('path', { ...stroke, d: 'M35 16v19a6 6 0 1 1-4-5.7V21l13-3v15a6 6 0 1 1-4-5.7V15l-5 1Z' })]
        case 'archive': return [h('path', { ...stroke, d: 'M20 15h24l3 8-3 26H20l-3-26 3-8ZM17 23h30M30 29h4m-4 6h4m-4 6h4' })]
        case 'code': return [h('path', { ...stroke, d: 'm27 20-9 12 9 12M37 20l9 12-9 12M35 17l-6 30' })]
        case 'design': return [h('path', { ...stroke, d: 'm32 15 16 17-16 17L16 32l16-17ZM23 32h18M32 23v18' })]
        case 'font': return [h('path', { ...stroke, d: 'm20 43 12-25 12 25M25 34h14M44 20h5v8M49 24H39' })]
        case 'book': return [h('path', { ...stroke, d: 'M18 19c6-3 11-1 14 3v23c-3-4-8-6-14-3V19ZM46 19c-6-3-11-1-14 3v23c3-4 8-6 14-3V19Z' })]
        case 'data': return [h('ellipse', { ...stroke, cx: '32', cy: '19', rx: '14', ry: '5' }), h('path', { ...stroke, d: 'M18 19v18c0 2.8 6.3 5 14 5s14-2.2 14-5V19M18 28c0 2.8 6.3 5 14 5s14-2.2 14-5' })]
        case 'app': return [h('rect', { ...stroke, x: '17', y: '17', width: '30', height: '30', rx: '7' }), ...[[24, 24], [32, 24], [40, 24], [24, 32], [32, 32], [40, 32], [24, 40], [32, 40], [40, 40]].map(([cx, cy]) => h('circle', { fill: 'currentColor', cx, cy, r: '2' }))]
        case 'text': return [h('path', { ...stroke, d: 'M21 20h22M21 28h22M21 36h14' })]
        case 'word': return [h('path', { ...stroke, d: 'm19 19 4 24 5-14 4 14 5-24 4 24 4-24' })]
        default: return [h('path', { ...stroke, d: 'M21 21h22M21 30h22M21 39h14' })]
      }
    }
    return () => h('svg', { class: 'file-glyph', viewBox: '0 0 64 64', 'aria-hidden': 'true' }, draw())
  },
})
</script>

<style scoped>
.file-icon-wrapper { display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.folder-icon, .document-icon, .thumbnail-icon { width: 100%; height: 100%; position: relative; color: var(--file-accent); }
.folder-icon svg { width: 100%; height: 100%; filter: drop-shadow(0 3px 4px rgba(96, 66, 44, 0.12)); }
.folder-back { fill: #F6DEC5; }
.folder-front { fill: #C18A5E; }
.folder-icon .format-label { background: #99633F; color: #fffaf4; }
.document-icon { display: flex; align-items: center; justify-content: center; }
.document-paper { position: relative; width: 76%; height: 90%; overflow: hidden; border: 1px solid color-mix(in srgb, var(--file-accent) 27%, white); border-radius: calc(var(--icon-size) * .13); background: #fffdfa; box-shadow: 0 calc(var(--icon-size) * .045) calc(var(--icon-size) * .09) rgba(61, 50, 38, .12); }
.document-fold { position: absolute; top: -1px; right: -1px; width: 29%; height: 25%; background: var(--file-soft); clip-path: polygon(0 0, 100% 100%, 0 100%); }
.file-glyph { position: absolute; top: 15%; left: 17%; width: 66%; height: 49%; color: var(--file-accent); }
.format-label { position: absolute; z-index: 2; right: 9%; bottom: 9%; left: 9%; display: flex; align-items: center; justify-content: center; min-height: 20%; padding: 0 3%; overflow: hidden; border-radius: calc(var(--icon-size) * .07); background: var(--file-accent); color: white; font-size: max(7px, calc(var(--icon-size) * .165)); font-weight: 800; line-height: 1; letter-spacing: .02em; text-overflow: clip; white-space: nowrap; }
.thumbnail-icon { overflow: hidden; border: 1px solid var(--ap-border-color); border-radius: calc(var(--icon-size) * .14); background: var(--file-soft); box-shadow: 0 calc(var(--icon-size) * .045) calc(var(--icon-size) * .09) rgba(61, 50, 38, .1); }
.img-thumb { width: 100%; height: 100%; display: block; }
.thumbnail-icon .format-label { right: 7%; bottom: 7%; left: auto; width: auto; min-width: 34%; padding: 0 7%; background: color-mix(in srgb, var(--file-accent) 88%, #31241b); box-shadow: 0 1px 3px rgba(32, 21, 14, .2); }
.thumbnail-fallback { width: 100%; height: 100%; position: relative; color: var(--file-accent); }
.thumbnail-fallback .file-glyph { top: 13%; left: 17%; }
@supports not (color: color-mix(in srgb, black, white)) { .document-paper { border-color: var(--file-soft); } .thumbnail-icon .format-label { background: var(--file-accent); } }
</style>
