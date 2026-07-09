<template>
  <div class="login-container">
    <div class="login-card">
      <div class="brand">
        <el-icon size="44" color="var(--el-color-primary)"><HomeFilled /></el-icon>
        <h2>AllahPan</h2>
        <p>家庭共享云盘，安全存留每一份记忆</p>
      </div>

      <el-tabs v-model="loginMode" class="login-tabs">
        <!-- 验证码登录 -->
        <el-tab-pane label="验证码登录" name="code">
          <el-form :model="codeForm" ref="codeFormRef" @submit.prevent>
            <el-form-item>
              <el-input
                v-model="codeForm.email"
                placeholder="请输入邮箱地址"
                size="large"
                :prefix-icon="Message"
              />
            </el-form-item>
            <el-form-item>
              <div class="code-row">
                <el-input
                  v-model="codeForm.code"
                  placeholder="6位验证码"
                  size="large"
                  class="code-input"
                />
                <el-button
                  :disabled="countdown > 0"
                  size="large"
                  class="code-btn"
                  @click="sendCode"
                >
                  {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
                </el-button>
              </div>
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              class="submit-btn"
              :loading="loading"
              @click="handleCodeLogin"
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <!-- 密码登录 -->
        <el-tab-pane label="密码登录" name="password">
          <el-form :model="pwdForm" ref="pwdFormRef" @submit.prevent>
            <el-form-item>
              <el-input
                v-model="pwdForm.email"
                placeholder="请输入邮箱地址"
                size="large"
                :prefix-icon="User"
              />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="pwdForm.password"
                type="password"
                placeholder="请输入密码"
                size="large"
                show-password
                :prefix-icon="Lock"
              />
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              class="submit-btn"
              :loading="loading"
              @click="handlePwdLogin"
            >
              登录
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { sendCode as sendCodeApi, loginByCode, loginByPassword } from '@/api/auth'
import { HomeFilled, Message, User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()
const loginMode = ref('code')
const loading = ref(false)

const codeForm = ref({ email: '', code: '' })
const pwdForm = ref({ email: '', password: '' })
const countdown = ref(0)

const sendCode = async () => {
  if (!codeForm.value.email) return ElMessage.warning('请输入邮箱地址')
  try {
    await sendCodeApi(codeForm.value.email)
    ElMessage.success('验证码已发送')
    countdown.value = 60
    const timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) { /* 拦截器统一处理 */ }
}

const processLoginRes = (res) => {
  userStore.setAuth(res)
  if (res.firstLogin) {
    router.push('/set-password')
  } else {
    router.push('/')
  }
}

const handleCodeLogin = async () => {
  if (!codeForm.value.email || !codeForm.value.code) {
    return ElMessage.warning('请填写邮箱和验证码')
  }
  loading.value = true
  try {
    const res = await loginByCode(codeForm.value.email, codeForm.value.code)
    processLoginRes(res)
  } catch (e) { /* 拦截器统一处理 */ }
  finally { loading.value = false }
}

const handlePwdLogin = async () => {
  if (!pwdForm.value.email || !pwdForm.value.password) {
    return ElMessage.warning('请填写邮箱和密码')
  }
  loading.value = true
  try {
    const res = await loginByPassword(pwdForm.value.email, pwdForm.value.password)
    processLoginRes(res)
  } catch (e) { /* 拦截器统一处理 */ }
  finally { loading.value = false }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 50% -20%, var(--el-color-primary-light-7), var(--ap-bg-page) 60%);
}
.login-card {
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
  font-size: 22px;
}
.brand p {
  font-size: 13px;
  color: var(--ap-text-sub);
  margin: 0;
}
.login-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  color: var(--ap-text-sub);
}
.login-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 600;
}
.code-row {
  display: flex;
  gap: 10px;
  width: 100%;
}
.code-input {
  flex: 1;
}
.code-btn {
  flex-shrink: 0;
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5);
}
.submit-btn {
  width: 100%;
  margin-top: 8px;
}

@media (max-width: 768px) {
  .login-container {
    background: radial-gradient(circle at 50% 0%, var(--el-color-primary-light-7), var(--ap-bg-page) 50%);
  }
  .login-card {
    padding: 28px 20px;
  }
  .brand h2 {
    font-size: 20px;
  }
  .login-card :deep(.el-input__inner) {
    font-size: 16px;
  }
}
</style>
