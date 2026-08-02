<template>
  <section class="search-filters" aria-label="搜索筛选">
    <div v-if="!isMobile" class="desktop-filter-row">
      <el-select
        :model-value="filters.fileType || 'ALL'"
        class="quick-select type-select"
        size="small"
        aria-label="文件类型筛选"
        @change="changeFileType"
      >
        <el-option :label="`全部类型${total ? `（${total}）` : ''}`" value="ALL" />
        <el-option
          v-for="type in FILE_TYPES"
          :key="type.value"
          :label="`${type.label}${typeCount(type.value) ? `（${typeCount(type.value)}）` : ''}`"
          :value="type.value"
        />
      </el-select>
      <el-select
        :model-value="filters.timePreset || detectTimePreset(filters)"
        class="quick-select"
        size="small"
        aria-label="创建时间筛选"
        @change="changeTimePreset"
      >
        <el-option v-for="item in TIME_PRESETS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        :model-value="detectSizePreset(filters)"
        class="quick-select"
        size="small"
        aria-label="文件大小筛选"
        @change="changeSizePreset"
      >
        <el-option v-for="item in SIZE_PRESETS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        :model-value="filters.searchScope || 'all'"
        class="quick-select scope-select"
        size="small"
        aria-label="搜索范围筛选"
        @change="(value) => quickChange({ searchScope: value })"
      >
        <el-option v-for="item in SCOPE_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        :model-value="sortValue"
        class="quick-select sort-select"
        size="small"
        aria-label="搜索结果排序"
        @change="changeSort"
      >
        <el-option v-for="item in SORT_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button
        class="advanced-button"
        :type="hasAdvancedFilter ? 'primary' : 'default'"
        plain
        size="small"
        :icon="Filter"
        @click="openPanel"
      >
        高级筛选<span v-if="expressionCount"> {{ expressionCount }}</span>
      </el-button>
      <el-button v-if="activeFilterCount > 0" text size="small" @click="$emit('reset')">重置</el-button>
    </div>

    <div v-else class="mobile-filter-row">
      <el-button
        class="mobile-filter-button"
        :type="activeFilterCount > 0 ? 'primary' : 'default'"
        plain
        :icon="Filter"
        @click="openPanel"
      >
        筛选<span v-if="activeFilterCount"> {{ activeFilterCount }}</span>
      </el-button>
      <el-select
        :model-value="sortValue"
        class="mobile-sort-select"
        size="small"
        aria-label="搜索结果排序"
        @change="changeSort"
      >
        <el-option v-for="item in SORT_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <span class="filter-result-count">{{ total }} 项</span>
    </div>

    <div v-if="activeChips.length" class="active-chips" aria-label="当前筛选条件">
      <span class="chips-label">当前条件</span>
      <button
        v-for="chip in activeChips"
        :key="chip.key"
        type="button"
        class="filter-chip"
        :aria-label="`移除${chip.label}`"
        @click="removeChip(chip.key)"
      >
        {{ chip.label }} <span aria-hidden="true">×</span>
      </button>
    </div>

    <el-dialog
      v-if="!isMobile"
      v-model="panelVisible"
      title="高级筛选"
      width="min(720px, calc(100vw - 32px))"
      destroy-on-close
    >
      <FilterPanel
        v-if="draft"
        v-model="draft"
        :expression-count="expressionCountOf(draft?.filterExpression)"
        @reset="resetFromPanel"
      />
      <template #footer>
        <el-button @click="panelVisible = false">取消</el-button>
        <el-button type="primary" @click="applyPanel">应用筛选</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-else
      v-model="panelVisible"
      title="筛选条件"
      direction="btt"
      size="min(90vh, 760px)"
      class="mobile-filter-drawer"
      destroy-on-close
    >
      <FilterPanel
        v-if="draft"
        v-model="draft"
        :expression-count="expressionCountOf(draft?.filterExpression)"
        @reset="resetFromPanel"
      />
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="panelVisible = false">取消</el-button>
          <el-button type="primary" @click="applyPanel">应用筛选</el-button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, ref, resolveComponent, watch } from 'vue'
import { Filter } from '@element-plus/icons-vue'
import { useResponsive } from '@/composables/useResponsive'
import SearchExpressionBuilder from './SearchExpressionBuilder.vue'

const props = defineProps({
  filters: { type: Object, required: true },
  total: { type: Number, default: 0 },
  typeAggregations: { type: Array, default: () => [] },
})

const emit = defineEmits(['change', 'reset'])
const { isMobile } = useResponsive()

