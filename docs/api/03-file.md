# 03 — 文件 API

**Base URL:** `http://localhost:8088/api/file`

所有接口需要认证：`Authorization: Bearer <token>`

---

## File 实体参考

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `number` | 文件 ID |
| `uploaderId` | `number` | 上传者用户 ID |
| `parentId` | `number` | 父目录 ID，0 = 根目录 |
| `fileName` | `string` | 文件名 |
| `filePath` | `string` | 虚拟路径，如 `/我的图片/screenshot.png` |
| `storageKey` | `string` | 本地存储路径 key |
| `fileType` | `string` | `FOLDER` / `IMAGE` / `VIDEO` / `DOCUMENT` / `OTHER` |
| `fileSize` | `number` | 文件大小（字节） |
| `contentType` | `string` | MIME 类型 |
| `thumbnailKey` | `string` | 缩略图本地路径 key（可空） |
| `isFolder` | `number` | 0=文件, 1=文件夹 |
| `processStatus` | `number` | 0=待处理, 1=缩略图完成, 2=文字提取完成, 3=全部完成, -1=失败 |
| `md5` | `string` | MD5 哈希（秒传用） |
| `createTime` | `string(ISO)` | 创建时间 |
| `updateTime` | `string(ISO)` | 更新时间 |
| `deleteTime` | `string(ISO)` | 软删除时间，null=正常 |

---

## 1. 上传文件

```
POST /api/file/upload
```

Multipart 表单上传，服务端直接接收文件并写入本地磁盘。含 MD5 秒传检测。

### 请求

Content-Type: `multipart/form-data`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file` | `file` | ✅ | — | 上传的文件 |
| `parentId` | `number` | ❌ | `0` | 父目录 ID |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/file/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@photo.png" \
  -F "parentId=0"
```

### 响应 — 新文件

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 43,
    "uploaderId": 1,
    "parentId": 0,
    "fileName": "photo.png",
    "filePath": "/photo.png",
    "storageKey": "1/2026/06/a1b2c3d4.png",
    "fileType": "IMAGE",
    "fileSize": 204800,
    "contentType": "image/png",
    "thumbnailKey": null,
    "isFolder": 0,
    "processStatus": 0,
    "originText": "",
    "md5": "d41d8cd98f00b204e9800998ecf8427e",
    "createTime": "2026-06-08T12:00:00.000+00:00"
  }
}
```

### 响应 — 秒传（MD5 已存在）

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 44,
    "processStatus": 3,
    "md5": "d41d8cd98f00b204e9800998ecf8427e"
  }
}
```

### 备注

- `fileType` 根据 `contentType` 自动判定（IMAGE/VIDEO/DOCUMENT/OTHER）
- `filePath` 从父目录链拼接（如 `/我的图片/photo.png`）
- 文件写入本地磁盘后触发 RabbitMQ 流水线，串行三个阶段：

| 阶段 | processStatus | 组件 | 说明 |
|------|:---:|---|---|
| 缩略图 | `0→1` | `ThumbnailGenerator` | IMAGE 缩放 300px→JPEG；PDF via PDFBox 渲染首帧 (可配置 DPI, 默认150)；其他类型跳过 |
| 文字提取 | `1→2` | `TextExtractor` → `OllamaService` | IMAGE 调用 qwen3.5:2b（think=false, num_predict=4096, ~3.1s）；PDF via PDFBox；DOCX/DOC/XLSX/XLS/PPTX/PPT via Apache POI；纯文本 UTF-8 读取；文字自动截断至 10000 字符 |
| ES 索引 | `2→3` | `EsIndexService` | HTTP POST → search 应用 :8081 写入 Elasticsearch；**索引失败不标记 processStatus=-1（降级，文件仍可用）** |

- **重试机制**：任一阶段失败自动重试 3 次（延迟 30s/60s/120s）。基础设施错误（Ollama/ES 不可达、超时）耗尽后降级（不标记 -1）；致命 DB 错误才标记 `processStatus=-1`
- **文件夹/秒传**：`processStatus` 直接设为 3，跳过整个流水线
- MD5 秒传仅查未删除的文件（`isFolder=0, deleteTime IS NULL`），自动插入新记录并复用已有 `storageKey`

---

## 3. 创建文件夹

```
POST /api/file/create-folder
```

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `folderName` | `string` | ✅ | — | 文件夹名 |
| `parentId` | `number` | ❌ | `0` | 父目录 ID |

### 请求示例

```bash
curl -X POST http://localhost:8088/api/file/create-folder \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"folderName":"我的图片","parentId":0}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 44,
    "fileName": "我的图片",
    "filePath": "/我的图片",
    "fileType": "FOLDER",
    "isFolder": 1,
    "processStatus": 3,
    "parentId": 0
  }
}
```

### 备注

