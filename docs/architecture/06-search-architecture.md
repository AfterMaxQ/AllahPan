# 06 — 搜索系统架构

**最后更新**: 2026-06-13

---

## 1. 概述

AllahPan 采用 **独立搜索微服务** 架构，搜索服务 (`allahpan-search:8081`) 独立于主应用 (`allahpan-core:8088`) 运行。

```
用户搜索请求
     │
     ▼
┌─────────────────────┐
│  allahpan-web (Vue) │  ← 直接调用 core 的搜索 API
└────────┬────────────┘
         │ GET /api/file/search?keyword=xxx
         ▼
┌─────────────────────┐
│  allahpan-core:8088 │  ← 透传搜索请求
└────────┬────────────┘
         │ GET /api/file/search → RestTemplate
         ▼
┌─────────────────────┐
│  allahpan-search    │  ← Elasticsearch 搜索 + IK 分词
│  :8081 (127.0.0.1)  │
│                     │
│  Spring Data ES     │
│  + ES Client 8.11   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Elasticsearch 8.11 │  ← IK 中文分词 (ik_max_word / ik_smart)
│  :9200              │
└─────────────────────┘
```

---

## 2. 索引设计

### 2.1 索引定义

| 属性 | 值 |
|------|-----|
| 索引名 | `allahpan_files` |
| 分片数 | 1 |
| 副本数 | 0 (单节点开发环境) |

### 2.2 文档模型 (EsFile)

```java
@Document(indexName = "allahpan_files")
public class EsFile {

    @Id
    private Long fileId;                          // 对应 DB files.id

    @Field(type = Text, analyzer = "ik_max_word")  // IK 细粒度分词
    private String fileName;                       // 文件名

    @Field(type = Keyword)
    private String fileType;                       // IMAGE/VIDEO/DOCUMENT/OTHER/FOLDER

    @Field(type = Text, analyzer = "ik_max_word")  // IK 细粒度分词
    private String originText;                     // 提取的全文内容（搜索主战场）

    @Field(type = Text, analyzer = "ik_max_word")
    private String filePath;                       // 虚拟路径

    private Long uploaderId;
    private String uploaderName;                   // 上传者昵称
    private Long fileSize;
    private Boolean isFolder;

    @Field(type = Date)
    private Date createTime;
}
```

### 2.3 字段分析器策略

| 字段 | 类型 | 分析器 | 原因 |
|------|------|--------|------|
| `fileName` | Text + IK | `ik_max_word` | 中文文件名需要细粒度分词搜索 |
| `originText` | Text + IK | `ik_max_word` | 全文内容搜索，需要最多的分词匹配 |
| `filePath` | Text + IK | `ik_max_word` | 路径中包含中文文件夹名 |
| `fileType` | Keyword | — | 精确过滤，不分词 |
| `uploaderName` | Keyword | — | 精确匹配 |

---

## 3. 搜索查询流程

### 3.1 前端调用链

```
SearchBar.vue (用户输入)
  │
  ▼
search.js: searchFiles({ keyword, fileType, pageNum, pageSize })
  │
  ▼
GET /api/file/search?keyword=xxx&fileType=IMAGE&pageNum=1&pageSize=20
  │
  ▼
FileController.search()
  │
  ▼
RestTemplate → GET localhost:8081/es-admin/files/search
  │
  ▼
EsFileController.search()
  │
  ▼
EsFileServiceImpl.search()
```

### 3.2 搜索请求构建 (Elasticsearch Java Client)

```java
SearchRequest.of(s -> s
    .index("allahpan_files")
    .query(q -> q.bool(b -> {
        // ① must: 多字段匹配（至少命中一个）
        b.must(m -> m.multiMatch(mm -> mm
            .fields("fileName^10", "originText^5", "originText.char^2")
            .query(keyword)
            .type(TextQueryType.BestFields)));

        // ② should: 文件名命中额外加分 (boost ×50)
        b.should(sh -> sh.match(mt -> mt
            .field("fileName")
            .query(keyword)
            .boost(50.0f)));

        // ③ filter: 文件类型精确过滤（可选）
        if (fileType != null)
            b.filter(f -> f.term(t -> t.field("fileType").value(fileType)));

        return b;
    }))
    // ④ 高亮
    .highlight(h -> h
        .fields("fileName", hf -> hf.numberOfFragments(0)
                .preTags("<mark>").postTags("</mark>"))
        .fields("originText", hf -> hf.numberOfFragments(3).fragmentSize(100)
                .preTags("<mark>").postTags("</mark>"))
        .fields("originText.char", ...))
    // ⑤ 聚合: 按文件类型分组统计
    .aggregations("fileTypes", a -> a
        .terms(t -> t.field("fileType.keyword").size(10)))
    // ⑥ 分页
    .from((pageNum - 1) * pageSize)
    .size(pageSize)
);
```

### 3.3 权重策略

| 字段 | 权重 | 说明 |
|------|------|------|
| `fileName` | ×10 | 文件名匹配优先级最高 |
| `originText` | ×5 | 全文内容匹配次之 |
| `originText.char` | ×2 | 字符级子字段兜底 |
| `fileName` (should) | ×50 | 文件名命中额外 boost，确保标题结果排在前面 |

### 3.4 返回格式

```json
{
  "list": [
    {
      "fileId": 502,
      "fileName": "report.pdf",
      "fileType": "DOCUMENT",
      "filePath": "/Work/report.pdf",
      "uploaderName": "张三",
      "fileSize": 102400,
      "createTime": "2026-06-12T16:06:52.849+00:00",
      "fileNameHighlight": "2025年<mark>财务</mark>报告.pdf",
      "contentSnippets": [
        "本次<mark>财务</mark>报表显示...",
        "...经营活动<mark>财务</mark>指标..."
      ],
      "score": 12.45
    }
  ],
  "totalCount": 42,
  "aggregations": {
    "fileTypes": [
      {"type": "DOCUMENT", "count": 25},
      {"type": "IMAGE", "count": 15},
      {"type": "FOLDER", "count": 2}
    ]
  }
}
```

