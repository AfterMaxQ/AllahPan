# 03 — 文件上传流程架构图

## MinIO 对象存储

AllahPan 采用 **MinIO 对象存储**：

- **MinIO**: 兼容 S3 的对象存储，3 个 bucket（`allahpan-files`、`allahpan-thumbnails`、`allahpan-trash`）。
- **storageKey**: 用户隔离的对象 key，如 `1/2026/06/{UUID}.png`。
- **秒传**: MD5 去重，相同文件跳过上传直接创建数据库记录（`processStatus=3`）。
- **流式 MD5**: 使用 `DigestInputStream` 边上传边计算 MD5，避免将整个文件加载到内存。

## 完整上传时序

```mermaid
sequenceDiagram
    actor 浏览器
    participant FileController as FileController
    participant FileService as FileServiceImpl
    participant MinioUtil as MinioUtil
    participant FileMapper as FileMapper
    participant MySQL as MySQL (files)
    participant RabbitMQ as RabbitMQ

    Note over 浏览器,RabbitMQ: ═══ Step 1: multipart 上传 ═══
    浏览器->>FileController: POST /api/file/upload<br/>{file: binary, parentId: 0}
    FileController->>FileService: upload(multipartFile, parentId)

    FileService->>FileService: 校验父文件夹存在
    FileService->>FileService: 解析文件路径（父目录链拼接）
    FileService->>FileService: DigestInputStream 边写边算 MD5
    FileService->>MinioUtil: putObject(storageKey, digestStream, size, contentType)
    MinioUtil-->>FileService: 上传完成, MD5 digest ready

    FileService->>FileMapper: selectByExample(md5=?, isFolder=0, deleteTime IS NULL)
    alt MD5 秒传
        MySQL-->>FileMapper: existingFile
        FileService->>MinioUtil: removeObject(storageKey)（清理刚上传的文件）
        FileService->>FileMapper: insert(新记录, 复用 storageKey/processStatus=3)
        MySQL-->>FileMapper: newFileId
        FileService-->>FileController: File (processStatus=3)
        FileController-->>浏览器: {instant: true, fileId}
    else 新文件
        FileService->>FileService: detectFileType(contentType)
        Note over FileService: IMAGE / VIDEO / DOCUMENT / OTHER
        FileService->>FileMapper: insert(file, processStatus=0)
        MySQL-->>FileMapper: fileId
        FileService-->>FileController: File (processStatus=0)
        FileController->>RabbitMQ: FileProcessSender.sendProcess(UPLOADED)
        Note over RabbitMQ: 触发流水线: 缩略图→文字提取→ES索引
        FileController-->>浏览器: {id, fileName, filePath, processStatus: 0}
    end
```

## processStatus 状态机（RabbitMQ 流水线）

```mermaid
stateDiagram-v2
    [*] --> pending: upload
    pending --> thumbnail_done: "RabbitMQ: 生成缩略图"
    thumbnail_done --> text_done: "RabbitMQ: OCR 提取文字"
    text_done --> indexed: "RabbitMQ: 写入 ES 索引"
    pending --> failed: 处理异常
    thumbnail_done --> failed: 处理异常
    text_done --> failed: 处理异常

    note right of pending: processStatus = 0<br/>等待处理
    note right of thumbnail_done: processStatus = 1<br/>缩略图完成
    note right of text_done: processStatus = 2<br/>文字提取完成
    note right of indexed: processStatus = 3<br/>全部完成(含ES)
    note right of failed: processStatus = -1
```

> **当前状态**: 文件上传后经 RabbitMQ 流水线: `UPLOADED → THUMBNAILED → TEXT_EXTRACTED → INDEXED`。文件夹和秒传文件直接 `processStatus=3`。
> **缩略图**: IMAGE（缩放 300px）+ PDF（PDFBox 渲染首帧，可配置 DPI，默认 150）。读写均通过 MinIO bucket。
> **文字提取**: IMAGE（Ollama OCR）+ PDF（PDFBox）+ DOCX/DOC/XLSX/XLS/PPTX/PPT（Apache POI）+ 纯文本（UTF-8 读取）。从 MinIO 获取文件流。
> **ES 索引**: 失败降级，不标记 processStatus=-1。
> **基础设施错误**: Ollama/ES/MinIO 不可达时，重试耗尽后降级而非标记失败。
> **重试最多 3 次**，指数退避 30s/60s/120s。

## 上传入口

文件通过 `POST /api/file/upload`（multipart 表单）直接上传到应用服务器。不存在本地文件监控——文件只能通过 Web API 创建，不会从外部文件系统同步。

## storageKey 结构

```
{userId}/{yyyy/MM}/{UUID}{ext}

示例: 1/2026/06/d27fed91-2fed-4e3e-bbcd-ce19dc3410c5.png
      │  │  │    │                                 │
      │  │  │    │                                 └── 原始扩展名
      │  │  │    └── UUID 去重
      │  │  └── 月份
      │  └── 年份
      └── 用户ID (隔离)
```

## 秒传（Instant Upload）流程

```mermaid
flowchart TD
    A["upload(md5, fileName, parentId)"] --> B{"MD5 在 files 表中存在?<br/>(isFolder=0, deleteTime IS NULL)"}
    B -->|"是"| C["取 existingFile.storageKey<br/>取 existingFile.fileSize<br/>取 existingFile.contentType<br/>取 existingFile.fileType"]
    C --> D["清理 MinIO 中刚上传的临时对象<br/>minioUtil.removeObject(newKey)"]
    D --> E["INSERT 新记录<br/>uploaderId = 当前用户<br/>parentId = 请求参数<br/>fileName = 请求参数<br/>storageKey = 已有的<br/>processStatus = 3"]
    E --> F["跳过流水线（秒传）"]
    B -->|"否"| G["文件已上传到 MinIO + 新建 DB 记录<br/>processStatus = 0"]
    G --> H["触发 RabbitMQ 流水线"]
```

