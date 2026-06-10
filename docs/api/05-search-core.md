# 05 — 搜索 API（core 代理）

**Base URL:** `http://localhost:8088/api/search`

需要认证：`Authorization: Bearer <token>`

---

## 搜索

```
GET /api/search
```

此端点不直接查询 Elasticsearch，而是通过 RestTemplate 代理转发到搜索服务 `http://localhost:8081/es-admin/files/search`。

### 请求

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | `string` | ✅ | — | 搜索关键词 |
| `fileType` | `string` | ❌ | — | 文件类型过滤（`IMAGE`/`VIDEO`/`DOCUMENT`/`OTHER`） |
| `pageNum` | `number` | ❌ | `1` | 页码 |
| `pageSize` | `number` | ❌ | `20` | 每页条数 |

### 请求示例

```bash
# 全文搜索
curl "http://localhost:8088/api/search?keyword=会议纪要" \
  -H "Authorization: Bearer <token>"

# 按类型过滤
curl "http://localhost:8088/api/search?keyword=合同&fileType=DOCUMENT&pageNum=1&pageSize=10" \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "list": [
      {
        "fileId": 43,
        "fileName": "会议纪要_2026.pdf",
        "fileType": "DOCUMENT",
        "filePath": "/工作文档/会议纪要_2026.pdf",
        "uploaderName": "user@example.com",
        "fileSize": 1048576,
        "createTime": "2026-06-08T12:00:00.000+00:00",
        "fileNameHighlight": "<mark>会议纪要</mark>_2026.pdf",
        "contentSnippets": [
          "本次<mark>会议纪要</mark>记录了关于项目进度的讨论...",
          "与会人员一致同意<mark>会议纪要</mark>中的行动计划..."
        ],
        "score": 2.15
      }
    ],
    "totalCount": 1,
    "aggregations": {
      "fileTypes": [
        { "type": "DOCUMENT", "count": 1 }
      ]
    }
  }
}
```

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `list` | `array` | 搜索结果列表 |
| `list[].fileId` | `number` | 文件 ID |
| `list[].fileName` | `string` | 文件名 |
| `list[].fileType` | `string` | 文件类型 |
| `list[].filePath` | `string` | 虚拟路径 |
| `list[].uploaderName` | `string` | 上传者 |
| `list[].fileSize` | `number` | 文件大小（字节） |
| `list[].createTime` | `string(ISO)` | 创建时间 |
| `list[].fileNameHighlight` | `string` | 文件名高亮（含 `<mark>` 标签） |
| `list[].contentSnippets` | `string[]` | 正文片段高亮，最多 3 段 |
| `list[].score` | `number` | ES 相关性评分 |
| `totalCount` | `number` | 匹配总数 |
| `aggregations.fileTypes` | `array` | 文件类型分布（top 10） |

### 搜索权重

| 字段 | 权重 |
|------|------|
| `fileName` | **10x** |
| `originText` | **5x** |

中文分词使用 `ik_max_word`。

### 备注

- `originText` 搜索字段的数据来源是 Ollama OCR 管线：IMAGE 文件上传后，`OllamaService` 调用 qwen3.5:2b（think=false, num_predict=4096）提取文字，写入 `files.origin_text`（LONGTEXT BLOB 列）。只有 `processStatus=3`（已索引）的文件才能被搜索到。
- 依赖搜索服务 `:8081` 正常运行
- 搜索服务不可用时返回 `CommonResult.failed("搜索服务暂不可用，请稍后重试")`（捕获 `RestClientException`，不抛 500）
- 当前每次请求 `new RestTemplate()`，生产环境应注入 Bean 复用连接池
- 与直接调用 `:8081/es-admin/files/search` 的区别：本接口经过 JWT 认证并包装 `CommonResult`

---

## 重建搜索索引

```
POST /api/search/rebuild-index
```

清空并全量重建 Elasticsearch 索引。从 MySQL 读取所有未删除的非文件夹文件，重新索引到 ES。

### 请求示例

```bash
curl -X POST http://localhost:8088/api/search/rebuild-index \
  -H "Authorization: Bearer <token>"
```

### 响应示例

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "indexedCount": 1500
  }
}
```

### 实现步骤

1. 调用搜索服务 `DELETE /es-admin/files/_all` 清空索引
2. 从 MySQL `files` 表查询所有未删除的非文件夹文件
3. 逐条调用 `POST /es-admin/files/index` 重新索引
4. 搜索服务不可用时返回友好错误

### 备注

- 适用场景：ES 索引数据与 MySQL 不一致时手动修复
- 单个文件索引失败不影响其他文件（容错处理）
