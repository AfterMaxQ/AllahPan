# 04 — 收藏 API

**Base URL:** `http://localhost:8088/api/favorite`

所有接口需要认证：`Authorization: Bearer <token>`

---

## 1. 收藏文件

```
POST /api/favorite/{fileId}
```

**幂等**：已收藏的文件再次调用不报错。

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `fileId` | path | `number` | 文件 ID |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/favorite/43 \
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

- 入库前检查 userId+fileId 是否已存在，防止重复收藏
- 重复收藏不报错，直接返回成功

---

## 2. 取消收藏

```
DELETE /api/favorite/{fileId}
```

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `fileId` | path | `number` | 文件 ID |

### 请求示例

```bash
curl -X DELETE http://localhost:8088/api/favorite/43 \
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

---

## 3. 检查是否已收藏

```
GET /api/favorite/check/{fileId}
```

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `fileId` | path | `number` | 文件 ID |

### 请求示例

```bash
curl http://localhost:8088/api/favorite/check/43 \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": true
}
```

---

## 4. 收藏列表

```
GET /api/favorite/list
```

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pageNum` | `number` | ❌ | `1` | 页码 |
| `pageSize` | `number` | ❌ | `20` | 每页条数 |

### 请求示例

```bash
curl "http://localhost:8088/api/favorite/list?pageNum=1&pageSize=20" \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "id": 43,
      "fileName": "photo.png",
      "fileType": "IMAGE",
      "fileSize": 204800,
      "filePath": "/我的图片/photo.png",
      "isFolder": 0,
      "createTime": "2026-06-08T12:00:00.000+00:00"
    },
    {
      "id": 45,
      "fileName": "文档合集",
      "fileType": "FOLDER",
      "fileSize": 0,
      "isFolder": 1,
      "createTime": "2026-06-08T11:00:00.000+00:00"
    }
  ]
}
```

### 备注

- 返回的是 `File` 对象列表（非 `FileFavorite`）
- 先查 `file_favorites` 表获取 fileId 列表（按 `create_time DESC` 排序），再逐个查 `files` 表
- PageHelper 分页作用于 `file_favorites` 查询，文件详情为逐一查询（N+1）
