import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useUserStore } from '@/stores/user'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截：携带 JWT
request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

// 响应拦截：解包 CommonResult + 处理 401
request.interceptors.response.use(
  (response) => {
    const res = response.data
    // 非标准 CommonResult 响应（如 search-service 独立返回），直接放行
    if (res.code === undefined) return res

    if (res.code === 200) {
      return res.data
    }

    // 业务码 401：未登录或 token 过期 → 登出并跳转登录页
    // 后端 RestAuthenticationEntryPoint 返回 HTTP 200 + code=401，不走 HTTP 401 分支
    if (res.code === 401) {
      const userStore = useUserStore()
      userStore.logout()
      router.push('/login')
      ElMessage.warning(res.message || '登录已过期，请重新登录')
      return Promise.reject(new Error(res.message || '未授权'))
    }

    if (!response.config.suppressErrorMessage) {
      ElMessage.error(res.message || '系统错误')
    }
    const error = new Error(res.message || 'Error')
    error.businessCode = res.code
    error.data = res
    return Promise.reject(error)
  },
  (error) => {
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      router.push('/login')
      ElMessage.warning('登录已过期，请重新登录')
    } else if (!error.config?.suppressErrorMessage) {
      ElMessage.error(error.message || '网络请求失败')
    }
    return Promise.reject(error)
  }
)

export default request
