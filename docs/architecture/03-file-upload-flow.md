# 03 — 文件上传流程架构图

## 本地存储架构

AllahPan 采用 **本地磁盘直写** 存储：

- **本地磁盘**: 所有上传文件的存储位置（`%USERPROFILE%\AllahPan\{email}\`）。文件通过 multipart 表单直接上传到应用服务器，写入本地文件系统。
- **storageKey**: 用户隔离的本地路径，如 `1/2026/06/{UUID}.png`，相对于用户根目录。
- **秒传**: MD5 去重，相同文件跳过上传直接创建数据库记录（`processStatus=3`）。

## 完整上传时序

```mermaid
sequenceDiagram
    actor 浏览器
    participant FileController as FileController
    participant FileService as FileServiceImpl
    participant LSS as LocalStorageService
    participant FileMapper as FileMapper
    participant MySQL as MySQL (files)
    participant RabbitMQ as RabbitMQ

    Note over 浏览器,RabbitMQ: ═══ Step 1: multipart 上传 ═══
    浏览器->>FileController: POST /api/file/upload<br/>{file: binary, parentId: 0}
    FileController->>FileService: upload(multipartFile, parentId)

    FileService->>FileService: 校验父文件夹存在
    FileService->>FileService: 解析文件路径（父目录链拼接）
    FileService->>LSS: store(inputStream) + 边写边算 MD5
    LSS-->>FileService: {storageKey, md5, fileSize}

    FileService->>FileMapper: selectByExample(md5=?, isFolder=0, deleteTime IS NULL)
    alt MD5 秒传
        MySQL-->>FileMapper: existingFile
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

## processStatus 状态机（Phase 4 RabbitMQ 流水线）

```mermaid
stateDiagram-v2
    [*] --> pending: confirmUpload
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
> **缩略图**: IMAGE（缩放 300px）+ PDF（PDFBox 渲染首帧，可配置 DPI，默认150）。
> **文字提取**: IMAGE（Ollama OCR）+ PDF（PDFBox）+ DOCX/DOC/XLSX/XLS/PPTX/PPT（Apache POI）+ 纯文本（UTF-8 读取）。
> **ES 索引**: 失败降级，不标记 processStatus=-1。
> **基础设施错误**: Ollama/ES 不可达时，重试耗尽后降级而非标记失败。
> **重试最多 3 次**，指数退避 30s/60s/120s。

## FileSystemWatcher 文件系统事件上传

当用户将文件直接拖入本地 AllahPan 文件夹时，`FileSystemWatcher` 自动发现并同步到数据库：

```mermaid
flowchart TD
    A["用户在本地文件夹创建/修改文件"] --> B["WatchService 检测到 ENTRY_CREATE"]
    B --> C["debounce (1s) 避免重复事件"]
    C --> D["reconcilePath: 判断文件/文件夹"]
    D --> E{"DB 中已存在?"}
    E -->|"是（parentId+fileName 匹配）"| F["跳过（避免重复）"]
    E -->|"否"| G["ensureFileInDb: 计算 MD5"]
    G --> H{"MD5 秒传检查"}
    H -->|"秒传"| I["复用已有 storageKey 创建 DB 记录"]
    H -->|"新文件"| J["FileMapper.insert() 创建 DB 记录"]
    J --> K["FileProcessSender.sendProcess(UPLOADED)"]
    K --> L["SSE 推送 file-created 事件"]
    I --> L

    subgraph "定时全量同步 (每5分钟)"
        M["fullSync(): 遍历本地文件树"]
        M --> N["对比 DB 记录"]
        N --> O["新增/删除 DB 差异记录"]
    end
```

- **启动时**: 3 秒后执行首次全量同步
- **防重复**: parentId + fileName 二级去重，避免 web 上传镜像到本地时触发重复事件
- **SSE 通知**: 每次变更推送 `file-created` / `file-updated` / `file-deleted` 事件

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
    C --> D["INSERT 新记录<br/>uploaderId = 当前用户<br/>parentId = 请求参数<br/>fileName = 请求参数<br/>storageKey = 已有的<br/>processStatus = 3"]
    D --> E["跳过流水线（秒传）"]
    B -->|"否"| F["写入本地磁盘 + 新建 DB 记录<br/>processStatus = 0"]
    F --> G["触发 RabbitMQ 流水线"]
```

## 关键文件索引

| 步骤 | 文件 | 方法 |
|------|------|------|
| 上传端点 | `FileController.java` | `upload()` |
| MD5 秒传检测 | `FileServiceImpl.java` | `upload()` |
| 本地存储写入 | `LocalStorageService.java` | `store()` |
| 文件记录入库 | `FileServiceImpl.java` | `upload()` |
| 文件类型检测 | `FileServiceImpl.java` | `detectFileType()` |
| 文件夹创建 | `FileServiceImpl.java` | `createFolder()` |
| 文件监控 | `FileSystemWatcher.java` | `reconcilePath()`, `fullSync()` |
| 本地文件 I/O | `LocalStorageService.java` | `store()`, `read()`, `delete()` |
| RabbitMQ 流水线 | `FileProcessReceiver.java` | `handle()` |
