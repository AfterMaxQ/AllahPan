import request from './index'

export function setPassword(newPassword) {
  return request.post('/user/set-password', { newPassword })
}

export function getMyInfo() {
  return request.get('/user/me')
}
