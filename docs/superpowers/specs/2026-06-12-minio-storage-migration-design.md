# MinIO 纯对象存储迁移 — 设计文档

**日期:** 2026-06-12  
**状态:** 设计已确认，待实现

## 背景

AllahPan 当前使用纯本地文件系统存储（`C:\Users\ray\AllahPan`），配合 RabbitMQ 处理流水线和 FileSystemWatcher 双向同步。实际运行中暴露了以下问题：

- 上传/下载稳定性差
- RabbitMQ 流水线不稳定（本质是本地文件系统+WatchService 同步不一致导致）
- 缩略图生成不可靠
- FileSystemWatcher 漏事件、DB 与磁盘状态不一致

**目标：** 将存储底座从本地文件系统迁移到 MinIO 对象存储，MinIO 作为唯一权威数据源。

## 架构决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 存储模式 | MinIO 唯一存储，移除本地文件系统 | 消除磁盘同步问题 |
| 上传/下载 | 后端代理（不用预签名 URL） | 家庭场景并发低，代理够用；MD5 秒传在服务端计算更可靠 |
| 处理管线 | 保留全部（缩略图+文本提取+ES索引） | 功能不缩减 |
| 消息队列 | 保留 RabbitMQ | RabbitMQ 本身稳定，问题在本地存储底座 |
| 缩略图 | 独立 bucket `allahpan-thumbnails` | 隔离清晰，可独立配置生命周期 |
| 回收站 | 独立 bucket `allahpan-trash` | 物理隔离，逻辑清晰 |

## 架构图

```
浏览器                          Core :8088                    RabbitMQ                MinIO
──────                          ──────────                    ────────                ────
  POST /upload ───────────────> FileController
                                │ MD5 流式计算
                                │ putObject ───────────────────────────────> allahpan-files
                                │ insert DB
                                │ sendProcess ───────────> ┌──────────────┐
  GET /download <─────────────  FileController             │ allahpan.file │──┐
                                │ getObject <────────────── MinIO files    │  │
                                                            └──────────────┘  │
                              消费者:                                         │
                               Stage1: getObject(files) → resize              │
                                       → putObject(thumbnails) <──────────────┤
                               Stage2: getObject(files) → POI/PDFBox/Ollama   │
                               Stage3: ES index → search :8081 <──────────────┘

  DELETE ─────────────────────> FileController
                                │ copyObject(files→trash)
                                │ removeObject(files)
                                │ update delete_time
```

## 存储模型

- **`storageKey`** 保持现有格式: `{userId}/yyyy/MM/{uuid}.{ext}`
- **`thumbnailKey`** 格式不变: `{userId}/yyyy/MM/{uuid}_thumb.jpg`
- **bucket 分配:**
  - `allahpan-files` — 所有上传文件
  - `allahpan-thumbnails` — 缩略图
  - `allahpan-trash` — 回收站（软删除文件移入此 bucket）

## 上传流程（3 步）

1. 浏览器 multipart POST → `FileController.upload()`
2. 后端流式接收 → 计算 MD5 → MD5 秒传检测 → 命中则复用已有 storageKey
3. `minioUtil.putObject(filesBucket, storageKey, inputStream, size, contentType)` → insert DB → `sendProcess(UPLOADED)`

前端不需改动。

## 下载/预览流程

```
GET /api/file/{id}/download  → minioUtil.getObject(filesBucket, storageKey)
                                → 流式拷贝到 ServletOutputStream
GET /api/file/{id}/stream    → 同上，Content-Disposition: inline
GET /api/file/{id}/thumbnail  → minioUtil.getObject(thumbBucket, thumbnailKey)
                                → 流式写回
```

## 处理管线（RabbitMQ，拓扑不变）

### Stage 1: 缩略图生成

- **当前:** 从本地磁盘 `FileInputStream` 读取 → Java2D/PDFBox 缩放 → 写入 `.thumbnails/`
- **改为:** `minioUtil.getObject(filesBucket, key)` → InputStream → Java2D/PDFBox → `minioUtil.putObject(thumbBucket, thumbnailKey, bytes, "image/jpeg")`

IMAGE 和 PDF 缩略图逻辑复用。

### Stage 2: 文本提取

- **当前:** 从本地磁盘 `FileInputStream` 读取 → POI/PDFBox → String
- **改为:** `minioUtil.getObject(filesBucket, key)` → InputStream → POI/PDFBox/Ollama → String

所有 POI/PDFBox 组件均接受 `InputStream`，改动量极小。

### Stage 3: ES 索引

完全不变 — `EsIndexServiceImpl.index()` 读 DB 字段，POST 到 search :8081。

## 回收站