- 文件夹 `processStatus` 直接设为 3（无需处理）
- `isFolder = 1`

---

## 4. 文件列表

```
GET /api/file/list
```

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `parentId` | `number` | ❌ | `0` | 父目录 ID，0 = 根目录 |

### 请求示例

```bash
# 根目录
curl "http://localhost:8088/api/file/list?parentId=0" \
  -H "Authorization: Bearer <token>"

# 指定目录
curl "http://localhost:8088/api/file/list?parentId=44" \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    {
      "id": 44,
      "fileName": "我的图片",
      "fileType": "FOLDER",
      "isFolder": 1,
      "processStatus": 3,
      "parentId": 0,
      "thumbnailUrl": null
    },
    {
      "id": 43,
      "fileName": "photo.png",
      "fileType": "IMAGE",
      "isFolder": 0,
      "fileSize": 204800,
      "processStatus": 1,
      "parentId": 0,
      "thumbnailKey": "1/2026/06/thumb_a1b2c3d4.jpg",
      "thumbnailUrl": "http://localhost:9000/allahpan-thumbnails/1/2026/06/thumb_a1b2c3d4.jpg?X-Amz-..."
    }
  ]
}
```

### 排序

文件夹优先，同类型按创建时间倒序：`ORDER BY is_folder DESC, create_time DESC`

### 备注

- 只返回未删除的文件（`deleteTime IS NULL`）
- 如有 `thumbnailKey`，自动附加 `thumbnailUrl`（`/api/file/{id}/thumbnail`）

---

## 5. 目录树（面包屑导航）

```
GET /api/file/tree/{folderId}
```

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `folderId` | path | `number` | 目标文件夹 ID |

### 请求示例

```bash
curl http://localhost:8088/api/file/tree/43 \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": [
    { "id": 0, "fileName": "/" },
    { "id": 44, "fileName": "我的图片" },
    { "id": 43, "fileName": "photo.png" }
  ]
}
```

### 备注

- 列表顺序：根 → 子目录 → ... → 目标文件
- 从 target 向 parent 链回溯，结果反转后返回

---

## 6. 文件详情

```
GET /api/file/{fileId}
```

### 请求示例

```bash
curl http://localhost:8088/api/file/43 \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 43,
    "fileName": "photo.png",
    "fileType": "IMAGE",
    "fileSize": 204800,
    "contentType": "image/png",
    "storageKey": "1/2026/06/a1b2c3d4.png",
    "thumbnailKey": "1/2026/06/thumb_a1b2c3d4.jpg",
    "isFolder": 0,
    "processStatus": 3,
    "parentId": 44,
    "filePath": "/我的图片/photo.png",
    "md5": "d41d8cd98f00b204e9800998ecf8427e",
    "createTime": "2026-06-08T12:00:00.000+00:00"
  }
}
```

---

## 7. 删除文件（移入垃圾站）

```
DELETE /api/file/{fileId}
```

软删除，设置 `deleteTime`。文件夹会递归删除所有子节点。

### 请求示例

```bash
curl -X DELETE http://localhost:8088/api/file/43 \
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

- 只设置 `deleteTime = new Date()`，不删除数据
- 文件夹会递归软删除所有未删除子节点

---

## 8. 垃圾站列表

```
GET /api/file/trash
```

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `pageNum` | `number` | ❌ | `1` | 页码 |
| `pageSize` | `number` | ❌ | `20` | 每页条数 |

### 请求示例

```bash
curl "http://localhost:8088/api/file/trash?pageNum=1&pageSize=20" \
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
      "deleteTime": "2026-06-08T13:00:00.000+00:00",
      "fileType": "IMAGE",
      "fileSize": 204800
    }
  ]
}
```

### 备注

- 只返回 `deleteTime IS NOT NULL` 的文件
- 按 `deleteTime DESC` 排序

---

## 9. 恢复文件

```
PUT /api/file/trash/{fileId}/restore
```

### 请求示例

```bash
curl -X PUT http://localhost:8088/api/file/trash/43/restore \
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

- 清除 `deleteTime`（设为 null）
- 检查父文件夹是否在垃圾站，若是则拒绝："请先恢复父文件夹"
- 文件夹会递归恢复所有子节点

---

## 10. 永久删除

```
DELETE /api/file/trash/{fileId}
```

物理删除，不可恢复。会删除本地文件和数据库记录。

### 请求示例

```bash
curl -X DELETE http://localhost:8088/api/file/trash/43 \
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

- 删除本地原文件和缩略图
- 文件夹会递归永久删除所有子节点
- 每天 3 AM 自动清理 60 天前的垃圾站文件（`TrashCleanupTask`）

---

## 11. 下载文件

```
GET /api/file/{fileId}/download
```

**本地文件服务**：从本地磁盘读取文件，直接返回 `FileSystemResource`（二进制流）；本地不存在则返回 404。

### 请求示例

```bash
curl "http://localhost:8088/api/file/43/download" \
  -H "Authorization: Bearer <token>"
