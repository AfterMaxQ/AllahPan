# 015 — MinIO 主存储 + 本地文件夹镜像（混合架构）

**日期:** 2026-06-09

## 背景

AllahPan 最初使用 MinIO 对象存储，后因用户需求改为纯本地文件系统，最终采用**混合架构**：MinIO 作为权威数据源 + 本地文件夹作为热缓存镜像。

## 架构

```
上传（浏览器）──presigned PUT──> MinIO ──confirm──> DB
                              └──LocalSyncService(异步)──> 本地文件夹

本地新文件 ──WatchService──> 上传 MinIO ──> DB 记录

下载/预览 ──优先读本地──> 本地有 → FileSystemResource（零延迟）
           └──本地无 → MinIO presigned GET（保底）

缩略图 ──本地 .thumbnails/ ──> GET /api/file/{id}/thumbnail
        └──降级 MinIO thumbnail bucket presigned URL
```

## 关键组件

| 组件 | 职责 |
|------|------|
| `MinioUtil` | 预签名 URL 生成、对象上传/下载/删除 |
| `LocalStorageService` | 本地文件 I/O（路径解析、读写、删除） |
| `LocalSyncService` | MinIO ↔ 本地双向同步桥接 |
| `FileSystemWatcher` | WatchService 监听 + DB 同步 + SSE 推送 |
| `FileController` | 所有文件 API（upload、confirm、download、stream、thumbnail、watch） |

## 存储模型

- **`storageKey`** = MinIO object key（格式: `1/yyyy/MM/{UUID}.ext`），权威标识符
- **本地路径** = 从 DB parent chain 计算（`folderA/folderB/file.txt`），方便人类浏览
- 两者解耦：MinIO key 是 UUID，本地路径是树状结构

## 上传（3 步 MinIO 预签名流程）

1. **pre-upload**: 计算 MD5 → 秒传检测 → 生成 MinIO key + 预签名 PUT URL
2. **浏览器直传**: `fetch(PUT, presignedUrl, fileBody)` — 不经过后端，不占 JVM 内存
3. **confirm-upload**: 创建 DB 记录 → 触发 RabbitMQ 管线 → 异步镜像到本地文件夹

## 本地同步（2 条路径）

**路径 A — 上传后同步（MinIO → 本地）**:
`LocalSyncService.mirrorMinioToLocal()` 在 confirm 后异步执行，从 MinIO 下载对象并写入本地文件夹对应路径。

**路径 B — 本地变更上传（本地 → MinIO）**:
`FileSystemWatcher` 检测到新文件 → `LocalSyncService.uploadLocalToMinio()` → 创建 DB 记录。

## 下载/预览策略

所有读操作**本地优先**：
- `GET /{id}/download` — 本地有则 FileSystemResource 流式传输；无则返回 MinIO presigned URL
- `GET /{id}/stream` — 同上（inline Content-Disposition）
- `GET /{id}/thumbnail` — 本地有则 FileSystemResource；无则 302 重定向到 MinIO

## SSE 实时推送

- 端点: `GET /api/file/watch?token={jwt}`
- 事件: `file-created`, `file-deleted`, `sync-complete`
- 前端: `useFileWatcher.js` 自动连接 + 重连

## 配置

```yaml
minio:
  endpoint: http://localhost:9000
  accessKey: minioadmin
  secretKey: minioadmin
  bucketName: allahpan-files
  thumbnailBucket: allahpan-thumbnails
  preSignExpiry: 300

allahpan:
  storage:
    root-path: ${ALLAHPAN_ROOT:C:/Users/ray/AllahPan}
    thumbnail-subdir: .thumbnails
  watch:
    debounce-ms: 1000
    reconcile-interval-minutes: 5
```

## 相关文件

- `MinioUtil.java` — MinIO SDK 封装
- `MinioConfig.java` — MinIO Client Bean 配置
- `LocalStorageService.java` + impl — 本地文件 I/O
- `LocalSyncService.java` — MinIO ↔ 本地双向同步
- `FileSystemWatcher.java` — WatchService + DB 同步 + SSE
- `FileController.java` — REST API
- `useFileWatcher.js` — 前端 SSE composable