| 操作 | MinIO 操作 | DB 操作 |
|------|-----------|---------|
| 软删除 | `copyObject(files→trash)` → `removeObject(files)` | `update delete_time=now` |
| 恢复 | `copyObject(trash→files)` → `removeObject(trash)` | `update delete_time=null` |
| 永久删除 | `removeObject(trash)` | `delete from files` |
| 定时清理 | `TrashCleanupTask` 扫 DB 30天前记录 → 删 trash bucket 对象 | `delete from files` |

同名冲突处理保留（`delete_time` 毫秒偏移），因为 DB 约束 `uk_parent_name_delete` 仍在。

## SSE 实时推送

移除 FileSystemWatcher 后，SSE 事件改为在业务操作点直接推送：

| 事件 | 触发点 |
|------|--------|
| `file-created` | `FileController.upload()` 成功后 |
| `file-deleted` | `FileController.delete()`/`batchDelete()` 成功后 |
| `file-updated` | `FileProcessReceiver` 每个阶段完成后 |
| `sync-complete` | 移除（不再有文件系统同步） |

SSE 端点 `GET /api/file/watch` 保留，SSE emitter 管理逻辑从 FileSystemWatcher 搬到 FileController。

## Maven 依赖

`allahpan-core/pom.xml` 新增：

```xml
<dependency>
    <groupId>io.minio</groupId>
    <artifactId>minio</artifactId>
    <version>8.5.10</version>
</dependency>
```

## 启动初始化

`MinioUtil` 构造函数 / `@PostConstruct` 中自动创建 bucket（如果不存在）：

```java
for (String bucket : List.of(bucketName, thumbnailBucket, trashBucket)) {
    boolean found = minioClient.bucketExists(BucketExistsArgs.builder().bucket(bucket).build());
    if (!found) {
        minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
    }
}
```

## 数据库

`init.sql` 和实体类**无需改动**。`files` 表的 `storage_key`、`thumbnail_key` 字段格式不变，只是值从「本地相对路径」变为「MinIO object key」（语义不变）。

## 配置变更

### docker-compose.yml

新增 MinIO 服务：
```yaml
minio:
  image: minio/minio
  container_name: minio
  ports:
    - "9000:9000"
    - "9001:9001"
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  volumes:
    - minio-data:/data
  command: server /data --console-address ":9001"
  restart: unless-stopped
```

新增 volume: `minio-data:`

### application-dev.yml

移除：
- `storage.root-path`
- `storage.thumbnail-subdir`
- `watch-service.debounce-ms`
- `watch-service.reconcile-interval-minutes`

新增：
```yaml
minio:
  endpoint: http://localhost:9000
  accessKey: minioadmin
  secretKey: minioadmin
  bucketName: allahpan-files
  thumbnailBucket: allahpan-thumbnails
  trashBucket: allahpan-trash
```

## 改动清单

### 删除（4 个文件）
- `LocalStorageService.java` + `LocalStorageServiceImpl.java`
- `LocalStorageConfig.java`
- `FileSystemWatcher.java`
- `StorageKeyMigration.java`

### 新增（2 个文件）
- `MinioUtil.java` — MinIO SDK 封装（putObject, getObject, removeObject, copyObject, getObjectInfo）
- `MinioConfig.java` — MinIO Client Bean

### 修改（7 个文件）
- `FileServiceImpl.java` — 所有存储操作改为 MinioUtil，移除 FileSystemWatcher/LocalStorageService 依赖
- `FileController.java` — 移除 FileSystemWatcher 依赖，SSE 事件在业务操作点推送
- `ThumbnailGenerator.java` — 输入源、输出去向改为 MinIO 流
- `TextExtractor.java` — 输入源改为 MinIO 流
- `TrashCleanupTask.java` — 清理逻辑改为 MinIO deleteObject
- `docker-compose.yml` — 添加 MinIO 服务
- `application-dev.yml` — 替换存储配置

### 不变
- `FileProcessSender.java` / `FileProcessReceiver.java` — RabbitMQ 管线
- `EsIndexServiceImpl.java` — ES 索引同步
- `OllamaService.java` — AI OCR
- `RabbitMqConfig.java` — 队列拓扑
- `FileProcessMessage.java` — 消息实体
- 认证/安全/收藏/分享全部模块
- 前端全部代码

## 验证

1. `docker-compose up -d` — MinIO 容器启动，3 个 bucket 自动创建
2. 上传文件 → 检查 MinIO Console (localhost:9001) 中 allahpan-files bucket 有对象
3. 下载文件 → 浏览器正常下载
4. 缩略图 → 检查 allahpan-thumbnails bucket 有缩略图对象
5. 文本提取 → DB 中 origin_text 有内容
6. ES 搜索 → 搜索到刚上传的文件
7. 删除 → 对象出现在 allahpan-trash bucket
8. 恢复 → 对象回到 allahpan-files
9. 永久删除 → 对象从 trash bucket 消失
10. `mvn test -pl allahpan-core` — 核心测试通过
