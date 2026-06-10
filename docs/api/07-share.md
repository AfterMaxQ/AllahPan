# 07 — 分享 API

**Base URL:** `http://localhost:8088/api/share`

文件分享链接，基于 Redis 存储分享码，支持 TTL 过期。

**公开端点**: `GET /api/share/{code}` — SecurityConfig 中将 `/api/share/**` 加入白名单 (`permitAll()`)，无需 JWT 即可访问。

**需认证端点**: `POST /api/share/{fileId}` 和 `DELETE /api/share/{code}` — 虽然路径也被 `/api/share/**` 白名单覆盖（避免 Spring Security 层面返回 401），但服务层通过 `SecurityContextHolder.getContext().getAuthentication()` 强制校验 JWT 身份，未认证的调用会收到业务层错误。**仅创建者可删除自己的分享。**

---

## 1. 创建分享链接

```
POST /api/share/{fileId}
```

需要认证：`Authorization: Bearer <token>`

### 请求

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| `fileId` | path | `number` | ✅ | — | 文件 ID |
| `expireHours` | query | `number` | ❌ | `24` | 有效期（小时），范围 1~168 |

### 请求示例

```bash
curl -X POST "http://localhost:8088/api/share/43?expireHours=48" \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "shareCode": "a1b2c3d4",
    "shareUrl": "/api/share/a1b2c3d4",
    "expireTime": "2026-06-10T12:00:00.000+00:00"
  }
}
```

### 备注

- 文件夹不支持分享
- 已删除文件不支持分享
- 分享码为 8 位随机字符，容错重试 3 次防止碰撞
- Redis 存储，TTL = `expireHours * 3600 + 3600`（1 小时缓冲）
- 服务层通过 `getCurrentUserId()` 从 SecurityContext 获取当前用户，未认证抛出 `UNAUTHORIZED`

---

## 2. 获取分享内容（公开）

```
GET /api/share/{code}
```

**无需认证。** 任何人拿到分享码均可访问。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `code` | path | `string` | 分享码 |

### 请求示例

```bash
curl "http://localhost:8088/api/share/a1b2c3d4"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "fileId": 43,
    "fileName": "photo.png",
    "fileSize": 204800,
    "fileType": "IMAGE",
    "downloadUrl": "http://localhost:9000/allahpan-files/1/2026/06/a1b2c3d4.png?X-Amz-...",
    "createTime": "2026-06-08T12:00:00.000+00:00"
  }
}
```

### 错误

| 情况 | 错误信息 |
|------|----------|
| 分享码不存在或 Redis 已过期 | 分享链接不存在或已过期 |
| 超过有效期 | 分享链接已过期（同时自动清理 Redis key） |
| 文件已被删除 | 文件不存在或已删除 |

---

## 3. 删除分享链接

```
DELETE /api/share/{code}
```

需要认证：`Authorization: Bearer <token>`
**仅创建者可删除。**（服务层通过 SecurityContext 校验 JWT，非创建者返回 "无权删除他人的分享"）

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `code` | path | `string` | 分享码 |

### 请求示例

```bash
curl -X DELETE http://localhost:8088/api/share/a1b2c3d4 \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": null
}
```

### 备注

- 校验 `creatorId`，非创建者返回 "无权删除他人的分享"
- 已过期的分享 key 可能已自动清理，删除会报 "分享链接不存在"

---

## Redis 存储结构

```
Key:   allahpan:share:{code}
Value: {"fileId":43, "creatorId":1, "expireTime":1749999999999}
TTL:   expireHours * 3600 + 3600
```