## 分片上传流程（大文件）

大文件通过 `ChunkController` 分片上传，支持断点续传：

```
POST /api/file/chunk/init        — 初始化上传会话
POST /api/file/chunk/upload      — 上传分片
POST /api/file/chunk/complete    — 合并分片并完成
GET  /api/file/chunk/status/{uploadId}  — 查询上传进度
```

### 完整分片上传时序

```mermaid
sequenceDiagram
    actor 浏览器
    participant ChunkController as ChunkController
    participant ChunkService as ChunkUploadServiceImpl
    participant Redis as Redis
    participant Disk as 本地临时目录
    participant MinioUtil as MinioUtil
    participant FileService as FileServiceImpl
    participant MySQL as MySQL
    participant RabbitMQ as RabbitMQ

    Note over 浏览器,RabbitMQ: ═══ Step 1: 初始化 ═══
    浏览器->>ChunkController: POST /api/file/chunk/init<br/>{fileName, totalChunks, fileSize, parentId}
    ChunkController->>ChunkService: init(fileName, totalChunks, fileSize, parentId)
    ChunkService->>ChunkService: 生成 uploadId (UUID)
    ChunkService->>Redis: HSET chunk:upload:{uploadId}<br/>(fileName, totalChunks, parentId, ...)
    ChunkService->>Disk: mkdir {tempDir}/allahpan-chunks/{uploadId}
    ChunkService-->>浏览器: {uploadId, uploadedChunks: []}

    Note over 浏览器,RabbitMQ: ═══ Step 2: 逐片上传 ═══
    loop 每个分片
        浏览器->>ChunkController: POST /api/file/chunk/upload<br/>{uploadId, chunkIndex, chunk: binary}
        ChunkController->>ChunkService: uploadChunk(uploadId, chunkIndex, file)
        ChunkService->>Disk: write chunk to {tempDir}/{uploadId}/{chunkIndex}
        ChunkService->>Redis: SADD chunk:upload:{uploadId}:chunks {chunkIndex}
        ChunkService-->>浏览器: {chunkIndex, success: true}
    end

    Note over 浏览器,RabbitMQ: ═══ Step 3: 合并完成 ═══
    浏览器->>ChunkController: POST /api/file/chunk/complete<br/>{uploadId}
    ChunkController->>ChunkService: complete(uploadId)
    ChunkService->>Redis: HGETALL chunk:upload:{uploadId}
    ChunkService->>Disk: 合并所有分片 → 完整文件
    ChunkService->>MinioUtil: putObject(storageKey, mergedFile)
    ChunkService->>FileService: MD5 秒传检测 + DB 插入
    FileService->>MySQL: INSERT files 记录
    FileService->>RabbitMQ: sendProcess(UPLOADED)
    ChunkService->>Redis: DEL chunk:upload:{uploadId}*
    ChunkService->>Disk: 清理临时目录
    ChunkService-->>浏览器: {fileId, fileName, processStatus: 0}
```

### 断点续传

如果 `uploadId` 已存在（会话未过期），`init` 返回已上传的分片索引列表：

```
GET /api/file/chunk/status/{uploadId}
→ {uploadId, totalChunks, uploadedChunks: [0, 1, 3], ...}
```

前端跳过已上传的分片，只补传缺失部分。

### Redis 会话结构

| Key | 类型 | TTL | 内容 |
|-----|------|-----|------|
| `chunk:upload:{uploadId}` | Hash | 24h | fileName, totalChunks, fileSize, parentId, md5 |
| `chunk:upload:{uploadId}:chunks` | Set | 24h | 已上传的分片索引集合 |

### 定时清理

`ChunkUploadServiceImpl` 使用 `@Scheduled(cron = "0 0 * * * ?")` 每小时清理超过 `allahpan.chunk.expire-hours`（默认 24h）的过期临时目录和 Redis 会话。

## 关键文件索引

| 步骤 | 文件 | 方法 |
|------|------|------|
| 上传端点 | `FileController.java` | `upload()` |
| 流式上传 + MD5 | `FileServiceImpl.java` | `storeAndCalculateMd5()` |
| MinIO 上传 | `MinioUtil.java` | `putObject()` |
| MD5 秒传检测 | `FileServiceImpl.java` | `upload()` |
| 文件记录入库 | `FileServiceImpl.java` | `upload()` |
| 文件类型检测 | `FileServiceImpl.java` | `detectFileType()` |
| 文件夹创建 | `FileServiceImpl.java` | `createFolder()` |
| RabbitMQ 流水线 | `FileProcessReceiver.java` | `handle()` |
| SSE 事件广播 | `SseBroadcaster.java` | `broadcast()` |
| 分片初始化 | `ChunkController.java` | `init()` |
| 分片上传 | `ChunkController.java` | `uploadChunk()` |
| 分片合并 | `ChunkUploadServiceImpl.java` | `complete()` |
| 分片状态 | `ChunkController.java` | `status()` |
| 过期清理 | `ChunkUploadServiceImpl.java` | `@Scheduled(cron="0 0 * * * ?")` |
