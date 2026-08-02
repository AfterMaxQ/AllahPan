<template>
  <section class="expression-group" :class="{ nested: depth > 0 }">
    <div class="group-header">
      <div class="group-title">
        <span v-if="depth > 0" class="group-label">条件组</span>
        <el-select v-model="group.logic" size="small" class="logic-select" aria-label="条件组合逻辑">
          <el-option label="满足全部条件（AND）" value="AND" />
          <el-option label="满足任一条件（OR）" value="OR" />
        </el-select>
      </div>
      <el-button
        v-if="depth > 0"
        text
        type="danger"
        size="small"
        :icon="Delete"
        aria-label="删除条件组"
        @click="$emit('remove')"
      >
        删除分组
      </el-button>
    </div>

    <div v-if="group.children.length === 0" class="group-empty">
      暂无条件，可以添加一个条件或嵌套分组。
    </div>

    <div v-for="(child, index) in group.children" :key="child.id" class="expression-child">
      <SearchExpressionBuilder
        v-if="child.type === 'group'"
        :group="child"
        :depth="depth + 1"
        @remove="removeChild(index)"
      />

      <div v-else class="condition-row">
        <el-select
          v-model="child.field"
          size="small"
          class="field-select"
          aria-label="筛选字段"
          @change="resetCondition(child)"
        >
          <el-option v-for="field in FIELD_OPTIONS" :key="field.value" :label="field.label" :value="field.value" />
        </el-select>
        <el-select
          v-model="child.operator"
          size="small"
          class="operator-select"
          aria-label="筛选操作"
          @change="resetConditionValue(child)"
        >
          <el-option
            v-for="operator in operatorsFor(child)"
            :key="operator.value"
            :label="operator.label"
            :value="operator.value"
          />
        </el-select>

        <el-select
          v-if="child.field === 'fileType' && isMultiValue(child)"
          v-model="child.value"
          multiple
          collapse-tags
          collapse-tags-tooltip
          size="small"
          class="value-select value-select-multiple"
          placeholder="选择类型"
          aria-label="文件类型值"
        >
          <el-option v-for="type in FILE_TYPE_OPTIONS" :key="type.value" :label="type.label" :value="type.value" />
        </el-select>
        <el-select
          v-else-if="child.field === 'fileType'"
          v-model="child.value"
          size="small"
          class="value-select"
          placeholder="选择类型"
          aria-label="文件类型值"
        >
          <el-option v-for="type in FILE_TYPE_OPTIONS" :key="type.value" :label="type.label" :value="type.value" />
        </el-select>
        <template v-else-if="isRangeField(child)">
          <el-input-number
            v-if="child.operator !== 'between'"
            v-model="child.value"
            :min="0"
            :precision="0"
            controls-position="right"
            size="small"
            class="value-number"
            placeholder="字节"
            aria-label="文件大小"
          />
          <div v-else class="range-values">
            <el-input-number
              v-model="child.value[0]"
              :min="0"
              :precision="0"
              controls-position="right"
              size="small"
              class="value-number"
              placeholder="最小字节"
              aria-label="最小文件大小"
            />
            <span>至</span>
            <el-input-number
              v-model="child.value[1]"
              :min="0"
              :precision="0"
              controls-position="right"
              size="small"
              class="value-number"
              placeholder="最大字节"
              aria-label="最大文件大小"
            />
          </div>
        </template>
        <template v-else-if="child.field === 'createTime'">
          <el-date-picker
            v-if="child.operator !== 'between'"
            v-model="child.value"
            type="datetime"
            value-format="YYYY-MM-DD HH:mm:ss"
            size="small"
            class="value-date"
            placeholder="选择时间"
            aria-label="创建时间"
          />
          <div v-else class="range-values date-range-values">
            <el-date-picker
              v-model="child.value[0]"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              size="small"
              class="value-date"
              placeholder="开始时间"
              aria-label="开始时间"
            />
            <span>至</span>
            <el-date-picker
              v-model="child.value[1]"
              type="datetime"
              value-format="YYYY-MM-DD HH:mm:ss"
              size="small"
              class="value-date"
              placeholder="结束时间"
              aria-label="结束时间"
            />
          </div>
        </template>
        <el-input
          v-else
          v-model="child.value"
          size="small"
          class="value-input"
          :placeholder="textPlaceholder(child)"
          :aria-label="`${fieldLabel(child.field)}值`"
          clearable
        />

        <el-button
          text
          type="danger"
          size="small"
          :icon="Delete"
          class="remove-condition"
          aria-label="删除条件"
          @click="removeChild(index)"
        />
      </div>

      <div v-if="index < group.children.length - 1" class="group-connector">
        {{ group.logic === 'AND' ? '并且' : '或者' }}
      </div>
    </div>

    <div class="group-actions">
      <el-button text type="primary" size="small" :icon="Plus" @click="addCondition">添加条件</el-button>
      <el-button
        text
        size="small"
        :icon="FolderAdd"
        :disabled="depth >= MAX_NESTED_DEPTH"
        @click="addGroup"
      >
        添加分组
      </el-button>
    </div>
  </section>