const FILE_TYPES = [
  { value: 'IMAGE', label: '图片' },
  { value: 'VIDEO', label: '视频' },
  { value: 'DOCUMENT', label: '文档' },
  { value: 'OTHER', label: '其他' },
]
const TIME_PRESETS = [
  { value: 'all', label: '不限时间' },
  { value: 'today', label: '今天' },
  { value: '7d', label: '最近 7 天' },
  { value: '30d', label: '最近 30 天' },
  { value: '1y', label: '最近 1 年' },
  { value: 'custom', label: '自定义时间' },
]
const SIZE_PRESETS = [
  { value: 'all', label: '不限大小' },
  { value: 'lt10m', label: '小于 10 MB' },
  { value: '10m100m', label: '10 MB - 100 MB' },
  { value: '100m1g', label: '100 MB - 1 GB' },
  { value: 'gt1g', label: '大于 1 GB' },
]
const SCOPE_OPTIONS = [
  { value: 'all', label: '搜索全部内容' },
  { value: 'name', label: '仅搜索文件名' },
  { value: 'content', label: '仅搜索文件内容' },
]
const SORT_OPTIONS = [
  { value: 'relevance:desc', label: '相关度最高' },
  { value: 'fileName:asc', label: '文件名升序' },
  { value: 'fileName:desc', label: '文件名降序' },
  { value: 'createTime:desc', label: '创建时间最新' },
  { value: 'createTime:asc', label: '创建时间最早' },
  { value: 'fileSize:desc', label: '文件最大优先' },
  { value: 'fileSize:asc', label: '文件最小优先' },
]

const panelVisible = ref(false)
const draft = ref(null)

const clone = (value) => {
  if (value == null) return value
  return JSON.parse(JSON.stringify(value))
}

const sortValue = computed(() => `${props.filters.sortBy || 'relevance'}:${props.filters.sortOrder || 'desc'}`)
const expressionCount = computed(() => expressionCountOf(props.filters.filterExpression))
const hasAdvancedFilter = computed(() => expressionCount.value > 0 || props.filters.timePreset === 'custom')
const activeFilterCount = computed(() => {
  let count = 0
  if (props.filters.fileType) count++
  if (props.filters.minSize != null || props.filters.maxSize != null) count++
  if (props.filters.startTime || props.filters.endTime) count++
  if (props.filters.searchScope && props.filters.searchScope !== 'all') count++
  if (expressionCount.value) count++
  return count
})

const typeCount = (type) => props.typeAggregations.find((item) => item.type === type)?.count || 0

const quickChange = (patch) => {
  emit('change', { ...clone(props.filters), ...patch })
}

const changeFileType = (value) => quickChange({ fileType: value === 'ALL' ? '' : value })
const changeTimePreset = (value) => {
  if (value === 'custom') {
    draft.value = clone(props.filters)
    if (!draft.value.filterExpression) {
      draft.value.filterExpression = { type: 'group', id: `root-${Date.now()}`, logic: 'AND', children: [] }
    }
    draft.value.timePreset = 'custom'
    panelVisible.value = true
    return
  }
  quickChange({ timePreset: value })
}

const sizeRange = (value) => {
  const MB = 1024 * 1024
  const GB = 1024 * MB
  switch (value) {
    case 'lt10m': return { minSize: null, maxSize: 10 * MB - 1 }
    case '10m100m': return { minSize: 10 * MB, maxSize: 100 * MB - 1 }
    case '100m1g': return { minSize: 100 * MB, maxSize: 1 * GB - 1 }
    case 'gt1g': return { minSize: 1 * GB, maxSize: null }
    default: return { minSize: null, maxSize: null }
  }
}

const changeSizePreset = (value) => quickChange({ sizePreset: value, ...sizeRange(value) })

const changeSort = (value) => {
  const [sortBy, sortOrder] = value.split(':')
  quickChange({ sortBy, sortOrder })
}

const detectSizePreset = (filters) => {
  if (filters.sizePreset) return filters.sizePreset
  const ranges = SIZE_PRESETS.map((item) => ({ value: item.value, ...sizeRange(item.value) }))
  return ranges.find((item) => item.minSize === (filters.minSize ?? null)
    && item.maxSize === (filters.maxSize ?? null))?.value || 'all'
}

const detectTimePreset = (filters) => filters.timePreset || (filters.startTime || filters.endTime ? 'custom' : 'all')

const expressionCountOf = (group) => {
  if (!group?.children?.length) return 0
  return group.children.reduce((count, child) => {
    if (child.type === 'group') return count + expressionCountOf(child)
    if (!hasExpressionValue(child.value)) return count
    return count + 1
  }, 0)
}

