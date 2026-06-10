# 06 — 搜索服务 API（search 应用）

**Base URL:** `http://localhost:8081`

搜索服务的 5 个端点**不使用 `CommonResult` 包装**，直接返回 `Map<String, Object>`。

> **重要**: 所有 5 个端点均返回原始 `Map<String, Object>`（如 `{success: true}`、`{list: [...], totalCount: N}`），不使用 `CommonResult` 包装。调用方（core 模块的 `SearchController` / `EsIndexServiceImpl`）自行处理响应和错误。

> 这些接口主要供 `allahpan-core` 内部调用（`EsIndexServiceImpl` / `SearchController`），也可直接用于管理操作。

---

## 1. 索引文件

```
POST /es-admin/files/index
```

将单个文件索引到 Elasticsearch。

### 请求

Content-Type: `application/json`

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `fileId` | `number/string` | ❌ | `0` | 文件 ID |
| `fileName` | `string` | ❌ | — | 文件名 |
| `fileType` | `string` | ❌ | — | 文件类型 |
| `originText` | `string` | ❌ | `""` | OCR 提取文字 |
| `filePath` | `string` | ❌ | — | 虚拟路径 |
| `uploaderId` | `number/string` | ❌ | `0` | 上传者 ID |
| `uploaderName` | `string` | ❌ | — | 上传者昵称 |
| `fileSize` | `number/string` | ❌ | `0` | 文件大小 |
| `isFolder` | `boolean` | ❌ | `false` | 是否文件夹 |
| `createTime` | `string` | ❌ | `当前时间` | ISO 格式或 `yyyy-MM-dd HH:mm:ss` |

### 请求示例

```bash
curl -X POST http://localhost:8081/es-admin/files/index \
  -H "Content-Type: application/json" \
  -d '{
    "fileId": 43,
    "fileName": "photo.png",
    "fileType": "IMAGE",
    "originText": "一张包含文字的截图",
    "filePath": "/我的图片/photo.png",
    "uploaderId": 1,
    "uploaderName": "user@example.com",
    "fileSize": 204800,
    "isFolder": false,
    "createTime": "2026-06-08T12:00:00.000Z"
  }'
```

### 响应

```json
{
  "success": true
}
```

---

## 2. 删除索引

```
DELETE /es-admin/files/{fileId}
```

### 请求

| 参数 | 位置 | 类型 | 说明 |
|------|------|------|------|
| `fileId` | path | `number` | 文件 ID |

### 请求示例

```bash
curl -X DELETE http://localhost:8081/es-admin/files/43
```

### 响应

```json
{
  "success": true
}
```

---

## 2.5. 清空所有索引

```
DELETE /es-admin/files/_all
```

清除 `allahpan_files` 索引中的所有文档。用于全量重建索引的前置步骤。

### 请求示例

```bash
curl -X DELETE http://localhost:8081/es-admin/files/_all
```

### 响应

```json
{
  "success": true,
  "deleted": 1500
}
```

---

## 3. 搜索

```
GET /es-admin/files/search
```

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | `string` | ✅ | — | 搜索关键词 |
| `fileType` | `string` | ❌ | — | 文件类型过滤 |
| `pageNum` | `number` | ❌ | `1` | 页码 |
| `pageSize` | `number` | ❌ | `20` | 每页条数 |

### 请求示例

```bash
curl "http://localhost:8081/es-admin/files/search?keyword=截图&fileType=IMAGE&pageNum=1&pageSize=10"
```

### 响应

```json
{
  "list": [
    {
      "fileId": 43,
      "fileName": "photo.png",
      "fileType": "IMAGE",
      "filePath": "/我的图片/photo.png",
      "uploaderName": "user@example.com",
      "fileSize": 204800,
      "createTime": "2026-06-08T12:00:00.000+00:00",
      "fileNameHighlight": "<mark>截图</mark>.png",
      "contentSnippets": [
        "一张包含<mark>截图</mark>文字的图片..."
      ],
      "score": 2.15
    }
  ],
  "totalCount": 1,
  "aggregations": {
    "fileTypes": [
      { "type": "IMAGE", "count": 1 }
    ]
  }
}
```

> 响应字段说明见 [05-search-core.md](05-search-core.md) 的响应字段表。

### 搜索实现细节

- **匹配字段**: `multi_match` 查询 `fileName`（权重 10×）和 `originText`（权重 5×），`BestFields` 策略
- **筛选**: `fileType` 非空时添加 `term` 过滤
- **高亮**: `fileName` 返回完整字段，`originText` 最多 3 段（每段 100 字符），标记为 `<mark>...</mark>`
- **聚合**: `fileType` 的 `terms` 聚合（top 10）
- **分词**: `ik_max_word` 中文分词器

---

## 4. 全量重建索引

```
POST /es-admin/rebuild
```

批量重建所有文件的 ES 索引。

### 请求

Content-Type: `application/json`

Body 为文件数据数组，每个元素结构同 `POST /es-admin/files/index` 的请求体：

```json
[
  { "fileId": 1, "fileName": "a.png", ... },
  { "fileId": 2, "fileName": "b.pdf", ... }
]
```

### 请求示例

```bash
curl -X POST http://localhost:8081/es-admin/rebuild \
  -H "Content-Type: application/json" \
  -d '[
    {"fileId":43,"fileName":"photo.png","fileType":"IMAGE",...},
    {"fileId":44,"fileName":"doc.pdf","fileType":"DOCUMENT",...}
  ]'
```

### 响应

```json
{
  "success": true,
  "total": 1500,
  "indexed": 1497,
  "failed": 3
}
```

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `boolean` | 固定为 `true` |
| `total` | `number` | 提交的总记录数 |
| `indexed` | `number` | 成功索引数 |
| `failed` | `number` | 失败数（异常被吞，不影响后续记录） |

---

## 错误处理

搜索服务控制器无全局异常处理。异常时 Spring 默认返回 HTTP 500，无 JSON 错误体。

## ES 文档结构

Index: `allahpan_files`（1 shard, 0 replica）

| 字段 | ES 类型 | 说明 |
|------|---------|------|
| `fileId` | `@Id` (Long) | 文档 ID |
| `fileName` | `text` + `ik_max_word` | 文件名 |
| `fileType` | `keyword` | 文件类型（精确匹配） |
| `originText` | `text` + `ik_max_word` | OCR 文字（全文检索） |
| `filePath` | `text` + `ik_max_word` | 虚拟路径 |
| `uploaderId` | `long` | 上传者 ID |
| `uploaderName` | `keyword` | 上传者昵称 |
| `fileSize` | `long` | 文件大小 |
| `isFolder` | `boolean` | 是否文件夹 |
| `createTime` | `date` | 创建时间 |