</template>

<script setup>
import { Delete, FolderAdd, Plus } from '@element-plus/icons-vue'

defineOptions({ name: 'SearchExpressionBuilder' })

const props = defineProps({
  group: { type: Object, required: true },
  depth: { type: Number, default: 0 },
})

defineEmits(['remove'])

const MAX_NESTED_DEPTH = 3

const FIELD_OPTIONS = [
  { value: 'fileName', label: '文件名' },
  { value: 'fileType', label: '文件类型' },
  { value: 'fileSize', label: '文件大小（字节）' },
  { value: 'createTime', label: '创建时间' },
  { value: 'filePath', label: '文件路径' },
  { value: 'originText', label: '文件内容' },
]

const FILE_TYPE_OPTIONS = [
  { value: 'IMAGE', label: '图片' },
  { value: 'VIDEO', label: '视频' },
  { value: 'DOCUMENT', label: '文档' },
  { value: 'OTHER', label: '其他' },
]

const OPERATOR_OPTIONS = {
  fileName: [
    { value: 'contains', label: '包含' },
    { value: 'not_contains', label: '不包含' },
    { value: 'equals', label: '等于' },
    { value: 'not_equals', label: '不等于' },
    { value: 'starts_with', label: '以此开头' },
    { value: 'ends_with', label: '以此结尾' },
  ],
  fileType: [
    { value: 'equals', label: '等于' },
    { value: 'not_equals', label: '不等于' },
    { value: 'in', label: '属于任一' },
    { value: 'not_in', label: '不属于任一' },
  ],
  fileSize: [
    { value: 'gt', label: '大于' },
    { value: 'gte', label: '大于等于' },
    { value: 'lt', label: '小于' },
    { value: 'lte', label: '小于等于' },
    { value: 'between', label: '介于' },
  ],
  createTime: [
    { value: 'after', label: '晚于或等于' },
    { value: 'before', label: '早于' },
    { value: 'between', label: '介于' },
  ],
  filePath: [
    { value: 'contains', label: '包含' },
    { value: 'not_contains', label: '不包含' },
  ],
  originText: [
    { value: 'contains', label: '包含' },
    { value: 'not_contains', label: '不包含' },
  ],
}

let idSeed = 0

const createId = () => `expression-${Date.now()}-${++idSeed}`

const createCondition = (field = 'fileName') => ({
  type: 'condition',
  id: createId(),
  field,
  operator: OPERATOR_OPTIONS[field][0].value,
  value: defaultValue(field, OPERATOR_OPTIONS[field][0].value),
})

const createGroup = () => ({
  type: 'group',
  id: createId(),
  logic: 'AND',
  children: [createCondition()],
})

const defaultValue = (field, operator) => {
  if (field === 'fileType' && ['in', 'not_in'].includes(operator)) return []
  if (field === 'fileSize' && operator === 'between') return [null, null]
  if (field === 'createTime' && operator === 'between') return ['', '']
  return field === 'fileType' ? 'DOCUMENT' : ''
}