const hasExpressionValue = (value) => value !== '' && value != null
  && (!Array.isArray(value) || (value.length > 0 && value.every((item) => item !== '' && item != null)))

const cleanExpression = (group) => {
  if (!group?.children?.length) return null
  const children = group.children.map((child) => {
    if (child.type === 'group') {
      const nested = cleanExpression(child)
      return nested ? { type: 'group', logic: child.logic, children: nested.children } : null
    }
    if (!hasExpressionValue(child.value)) return null
    return { type: 'condition', field: child.field, operator: child.operator, value: child.value }
  }).filter(Boolean)
  return children.length ? { type: 'group', logic: group.logic || 'AND', children } : null
}

const openPanel = () => {
  draft.value = clone(props.filters)
  if (!draft.value.filterExpression) {
    draft.value.filterExpression = { type: 'group', id: `root-${Date.now()}`, logic: 'AND', children: [] }
  }
  panelVisible.value = true
}

const applyPanel = () => {
  const next = clone(draft.value || props.filters)
  next.filterExpression = cleanExpression(next.filterExpression)
  if (next.timePreset === 'custom') {
    next.timePreset = next.startTime || next.endTime ? 'custom' : 'all'
  }
  emit('change', next)
  panelVisible.value = false
}

const resetFromPanel = () => {
  const next = clone(props.filters)
  next.filterExpression = null
  next.startTime = ''
  next.endTime = ''
  next.timePreset = 'all'
  emit('change', next)
  panelVisible.value = false
}

const removeChip = (key) => {
  const next = clone(props.filters)
  if (key === 'fileType') next.fileType = ''
  if (key === 'size') {
    next.minSize = null
    next.maxSize = null
    next.sizePreset = 'all'
  }
  if (key === 'time') {
    next.startTime = ''
    next.endTime = ''
    next.timePreset = 'all'
  }
  if (key === 'scope') next.searchScope = 'all'
  if (key === 'expression') next.filterExpression = null
  emit('change', next)
}

const activeChips = computed(() => {
  const chips = []
  const type = FILE_TYPES.find((item) => item.value === props.filters.fileType)
  if (type) chips.push({ key: 'fileType', label: type.label })
  const size = SIZE_PRESETS.find((item) => item.value === detectSizePreset(props.filters))
  if (size && size.value !== 'all') chips.push({ key: 'size', label: size.label })
  const time = TIME_PRESETS.find((item) => item.value === detectTimePreset(props.filters))
  if (time && time.value !== 'all') chips.push({ key: 'time', label: time.label })
  const scope = SCOPE_OPTIONS.find((item) => item.value === props.filters.searchScope)
  if (scope && scope.value !== 'all') chips.push({ key: 'scope', label: scope.label })
  if (expressionCount.value) chips.push({ key: 'expression', label: `高级条件 ${expressionCount.value}` })
  return chips
})

