import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('allahpan_token') || '')
  const userInfo = ref(null)
  const isFirstLogin = ref(localStorage.getItem('allahpan_first') === 'true')

  const setAuth = (data) => {
    token.value = data.token
    isFirstLogin.value = data.firstLogin || false
    localStorage.setItem('allahpan_token', data.token)
    localStorage.setItem('allahpan_first', String(data.firstLogin || false))
  }

  const updateTokenAfterSetPassword = (newToken) => {
    token.value = newToken
    isFirstLogin.value = false
    localStorage.setItem('allahpan_token', newToken)
    localStorage.setItem('allahpan_first', 'false')
  }

  const setUserInfo = (info) => {
    userInfo.value = info
  }

  const logout = () => {
    token.value = ''
    userInfo.value = null
    isFirstLogin.value = false
    localStorage.clear()
  }

  return { token, userInfo, isFirstLogin, setAuth, updateTokenAfterSetPassword, setUserInfo, logout }
})
