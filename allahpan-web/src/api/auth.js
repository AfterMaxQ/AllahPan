import request from './index'

export function sendCode(email) {
  return request.post('/auth/send-code', { email })
}

export function loginByCode(email, code) {
  return request.post('/auth/login-by-code', { email, code })
}

export function loginByPassword(email, password) {
  return request.post('/auth/login-by-password', { email, password })
}
