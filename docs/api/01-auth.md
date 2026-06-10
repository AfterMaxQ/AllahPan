# 01 — 认证 API

**Base URL:** `http://localhost:8088/api/auth`

所有认证接口**不需要** Authorization header（已在 SecurityConfig 白名单中）。

---

## 1. 发送验证码

```
POST /api/auth/send-code
```

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `email` | `string` | ✅ | 邮箱 (`@NotBlank`) |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com"}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": null
}
```

### 限流规则

| 规则 | 限制 | 错误返回 |
|------|------|----------|
| 发送间隔 | 30 秒内不可重复发送 | `{code: 429, message: "验证码发送次数超过限制,请30s后重试"}` |
| 小时上限 | 每小时最多 50 次 | `{code: 429, message: "请求频率过快，请稍后重试"}` |

### 备注

- 验证码为 **6 位随机数字**
- 有效期 **5 分钟**（Redis TTL）
- 验证码通过 QQ 邮箱 SMTP 发送（`MailService`），日志可查看发送状态

---

## 2. 验证码登录

```
POST /api/auth/login-by-code
```

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `email` | `string` | ✅ | 邮箱 |
| `code` | `string` | ✅ | 6 位验证码 |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/auth/login-by-code \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","code":"975081"}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...",
    "tokenHead": "Bearer ",
    "userId": 1,
    "email": "user@example.com",
    "hasPassword": false,
    "firstLogin": true
  }
}
```

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `token` | `string` | JWT token (HS512, 7天有效) |
| `tokenHead` | `string` | 固定为 `"Bearer "` |
| `userId` | `long` | 用户 ID |
| `email` | `string` | 邮箱 |
| `hasPassword` | `boolean` | 是否已设置密码 |
| `firstLogin` | `boolean` | 是否首次登录（= `!hasPassword`） |

### 行为

- **新用户**: 邮箱未注册时自动注册，`hasPassword = false`，`firstLogin = true`
- **老用户**: 直接登录，更新 `lastLoginTime`

### 错误码

| code | 说明 |
|------|------|
| 400 | 验证码错误 (`CODE_ERROR`) |
| 400 | 验证码过期 (`CODE_EXPIRED`) |

---

## 3. 密码登录

```
POST /api/auth/login-by-password
```

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `email` | `string` | ✅ | 邮箱 |
| `password` | `string` | ✅ | BCrypt 密码 |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/auth/login-by-password \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"mypassword"}'
```

### 响应示例

响应格式与验证码登录相同。

### 错误

- 用户不存在 → `{code: 500, message: "邮箱未注册"}`
- 密码错误 → `{code: 500, message: "密码错误"}`
- 未设置密码（`firstLogin=1`）→ 需先用验证码登录后调用 `/api/user/set-password`
