<template>
  <div class="setpwd-container">
    <div class="setpwd-card">
      <div class="brand">
        <el-icon size="40" color="var(--el-color-primary)"><Lock /></el-icon>
        <h2>设置登录密码</h2>
        <p>欢迎加入 AllahPan，请为您的账号设置一个安全密码</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入新密码"
            size="large"
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>
        <el-form-item prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="请再次确认密码"
            size="large"
            show-password
            :prefix-icon="CircleCheck"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :loading="submitting"
          @click="handleSubmit"
        >
          开启云盘之旅
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { setPassword } from '@/api/user'
import { Lock, CircleCheck } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref(null)
const submitting = ref(false)

const form = reactive({ password: '', confirm: '' })
const rules = {
  password: [
    { required: true, message: '请填写新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const handleSubmit = () => {
  formRef.value?.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const res = await setPassword(form.password)
      userStore.updateTokenAfterSetPassword(res.token)
      ElMessage.success('密码设置成功')
      router.replace('/')
    } catch (e) { /* 拦截器统一处理 */ }
    finally { submitting.value = false }
  })
}
</script>

<style scoped>
.setpwd-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% -20%, var(--el-color-primary-light-7), var(--ap-bg-page) 60%);
}
.setpwd-card {
  width: calc(100% - 48px);
  max-width: 400px;
  padding: 32px 24px;
  background: var(--ap-bg-card);
  border-radius: 20px;
  border: 1px solid var(--ap-border-color);
  box-shadow: 0 12px 40px rgba(61, 50, 38, 0.06);
}
.brand {
  text-align: center;
  margin-bottom: 28px;
}
.brand h2 {
  margin: 8px 0 4px;
  color: var(--ap-text-main);
  font-size: 20px;
}
.brand p {
  font-size: 13px;
  color: var(--ap-text-sub);
  margin: 0;
  line-height: 1.6;
}
.submit-btn {
  width: 100%;
  margin-top: 8px;
}

@media (max-width: 768px) {
  .setpwd-container {
    background: radial-gradient(circle at 50% 0%, var(--el-color-primary-light-7), var(--ap-bg-page) 50%);
  }
  .setpwd-card {
    padding: 28px 20px;
  }
  .brand h2 {
    font-size: 18px;
  }
  .setpwd-card :deep(.el-input__inner) {
    font-size: 16px;
  }
}
</style>