const FilterPanel = defineComponent({
  name: 'SearchFilterPanel',
  props: {
    modelValue: { type: Object, required: true },
    expressionCount: { type: Number, default: 0 },
  },
  emits: ['update:modelValue', 'reset'],
  setup(panelProps, { emit: panelEmit }) {
    const DatePicker = resolveComponent('el-date-picker')
    const Button = resolveComponent('el-button')
    const Select = resolveComponent('el-select')
    const Option = resolveComponent('el-option')
    const model = computed({
      get: () => panelProps.modelValue,
      set: (value) => panelEmit('update:modelValue', value),
    })
    const update = (key, value) => {
      model.value = { ...clone(model.value), [key]: value }
    }
    const updateMany = (patch) => {
      model.value = { ...clone(model.value), ...patch }
    }
    const select = (value, options, className, ariaLabel, onChange = (next) => update('value', next)) => h(Select, {
      modelValue: value,
      'onUpdate:modelValue': onChange,
      class: className,
      size: 'small',
      'aria-label': ariaLabel,
    }, () => options.map((option) => h(Option, {
      key: option.value,
      label: option.label,
      value: option.value,
    })))
    return () => h('div', { class: 'filter-panel' }, [
      isMobile.value ? h('div', { class: 'panel-section mobile-basic-panel' }, [
        h('div', { class: 'panel-section-title' }, [
          h('strong', '基础筛选'),
          h('span', '可与高级表达式组合'),
        ]),
        h('div', { class: 'panel-basic-grid' }, [
          select(
            model.value.fileType || 'ALL',
            [{ value: 'ALL', label: '全部类型' }, ...FILE_TYPES],
            'panel-select',
            '文件类型筛选',
            (value) => update('fileType', value === 'ALL' ? '' : value),
          ),
          select(
            detectTimePreset(model.value),
            TIME_PRESETS,
            'panel-select',
            '创建时间筛选',
            (value) => updateMany({
              timePreset: value,
              ...(value === 'custom' ? {} : { startTime: '', endTime: '' }),
            }),
          ),
          select(
            detectSizePreset(model.value),
            SIZE_PRESETS,
            'panel-select',
            '文件大小筛选',
            (value) => updateMany({ sizePreset: value, ...sizeRange(value) }),
          ),
          select(
            model.value.searchScope || 'all',
            SCOPE_OPTIONS,
            'panel-select',
            '搜索范围筛选',
            (value) => update('searchScope', value),
          ),
        ]),
      ]) : null,
      h('div', { class: 'panel-section' }, [
        h('div', { class: 'panel-section-title' }, [
          h('strong', '自定义时间范围'),
          h('span', '可与高级表达式同时生效'),
        ]),
        h('div', { class: 'custom-time-row' }, [
          h(DatePicker, {
            modelValue: model.value.startTime || '',
            'onUpdate:modelValue': (value) => update('startTime', value || ''),
            type: 'datetime',
            'value-format': 'YYYY-MM-DD HH:mm:ss',
            placeholder: '开始时间',
            clearable: true,
          }),
          h('span', '至'),
          h(DatePicker, {
            modelValue: model.value.endTime || '',
            'onUpdate:modelValue': (value) => update('endTime', value || ''),
            type: 'datetime',
            'value-format': 'YYYY-MM-DD HH:mm:ss',
            placeholder: '结束时间',
            clearable: true,
          }),
        ]),
      ]),
      h('div', { class: 'panel-section' }, [
        h('div', { class: 'panel-section-title' }, [
          h('strong', '自定义表达式'),
          h('span', `支持嵌套 AND / OR，当前有效条件 ${panelProps.expressionCount} 项`),
        ]),
        h(SearchExpressionBuilder, {
          group: model.value.filterExpression,
          onUpdate: () => panelEmit('update:modelValue', { ...model.value }),
        }),
      ]),
      h('div', { class: 'panel-hint' }, '条件会与上方的基础筛选同时生效；表达式中的多个条件可使用 AND / OR 组合。'),
      h('div', { class: 'panel-reset' }, [
        h(Button, { text: true, size: 'small', onClick: () => panelEmit('reset') }, () => '清空高级条件'),
      ]),
    ])
  },
})

watch(() => props.filters, (value) => {
  if (!panelVisible.value) draft.value = clone(value)
}, { deep: true })
</script>

<style scoped>
.search-filters {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 18px;
}
.desktop-filter-row,
.mobile-filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.quick-select { width: 126px; }
.type-select { width: 142px; }
.scope-select { width: 144px; }
.sort-select { width: 144px; }
.advanced-button { margin-left: auto; }
.active-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.chips-label { color: var(--ap-text-sub); font-size: 12px; }
.filter-chip {
  min-height: 28px;
  padding: 3px 8px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 14px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary-dark-2);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.filter-chip:hover { background: var(--el-color-primary-light-8); }
.mobile-filter-row { flex-wrap: nowrap; }
.mobile-filter-button { flex: 0 0 auto; }
.mobile-sort-select { width: 142px; flex: 0 0 142px; }
.filter-result-count { margin-left: auto; color: var(--ap-text-sub); font-size: 12px; white-space: nowrap; }
.filter-panel { display: flex; flex-direction: column; gap: 18px; }
.panel-section { display: flex; flex-direction: column; gap: 10px; }
.panel-section-title { display: flex; align-items: baseline; gap: 8px; }
.panel-section-title strong { color: var(--ap-text-main); font-size: 14px; }
.panel-section-title span { color: var(--ap-text-sub); font-size: 12px; }
.custom-time-row { display: flex; align-items: center; gap: 8px; }
.custom-time-row :deep(.el-date-editor) { flex: 1 1 0; min-width: 0; }
.custom-time-row > span { color: var(--ap-text-sub); font-size: 12px; }
.panel-hint { color: var(--ap-text-sub); font-size: 12px; line-height: 1.6; }
.panel-reset { display: flex; justify-content: flex-end; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
.panel-basic-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.panel-select { width: 100%; }

@media (max-width: 768px) {
  .search-filters { gap: 8px; margin-bottom: 12px; }
  .active-chips { gap: 5px; }
  .filter-chip { min-height: 30px; }
  .custom-time-row { align-items: stretch; flex-direction: column; }
  .custom-time-row > span { text-align: center; }
}
</style>