```

### 响应 — 本地文件

HTTP 200，直接返回文件二进制流：
```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename*=UTF-8''photo.png
```

### 备注

- 文件夹不支持下载
- 已删除文件不支持下载
- 本地文件直接流式返回

---

## 11.5. 内联预览

```
GET /api/file/{fileId}/stream
```

与下载类似，但 `Content-Disposition: inline`（浏览器内联显示而非下载）。

### 响应 — 本地文件

```
Content-Type: {实际MIME类型}
Content-Disposition: inline; filename*=UTF-8''photo.png
```

### 备注

- 文件夹和已删除文件同样受限
- 适用于图片/PDF 等浏览器直接预览
- 本地文件直接流式返回

---

## 11.6. 缩略图

```
GET /api/file/{fileId}/thumbnail
```

返回文件缩略图（JPEG）。

### 响应 — 本地

```
Content-Type: image/jpeg
（二进制流）
```

### 响应 — 无缩略图

HTTP 404，无缩略图 key。

### 备注

- 公开端点（在 SecurityConfig 白名单中）
- 本地缩略图存储在 `.thumbnails/` 子目录下

---

## 11.7. SSE 实时推送

```
GET /api/file/watch?token=<jwt>
```

服务端推送事件 (Server-Sent Events)，用于前端实时接收文件变更通知，无需轮询。

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `token` | `string` | ✅ | — | JWT token（通过 query param 传递，因为 EventSource 不支持自定义请求头） |

### 事件类型

| 事件 | 数据 | 说明 |
|------|------|------|
| `connected` | `{message: "..."}` | SSE 连接成功确认 |
| `file-created` | `{fileId, parentId, fileName, ...}` | 新文件创建（含 local watcher 发现） |
| `file-updated` | `{fileId, parentId, processStatus, thumbnailKey, originText, ...}` | 文件更新（pipeline 进度、重命名等） |
| `file-deleted` | `{fileId, parentId}` | 文件删除 |
| `sync-complete` | `{message: "..."}` | 全量同步完成 |

### 浏览器示例

```javascript
const es = new EventSource(`http://localhost:8088/api/file/watch?token=${jwt}`);
es.addEventListener('file-created', e => { /* 刷新文件列表 */ });
es.addEventListener('file-updated', e => { /* 更新文件状态 */ });
```

### 备注

- SSE 超时 30 分钟，前端应自动重连
- JWT 手动校验（EventSource 无法设 Authorization 头）
- 流水线每阶段完成后通过 `notifyStatusChange` 推送 `file-updated` 事件

---

## 12. 重命名文件

```
PUT /api/file/{fileId}/rename
```

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `newName` | `string` | ✅ | 新文件名 |

```bash
curl -X PUT http://localhost:8088/api/file/43/rename \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"newName":"new-name.png"}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 43,
    "fileName": "new-name.png",
    "filePath": "/我的图片/new-name.png",
    "parentId": 44,
    "isFolder": 0
  }
}
```

### 备注

- 自动重建 `filePath`
- 文件夹重命名时，**递归重建所有子孙节点的 `filePath`**
- 已删除文件不可重命名

---

## 13. 移动文件

```
PUT /api/file/{fileId}/move
```

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `targetParentId` | `number` | ❌ | `0` | 目标文件夹 ID，0=根目录 |

```bash
curl -X PUT http://localhost:8088/api/file/43/move \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"targetParentId":45}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 43,
    "fileName": "photo.png",
    "filePath": "/文档/photo.png",
    "parentId": 45,
    "isFolder": 0
  }
}
```

### 备注

- 自动重建 `filePath`
- 文件夹移动时，**递归重建所有子孙节点的 `filePath`**
- 校验规则：
  - 目标必须是存在的文件夹且不在垃圾站
  - 不能移动到自身
  - 不能移动到自己的子文件夹（循环检测）
  - 移动到同一目录（`targetParentId == parentId`）时直接返回，无副作用
- 已删除文件不可移动

---

## 14. 批量删除

```
DELETE /api/file/batch
```

将多个文件移入垃圾站。单个失败不影响其他。

### 请求

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `fileIds` | `number[]` | ✅ | 文件 ID 数组 |

```bash
curl -X DELETE http://localhost:8088/api/file/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"fileIds":[43,44,45]}'
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "deletedCount": 2,
    "failedIds": [45]
  }
}
```

### 备注

- 容错处理：不存在的 ID 或已删除的文件会被跳过
- 文件夹会递归软删除所有子节点
- `failedIds` 记录处理失败的 ID（文件不存在、已删除等）
- 同时清理本地磁盘镜像文件