---

## 4. IK 分词器

### 4.1 安装

通过 Dockerfile 在 ES 8.11 镜像上安装：

```dockerfile
FROM docker.elastic.co/elasticsearch/elasticsearch:8.11.0
COPY elasticsearch-analysis-ik-8.11.0.zip /tmp/
RUN bin/elasticsearch-plugin install --batch file:///tmp/elasticsearch-analysis-ik-8.11.0.zip
```

### 4.2 两种模式

| 模式 | 说明 | 示例输入 | 示例输出 |
|------|------|----------|----------|
| `ik_max_word` | 最细粒度切分，穷尽词汇组合 | "中华人民共和国" | `中华人民共和国` `中华人民` `中华` `华人` `人民共和国` `人民` `共和国` `共和` `国` |
| `ik_smart` | 最粗粒度切分，非复合词 | "中华人民共和国" | `中华人民共和国` |

本系统使用 `ik_max_word`，保证搜索召回率最大。

### 4.3 索引策略

`fileName`、`originText`、`filePath` 三个 Text 字段在建索引时使用 `ik_max_word` 分析，搜索时同样使用 `ik_max_word` 分析查询词，实现中英文混合搜索。

---

## 5. 索引管理

### 5.1 初始化

搜索服务启动时 (`EsFileServiceImpl.ensureIndexExists()`):

```
① 删除旧索引 (避免不兼容的 mapping)
② 重新创建索引 allahpan_files
③ 若索引已存在 (resource_already_exists_exception) → 忽略
```

### 5.2 启动对账

core 模块启动后 (`EsIndexServiceImpl.scheduleStartupCleanup()`):

```
轮询 GET localhost:8081/es-admin/files/search?keyword=__health__
  ├── 每 5 秒一次, 最多 60 次 (5 分钟)
  ├── 搜索服务就绪 → 全量重建索引
  └── 5 分钟超时 → 放弃, 后续由定时对账补救
```

### 5.3 定时对账

```java
@Scheduled(fixedDelay = 30 * 60 * 1000, initialDelay = 10 * 60 * 1000)
```

每 30 分钟全量重建索引（删除全部 + 遍历 DB 重新索引所有未删除非文件夹文件），清理 ES 中的孤儿文档。

### 5.4 管理接口 (EsAdminController)

```
POST   /es-admin/rebuild    — 全量重建 (传入文件数据列表)
POST   /es-admin/files/index   — 索引单文件
DELETE /es-admin/files/{id}    — 删除单文件
DELETE /es-admin/files/_all    — 清空全部
GET    /es-admin/files/search  — 搜索
```

---

## 6. 数据流全景

```
                      ┌──────────────────────────────────┐
                      │          数据库 (MySQL)           │
                      │  files 表 (fileName, originText, │
                      │            filePath, fileType...) │
                      └──────────────┬───────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
        [文件上传]             [文件修改]              [文件删除]
              │                      │                      │
              ▼                      ▼                      ▼
      RabbitMQ 流水线        直接调用 index()         直接调用 delete()
      TEXT_EXTRACTED 后          │                      │
              │                  │                      │
              ▼                  │                      │
      EsIndexServiceImpl ────────┴──────────────────────┘
              │
              │ REST (localhost:8081)
              ▼
      EsFileController
              │
              ▼
      EsFileServiceImpl → Spring Data ES → Elasticsearch
```

---

## 7. 模块依赖

```
allahpan-core (8088)
  │
  ├── EsIndexService (接口)
  ├── EsIndexServiceImpl (实现, 通过 RestTemplate 调 search)
  │
  └── 依赖: allahpan-common (仅共用工具类, 无 search 依赖)

allahpan-search (8081, 绑定 127.0.0.1)
  │
  ├── EsFileRepository (Spring Data ES)
  ├── EsFileServiceImpl (搜索逻辑)
  ├── EsFileController (索引管理 + 搜索 API)
  ├── EsAdminController (管理接口)
  │
  └── 依赖: allahpan-common (仅共用工具类, 无 core 依赖)
```

两个模块完全解耦，通过 HTTP 通信。search 模块绑定 `127.0.0.1`，不对外暴露。

---

## 8. 前端搜索体验

### 8.1 搜索入口

- **全局搜索栏** (`AppHeader.vue`): 顶部常驻，支持跳转到搜索结果页
- **搜索结果页** (`Search.vue`): 展示文件列表 + 高亮片段 + 类型筛选

### 8.2 交互流程

```
用户输入关键词
     │
     ▼
SearchBar.vue (防抖 300ms)
     │
     ▼
router.push('/search?keyword=xxx')
     │
     ▼
Search.vue 加载
  ├── 调用 searchFiles API
  ├── 展示结果列表（文件名高亮 + 内容片段高亮）
  ├── 左侧类型筛选（使用聚合结果）
  └── 分页浏览
```

---

## 9. 配置速查

| 配置项 | 值 | 说明 |
|--------|-----|------|
| ES 索引名 | `allahpan_files` | 自动创建 |
| 分片/副本 | 1/0 | 单节点开发配置 |
| IK 版本 | 8.11.0 | 与 ES 版本一致 |
| 搜索服务端口 | 8081 | 绑定 127.0.0.1 |
| 搜索服务地址 | `http://localhost:8081` | core 通过此地址调用 |
| 定时对账间隔 | 30 分钟 | 清理孤儿文档 |
| 启动清理超时 | 5 分钟 | 轮询等待搜索服务就绪 |
