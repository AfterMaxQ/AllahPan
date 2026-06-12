# AllahPan API 文档

## 服务信息

| 服务 | 端口 | 说明 |
|------|------|------|
| 主应用 (allahpan-core) | **:8088** | 认证、用户、文件、收藏、搜索代理 |
| 搜索服务 (allahpan-search) | **:8081** | Elasticsearch 索引与全文搜索 |

## 认证

除登录/发送验证码外，所有 API 需要 JWT 认证：

```
Authorization: Bearer <token>
```

Token 通过登录接口获取，HS512 签名，有效期 **7 天**。

## 通用响应格式

所有 core 接口返回 `CommonResult<T>`：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `long` | 业务状态码 |
| `message` | `string` | 提示信息 |
| `data` | `T` (泛型) | 响应数据，可能为 `null` |

> **例外**: 搜索服务 (`:8081`) 的 5 个端点返回原始 `Map<String, Object>`，不使用 `CommonResult` 包装。详见 [06-search-service.md](06-search-service.md)。

## 错误码

| code | 常量 | 说明 |
|------|------|------|
| 200 | `SUCCESS` | 操作成功 |
| 400 | `CODE_ERROR` | 验证码错误 |
| 400 | `CODE_EXPIRED` | 验证码过期 |
| 401 | `UNAUTHORIZED` | 未登录或 token 过期 |
| 403 | `FORBIDDEN` | 无权限访问 |
| 404 | `VALIDATE_FAILED` | 参数校验失败 |
| 429 | `TOO_MANY_REQUESTS` | 请求频率过快 |
| 429 | `CODE_SEND_LIMIT` | 验证码发送间隔不足 30s |
| 500 | `FAILED` | 操作失败 |

## 分页

支持分页的接口使用 `pageNum`（从 1 开始）和 `pageSize` 参数：

```
GET /api/file/list?parentId=0
GET /api/file/trash?pageNum=1&pageSize=20
GET /api/favorite/list?pageNum=1&pageSize=20
GET /api/search?keyword=xxx&pageNum=1&pageSize=20
```

后端通过 PageHelper 自动分页。响应中 `data` 为分页结果数组，不含 `total`/`pageNum` 等分页元信息（除搜索接口外）。

## 端点索引

| 分类 | 文档 | 端点数 |
|------|------|--------|
| 认证 | [01-auth.md](01-auth.md) | 3 |
| 用户 | [02-user.md](02-user.md) | 2 |
| 文件 | [03-file.md](03-file.md) | 16 |
| 收藏 | [04-favorite.md](04-favorite.md) | 4 |
| 搜索（代理） | [05-search-core.md](05-search-core.md) | 2 |
| 搜索服务 | [06-search-service.md](06-search-service.md) | 5 |
| 分享 | [07-share.md](07-share.md) | 3 |
| **合计** | | **35** (30 core + 5 search) |

## 快速导航

### 前端开发常用

| 场景 | 端点 | 文档 |
|------|------|------|
| 登录 | `POST /api/auth/login-by-code` | [01-auth.md](01-auth.md) |
| 获取当前用户 | `GET /api/user/me` | [02-user.md](02-user.md) |
| 文件列表 | `GET /api/file/list?parentId=0` | [03-file.md](03-file.md) |
| 上传文件 | `POST /api/file/upload` (multipart) | [03-file.md](03-file.md) |
| 创建文件夹 | `POST /api/file/create-folder` | [03-file.md](03-file.md) |
| 收藏/取消收藏 | `POST/DELETE /api/favorite/{fileId}` | [04-favorite.md](04-favorite.md) |
| 全文搜索 | `GET /api/search?keyword=xxx` | [05-search-core.md](05-search-core.md) |
| 重建搜索索引 | `POST /api/search/rebuild-index` | [05-search-core.md](05-search-core.md) |
| 下载文件 | `GET /api/file/{fileId}/download` | [03-file.md](03-file.md) |
| 内联预览 | `GET /api/file/{fileId}/stream` | [03-file.md](03-file.md) |
| 缩略图 | `GET /api/file/{fileId}/thumbnail` | [03-file.md](03-file.md) |
| 实时推送 | `GET /api/file/watch?token=...` (SSE) | [03-file.md](03-file.md) |
| 重命名 | `PUT /api/file/{fileId}/rename` | [03-file.md](03-file.md) |
| 移动 | `PUT /api/file/{fileId}/move` | [03-file.md](03-file.md) |
| 批量删除 | `DELETE /api/file/batch` | [03-file.md](03-file.md) |
| 垃圾站 | `GET /api/file/trash` → 恢复/永久删除 | [03-file.md](03-file.md) |
| 分享文件 | `POST /api/share/{fileId}` | [07-share.md](07-share.md) |

### 服务间对接

| 场景 | 端点 | 文档 |
|------|------|------|
| 索引文件（处理流水线） | `POST /es-admin/files/index` | [06-search-service.md](06-search-service.md) |
| 删除索引 | `DELETE /es-admin/files/{fileId}` | [06-search-service.md](06-search-service.md) |
| 清空所有索引 | `DELETE /es-admin/files/_all` | [06-search-service.md](06-search-service.md) |
| 全文搜索 | `GET /es-admin/files/search` | [06-search-service.md](06-search-service.md) |
| 全量重建索引 | `POST /es-admin/rebuild` | [06-search-service.md](06-search-service.md) |