const operatorsFor = (condition) => OPERATOR_OPTIONS[condition.field] || OPERATOR_OPTIONS.fileName
const fieldLabel = (field) => FIELD_OPTIONS.find((item) => item.value === field)?.label || field
const isMultiValue = (condition) => ['in', 'not_in'].includes(condition.operator)
const isRangeField = (condition) => condition.field === 'fileSize'
const textPlaceholder = (condition) => {
  if (condition.field === 'filePath') return '输入路径片段'
  if (condition.field === 'originText') return '输入内容片段'
  return '输入文件名'
}

const resetCondition = (condition) => {
  condition.operator = operatorsFor(condition)[0].value
  resetConditionValue(condition)
}

const resetConditionValue = (condition) => {
  condition.value = defaultValue(condition.field, condition.operator)
}

const removeChild = (index) => {
  props.group.children.splice(index, 1)
}

const addCondition = () => {
  props.group.children.push(createCondition())
}

const addGroup = () => {
  if (props.depth >= MAX_NESTED_DEPTH) return
  props.group.children.push(createGroup())
}
</script>

<style scoped>
.expression-group {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.expression-group.nested {
  padding: 11px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 11px;
  background: var(--el-color-primary-light-9);
}
.group-header,
.group-title,
.group-actions,
.condition-row,
.range-values {
  display: flex;
  align-items: center;
}
.group-header {
  justify-content: space-between;
  gap: 8px;
}
.group-title {
  min-width: 0;
  gap: 7px;
}
.group-label {
  flex: 0 0 auto;
  color: var(--ap-text-sub);
  font-size: 12px;
}
.logic-select {
  width: 208px;
}
.group-empty {
  padding: 10px;
  border: 1px dashed var(--ap-border-color);
  border-radius: 9px;
  color: var(--ap-text-sub);
  font-size: 12px;
  text-align: center;
}
.expression-child {
  position: relative;
}
.condition-row {
  gap: 7px;
  min-width: 0;
}
.field-select { width: 128px; flex: 0 0 128px; }
.operator-select { width: 128px; flex: 0 0 128px; }
.value-select { width: 128px; flex: 1 1 128px; min-width: 100px; }
.value-select-multiple { min-width: 160px; }
.value-input { flex: 1 1 160px; min-width: 120px; }
.value-number { width: 150px; flex: 1 1 150px; min-width: 112px; }
.value-date { width: 180px; flex: 1 1 180px; min-width: 150px; }
.range-values { flex: 1 1 auto; gap: 6px; min-width: 0; }
.range-values > span { flex: 0 0 auto; color: var(--ap-text-sub); font-size: 12px; }
.date-range-values .value-date { min-width: 135px; }
.remove-condition { flex: 0 0 32px; width: 32px; padding: 0; }
.group-connector {
  width: max-content;
  margin: 5px 0 5px 14px;
  padding: 2px 9px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 9px;
  background: var(--ap-bg-card);
  color: var(--el-color-primary-dark-2);
  font-size: 11px;
}
.group-actions {
  gap: 4px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .expression-group.nested { padding: 9px; }
  .condition-row { align-items: stretch; flex-wrap: wrap; gap: 6px; }
  .field-select,
  .operator-select,
  .value-select,
  .value-select-multiple,
  .value-input,
  .value-number,
  .value-date { width: auto; min-width: 0; flex: 1 1 calc(50% - 6px); }
  .value-input,
  .value-select-multiple,
  .range-values { flex-basis: calc(100% - 38px); }
  .remove-condition { align-self: center; }
  .range-values { flex-wrap: wrap; }
  .range-values .value-number,
  .range-values .value-date { flex: 1 1 130px; }
  .date-range-values { flex-basis: 100%; }
  .date-range-values .value-date { flex-basis: 100%; }
  .logic-select { width: 100%; }
}
</style>
