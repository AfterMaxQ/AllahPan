<template>
  <el-dialog
    v-model="visible"
    title="新建文件夹"
    width="420px"
    @opened="focusInput"
    destroy-on-close
  >
    <el-form :model="form" :rules="rules" ref="formRef" label-width="0" @submit.prevent>
      <el-form-item prop="folderName">
        <el-input
          ref="inputRef"
          v-model="form.folderName"
          placeholder="请输入文件夹名称"
          maxlength="100"
          @keyup.enter="handleSubmit"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { createFolder } from '@/api/file'
import { useFileStore } from '@/stores/file'

const visible = ref(false)
const submitting = ref(false)
const inputRef = ref(null)
const formRef = ref(null)
const fileStore = useFileStore()

const form = reactive({ folderName: '' })
const rules = {
  folderName: [{ required: true, message: '请填写文件夹名称', trigger: 'blur' }],
}

const open = () => {
  form.folderName = ''
  visible.value = true
}

const focusInput = () => {
  inputRef.value?.focus()
}

defineExpose({ open })
const emit = defineEmits(['created'])

const handleSubmit = () => {
  formRef.value?.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      await createFolder(form.folderName, fileStore.currentFolderId)
      ElMessage.success('文件夹创建成功')
      visible.value = false
      emit('created')
    } catch (e) {
      // 错误由拦截器统一处理
    } finally {
      submitting.value = false
    }
  })
}
</script>
