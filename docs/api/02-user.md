# 02 — 用户 API

**Base URL:** `http://localhost:8088/api/user`

所有接口需要认证：`Authorization: Bearer <token>`

---

## 1. 首次设置密码

```
POST /api/user/set-password
```

用于验证码登录后的新用户设置密码。

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `newPassword` | `string` | ✅ | 新密码 (`@NotBlank`) |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/user/set-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"newPassword":"my_secure_password"}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...",
    "hasPassword": true
  }
}
```

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `token` | `string` | **新 JWT token**（`hasPassword` 已变为 `true`，旧 token 仍有效但不含此声明） |
| `hasPassword` | `boolean` | 固定为 `true` |

### 备注

- 密码通过 `BCryptPasswordEncoder` 哈希后存入 `users.password`
- 设置后 `users.first_login` 从 1 变为 0
- 已设置过密码的用户再次调用会覆盖旧密码

---

## 2. 获取当前用户信息

```
GET /api/user/me
```

### 请求

无需参数，从 JWT token 解析当前用户。

### 请求示例

```bash
curl http://localhost:8088/api/user/me \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "email": "user@example.com",
    "nickname": "user",
    "avatarUrl": null,
    "status": 1,
    "firstLogin": 0,
    "lastLoginTime": "2026-06-08T12:00:00.000+00:00",
    "createTime": "2026-06-08T10:00:00.000+00:00",
    "updateTime": "2026-06-08T12:00:00.000+00:00"
  }
}
```

### 备注

- `password` 字段已被置 `null`，不会返回

---

## User 实体参考

| 字段 | Java 类型 | JSON 类型 | 说明 |
|------|-----------|-----------|------|
| `id` | `Long` | `number` | 主键 |
| `email` | `String` | `string` | 邮箱（唯一，登录凭证） |
| `password` | `String` | `string` | BCrypt 哈希（接口中通常为 null） |
| `nickname` | `String` | `string` | 昵称 |
| `avatarUrl` | `String` | `string` | 头像 key（可空） |
| `status` | `Byte` | `number` | 0=禁用, 1=正常 |
| `firstLogin` | `Byte` | `number` | 0=已设密码, 1=首次登录 |
| `lastLoginTime` | `Date` | `string(ISO)` | 最后登录时间 |
| `createTime` | `Date` | `string(ISO)` | 注册时间 |
| `updateTime` | `Date` | `string(ISO)` | 更新时间 |
