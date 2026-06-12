# MinIO 纯对象存储迁移 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将存储底座从本地文件系统迁移到 MinIO 对象存储，MinIO 作为唯一权威数据源。

**Architecture:** 替换 LocalStorageService → MinioUtil（封装 MinIO SDK），删除 FileSystemWatcher/LocalStorageConfig/StorageKeyMigration，SSE 事件改为在业务操作点直接推送，RabbitMQ 管线拓扑不变。

**Tech Stack:** Java 17, Spring Boot 3.5.14, MinIO SDK 8.5.10, MyBatis 3.5, RabbitMQ 3.12

**依赖链:**
```
Task 1 (Infrastructure) + Task 2 (MinioUtil/Config)  ← 并行
    ↓
Task 3 (删除旧组件) + Task 4 (FileServiceImpl) + Task 6 (ThumbnailGenerator/TextExtractor/OllamaService)  ← 并行(依赖1+2)
    ↓
Task 5 (FileController) ← 依赖 2+3+4
Task 7 (TrashCleanupTask) ← 依赖 4
    ↓
Task 8 (验证编译+测试)
```

---

### Task 1: 基础设施配置（docker-compose + pom.xml + application-dev.yml）

**Files:**
- Modify: `allahpan-core/pom.xml`
- Modify: `allahpan-core/src/main/resources/application-dev.yml`
- Modify: `docker-compose.yml`

- [ ] **Step 1: 添加 MinIO SDK 依赖到 pom.xml**

在 `allahpan-core/pom.xml` 的 `<dependencies>` 末尾新增：
```xml
<!-- MinIO Object Storage -->
<dependency>
    <groupId>io.minio</groupId>
    <artifactId>minio</artifactId>
    <version>8.5.10</version>
</dependency>
```

- [ ] **Step 2: 更新 docker-compose.yml 添加 MinIO 服务**

在 `services:` 下新增（在 elasticsearch 之后）：
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

在 `volumes:` 下新增：
```yaml
  minio-data:
```

- [ ] **Step 3: 更新 application-dev.yml**

移除以下配置块：
```yaml
# 移除: allahpan.storage.* (root-path, thumbnail-subdir)
# 移除: allahpan.watch.* (debounce-ms, reconcile-interval-minutes)
```

新增 MinIO 配置（与其他 `allahpan.*` 配置并列）：
```yaml
minio:
  endpoint: http://localhost:9000
  accessKey: minioadmin
  secretKey: minioadmin
  bucketName: allahpan-files
  thumbnailBucket: allahpan-thumbnails
  trashBucket: allahpan-trash
```

- [ ] **Step 4: 重启 Docker 基础设施**

```bash
docker-compose down
docker-compose up -d
```

验证：
```bash
docker ps --filter "name=minio"
curl -s http://localhost:9000/minio/health/live
# 期望: 200 OK
```

- [ ] **Step 5: Commit**

```bash
git add allahpan-core/pom.xml docker-compose.yml allahpan-core/src/main/resources/application-dev.yml
git commit -m "chore: add MinIO dependency, config, and docker-compose service

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: MinioUtil + MinioConfig（新增文件）

**Files:**
- Create: `allahpan-core/src/main/java/com/allahpan/component/MinioConfig.java`
- Create: `allahpan-core/src/main/java/com/allahpan/component/MinioUtil.java`

- [ ] **Step 1: 创建 MinioConfig**

`allahpan-core/src/main/java/com/allahpan/component/MinioConfig.java`：

```java
package com.allahpan.component;

import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MinioConfig {

    @Value("${minio.endpoint}")
    private String endpoint;

    @Value("${minio.accessKey}")
    private String accessKey;

    @Value("${minio.secretKey}")
    private String secretKey;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }
}
```

- [ ] **Step 2: 创建 MinioUtil**

`allahpan-core/src/main/java/com/allahpan/component/MinioUtil.java`：

```java
package com.allahpan.component;

import io.minio.*;
import io.minio.errors.MinioException;
import io.minio.http.Method;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.util.concurrent.TimeUnit;

@Component
public class MinioUtil {

    private static final Logger log = LoggerFactory.getLogger(MinioUtil.class);

    @Autowired
    private MinioClient minioClient;

    @Value("${minio.bucketName}")
    private String bucketName;

    @Value("${minio.thumbnailBucket}")
    private String thumbnailBucket;

    @Value("${minio.trashBucket}")
    private String trashBucket;

    @PostConstruct
    public void init() {
        // 确保 3 个 bucket 存在
        for (String bucket : new String[]{bucketName, thumbnailBucket, trashBucket}) {
            try {
                boolean found = minioClient.bucketExists(
                        BucketExistsArgs.builder().bucket(bucket).build());
                if (!found) {
                    minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
                    log.info("MinIO bucket created: {}", bucket);
                }
            } catch (Exception e) {
                log.error("Failed to check/create MinIO bucket: {}", bucket, e);
                throw new RuntimeException("MinIO bucket initialization failed: " + bucket, e);
            }
        }
        log.info("MinIO storage ready: files={}, thumbnails={}, trash={}",
                bucketName, thumbnailBucket, trashBucket);
    }

    /** 上传对象到 files bucket */
    public void putObject(String objectKey, InputStream data, long size, String contentType)
            throws Exception {
        minioClient.putObject(
                PutObjectArgs.builder()
                        .bucket(bucketName)
                        .object(objectKey)
                        .stream(data, size, -1)
                        .contentType(contentType)
                        .build()
        );
    }

    /** 上传对象到 thumbnail bucket */
    public void putThumbnail(String objectKey, InputStream data, long size, String contentType)
            throws Exception {
        minioClient.putObject(
                PutObjectArgs.builder()
                        .bucket(thumbnailBucket)
                        .object(objectKey)
                        .stream(data, size, -1)
                        .contentType(contentType)
                        .build()
        );
    }

    /** 从 files bucket 下载对象 */
    public InputStream getObject(String objectKey) throws Exception {
        return minioClient.getObject(
                GetObjectArgs.builder()
                        .bucket(bucketName)
                        .object(objectKey)
                        .build()
        );
    }

    /** 从 thumbnail bucket 下载对象 */
    public InputStream getThumbnail(String objectKey) throws Exception {
        return minioClient.getObject(
                GetObjectArgs.builder()
                        .bucket(thumbnailBucket)
                        .object(objectKey)
                        .build()
        );
    }

    /** 获取对象信息（大小、类型等） */
    public StatObjectResponse statObject(String objectKey) throws Exception {
        return minioClient.statObject(
                StatObjectArgs.builder()
                        .bucket(bucketName)
                        .object(objectKey)
                        .build()
        );
    }

    /** 检查对象是否存在（files bucket） */
    public boolean objectExists(String objectKey) {
        try {
            statObject(objectKey);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /** 从 files bucket 删除对象 */
    public void removeObject(String objectKey) throws Exception {
        minioClient.removeObject(
                RemoveObjectArgs.builder()
                        .bucket(bucketName)
                        .object(objectKey)
                        .build()
        );
    }

    /** 从 thumbnail bucket 删除对象 */
    public void removeThumbnail(String objectKey) throws Exception {
        minioClient.removeObject(
                RemoveObjectArgs.builder()
                        .bucket(thumbnailBucket)
                        .object(objectKey)
                        .build()
        );
    }

    /** 跨 bucket 复制：文件 → 回收站 */
    public void copyToTrash(String objectKey) throws Exception {
        minioClient.copyObject(
                CopyObjectArgs.builder()
                        .source(CopySource.builder()
                                .bucket(bucketName)
                                .object(objectKey)
                                .build())
                        .bucket(trashBucket)
                        .object(objectKey)
                        .build()
        );
    }

    /** 跨 bucket 复制：回收站 → 文件 */
    public void restoreFromTrash(String objectKey) throws Exception {
        minioClient.copyObject(
                CopyObjectArgs.builder()
                        .source(CopySource.builder()
                                .bucket(trashBucket)
                                .object(objectKey)
                                .build())
                        .bucket(bucketName)
                        .object(objectKey)
                        .build()
        );
    }

    /** 从 trash bucket 删除对象 */
    public void removeFromTrash(String objectKey) throws Exception {
        minioClient.removeObject(
                RemoveObjectArgs.builder()
                        .bucket(trashBucket)
                        .object(objectKey)
                        .build()
        );
    }

    public String getBucketName() { return bucketName; }
    public String getThumbnailBucket() { return thumbnailBucket; }
    public String getTrashBucket() { return trashBucket; }
}
```

- [ ] **Step 3: 验证编译**

```bash
mvn compile -pl allahpan-core -DskipTests
```

期望：BUILD SUCCESS（会有未使用的 import 警告，后续任务逐一消除）

- [ ] **Step 4: Commit**

```bash
git add allahpan-core/src/main/java/com/allahpan/component/MinioConfig.java allahpan-core/src/main/java/com/allahpan/component/MinioUtil.java
git commit -m "feat: add MinioUtil and MinioConfig for MinIO object storage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 删除废弃组件

**Files:**
- Delete: `allahpan-core/src/main/java/com/allahpan/service/LocalStorageService.java`
- Delete: `allahpan-core/src/main/java/com/allahpan/service/impl/LocalStorageServiceImpl.java`
- Delete: `allahpan-core/src/main/java/com/allahpan/config/LocalStorageConfig.java`
- Delete: `allahpan-core/src/main/java/com/allahpan/component/FileSystemWatcher.java`
- Delete: `allahpan-core/src/main/java/com/allahpan/component/StorageKeyMigration.java`

- [ ] **Step 1: 删除文件**

```bash
rm allahpan-core/src/main/java/com/allahpan/service/LocalStorageService.java
rm allahpan-core/src/main/java/com/allahpan/service/impl/LocalStorageServiceImpl.java
rm allahpan-core/src/main/java/com/allahpan/config/LocalStorageConfig.java
rm allahpan-core/src/main/java/com/allahpan/component/FileSystemWatcher.java
rm allahpan-core/src/main/java/com/allahpan/component/StorageKeyMigration.java
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "refactor: remove local storage components (pre-MinIO migration)

Delete LocalStorageService, LocalStorageServiceImpl, LocalStorageConfig,
FileSystemWatcher, and StorageKeyMigration. These will be replaced by
MinIO object storage (MinioUtil + MinioConfig).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

注意：此时编译会失败（其他文件引用已删除的类），后续任务逐一修复。

---

### Task 4: 改造 FileServiceImpl（存储操作全部切换为 MinioUtil）

**Files:**
- Modify: `allahpan-core/src/main/java/com/allahpan/service/impl/FileServiceImpl.java`
- Modify: `allahpan-core/src/main/java/com/allahpan/service/FileService.java`（查看接口定义）

**核心改动点：**
1. 移除 `@Autowired LocalStorageService localStorageService`
2. 注入 `@Autowired MinioUtil minioUtil`
3. 移除 `@Autowired FileSystemWatcher fileSystemWatcher`（如果有）
4. `storeAndCalculateMd5` → 流式上传到 MinIO 同时计算 MD5
5. 秒传 → `minioUtil.removeObject()` 替代 `localStorageService.delete()`
6. `createFolder` → 如果之前在本地创建文件夹，改为 minioUtil 创建占位对象或 DB only
7. `moveToTrash` → `minioUtil.copyToTrash()` + `minioUtil.removeObject()`
8. `restoreFromTrash` → `minioUtil.restoreFromTrash()` + `minioUtil.removeFromTrash()`
9. `permanentDelete` → `minioUtil.removeFromTrash()` + `minioUtil.removeThumbnail()`
10. `resolveConflict` → `minioUtil.objectExists()` 替代 `Files.exists()`
11. `deleteFile`(软删除) → MinIO 跨 bucket 复制+删除
12. `renameFile` → `minioUtil.copyObject` + `minioUtil.removeObject`（无原生 rename）
13. `moveFile` → `minioUtil.copyObject` + `minioUtil.removeObject`
14. `cleanupOrphanedTrash` → 改为 `minioUtil.statObject()`
15. `listTrash` → 检查 MinIO trash bucket 状态
16. 移除所有 `java.nio.file.*` import

**关键代码片段：**

```java
// 替换 storeAndCalculateMd5
private String storeAndCalculateMd5(InputStream inputStream, String objectKey) throws Exception {
    MessageDigest digest = MessageDigest.getInstance("MD5");
    // 将流读入 byte[] 以计算 MD5 (大文件需考虑内存)
    byte[] data = inputStream.readAllBytes();
    digest.update(data);
    String md5 = bytesToHex(digest.digest());
    // 上传到 MinIO
    try (InputStream uploadStream = new java.io.ByteArrayInputStream(data)) {
        minioUtil.putObject(objectKey, uploadStream, data.length, "application/octet-stream");
    }
    return md5;
}
```

```java
// 修改 resolveConflict
private String resolveConflict(String relativePath, Long parentId) {
    String base = relativePath;
    int counter = 1;
    while (minioUtil.objectExists(relativePath)) {
        // 同名冲突，加序号
        String name = base.substring(base.lastIndexOf('/') + 1);
        String parent = base.substring(0, base.lastIndexOf('/'));
        String newName = name + " (" + counter + ")";
        relativePath = parent + "/" + newName;
        counter++;
    }
    return relativePath;
}
```

```java
// 软删除改为 MinIO 操作
try {
    minioUtil.copyToTrash(storageKey);
    minioUtil.removeObject(storageKey);
} catch (Exception e) {
    log.error("MinIO trash move failed: {}", storageKey, e);
    Asserts.fail("删除文件失败");
}
```

```java
// 永久删除
try {
    minioUtil.removeFromTrash(storageKey);
    if (thumbnailKey != null && !thumbnailKey.isEmpty()) {
        minioUtil.removeThumbnail(thumbnailKey);
    }
} catch (Exception e) {
    log.error("MinIO permanent delete failed: {}", storageKey, e);
}
```

- [ ] **Step 1: 修改 FileServiceImpl — 依赖和 import**

移除 `import com.allahpan.service.LocalStorageService` 和 `import com.allahpan.component.FileSystemWatcher` 以及所有 `java.nio.file.*` import。
新增 `import com.allahpan.component.MinioUtil`。

替换字段：
```java
@Autowired
private MinioUtil minioUtil;
// 删除: @Autowired private LocalStorageService localStorageService;
// 删除: @Autowired private FileSystemWatcher fileSystemWatcher;
```

- [ ] **Step 2: 重写 storeAndCalculateMd5**

见上方代码片段。

- [ ] **Step 3: 修改 upload() 方法的秒传路径**

将 `localStorageService.delete(relativePath)` 改为 `minioUtil.removeObject(storageKey)`。

- [ ] **Step 4: 修改 deleteFile()（软删除）**

将 `localStorageService.moveToTrash()` 改为 MinIO 跨 bucket 复制+删除。

- [ ] **Step 5: 修改 permanentDelete()**

将 `localStorageService.deleteFromTrash()` + `localStorageService.deleteThumbnail()` 改为 MinIO 删除操作。

- [ ] **Step 6: 修改 renameFile()**

将 `Files.move()` 改为 `minioUtil.copyObject()` + `minioUtil.removeObject()`。

- [ ] **Step 7: 修改 moveFile()**

同上。

- [ ] **Step 8: 修改 resolveConflict()**

见上方代码片段。

- [ ] **Step 9: 修改 createFolder()**

如果原来有 `Files.createDirectories()`，移除。MinIO 中文件夹为逻辑概念（DB 记录即可）。如果使用占位对象，创建一个 0 字节对象。

- [ ] **Step 10: 修改 cleanupOrphanedTrash()**

将 `Files.exists()` 改为 `minioUtil.objectExists()` 或扫描 trash bucket。

- [ ] **Step 11: Commit**

```bash
git add allahpan-core/src/main/java/com/allahpan/service/impl/FileServiceImpl.java
git commit -m "refactor: switch FileServiceImpl from local storage to MinIO

Replace all LocalStorageService calls with MinioUtil equivalents.
Upload streams directly to MinIO, download from MinIO, trash moves
across buckets, rename/move via copy+delete.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 改造 FileController（SSE + download/stream/thumbnail）

**Files:**
- Modify: `allahpan-core/src/main/java/com/allahpan/controller/FileController.java`

**核心改动点：**
1. 移除 `@Autowired LocalStorageService localStorageService`
2. 移除 `@Autowired FileSystemWatcher fileSystemWatcher`
3. 注入 `@Autowired MinioUtil minioUtil`
4. `downloadFile()` — `FileSystemResource(localPath)` → `InputStreamResource(minioUtil.getObject(key))`
5. `streamFile()` — 同上
6. `getThumbnail()` — `FileSystemResource(thumbPath)` → `InputStreamResource(minioUtil.getThumbnail(key))`
7. `watchFiles()` (SSE) — 将 SSE emitter 管理逻辑从 FileSystemWatcher 搬到这里。添加 `List<SseEmitter> emitters = new CopyOnWriteArrayList<>()`，实现 `subscribe()` 和 `notifyAll()` 方法。
8. `upload()` — 成功后调用 `notifySse(...)` 推送 `file-created`
9. `deleteFile()` / `batchDelete()` — 成功后推送 `file-deleted`
10. 添加一个公开方法 `notifyStatusChange(File file)` 供 `FileProcessReceiver` 调用（替代原来调 `fileSystemWatcher.notifyAll()`）

**SSE 迁移关键：** 把 FileSystemWatcher 中的 `emitters`、`subscribe()`、`notifyAll()` 完整搬到 FileController，去掉 WatchService 相关代码。

```java
// FileController 新增 SSE 支持
private final List<SseEmitter> emitters = new java.util.concurrent.CopyOnWriteArrayList<>();

public SseEmitter subscribe() {
    SseEmitter emitter = new SseEmitter(30 * 60 * 1000L); // 30min timeout
    emitters.add(emitter);
    emitter.onCompletion(() -> emitters.remove(emitter));
    emitter.onTimeout(() -> emitters.remove(emitter));
    emitter.onError(e -> emitters.remove(emitter));
    try {
        emitter.send(SseEmitter.event().name("connected").data("ok"));
    } catch (Exception ignored) {}
    return emitter;
}

public void notifySse(String eventType, Object data) {
    for (SseEmitter emitter : emitters) {
        try {
            emitter.send(SseEmitter.event().name(eventType).data(data));
        } catch (Exception e) {
            emitters.remove(emitter);
        }
    }
}
```

- [ ] **Step 1: 修改 FileController imports 和依赖注入**

移除 `import com.allahpan.component.FileSystemWatcher`、`import com.allahpan.service.LocalStorageService`、`import java.nio.file.*`、`import org.springframework.core.io.FileSystemResource`。
新增 `import com.allahpan.component.MinioUtil`、`import org.springframework.core.io.InputStreamResource`。

替换注入：
```java
@Autowired
private MinioUtil minioUtil;
// 删除: @Autowired private LocalStorageService localStorageService;
// 删除: @Autowired private FileSystemWatcher fileSystemWatcher;
```

- [ ] **Step 2: 添加 SSE emitter 管理**

见上方代码片段。

- [ ] **Step 3: 修改 downloadFile()**

```java
@GetMapping("/{fileId}/download")
public ResponseEntity<Resource> downloadFile(@PathVariable Long fileId) {
    File file = fileService.getById(fileId);
    try {
        InputStream stream = minioUtil.getObject(file.getStorageKey());
        InputStreamResource resource = new InputStreamResource(stream);
        String encodedName = URLEncoder.encode(file.getFileName(), StandardCharsets.UTF_8)
                .replaceAll("\\+", "%20");
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(
                        file.getContentType() != null ? file.getContentType() : "application/octet-stream"))
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename*=UTF-8''" + encodedName)
                .body(resource);
    } catch (Exception e) {
        log.error("Download failed: {}", file.getStorageKey(), e);
        Asserts.fail("文件下载失败");
        return null;
    }
}
```

- [ ] **Step 4: 修改 streamFile()**

同 downloadFile，`Content-Disposition: inline`。

- [ ] **Step 5: 修改 getThumbnail()**

```java
@GetMapping("/{fileId}/thumbnail")
public ResponseEntity<Resource> getThumbnail(@PathVariable Long fileId) {
    File file = fileService.getById(fileId);
    if (file.getThumbnailKey() == null || file.getThumbnailKey().isEmpty()) {
        return ResponseEntity.notFound().build();
    }
    try {
        InputStream stream = minioUtil.getThumbnail(file.getThumbnailKey());
        InputStreamResource resource = new InputStreamResource(stream);
        return ResponseEntity.ok()
                .contentType(MediaType.IMAGE_JPEG)
                .body(resource);
    } catch (Exception e) {
        log.error("Thumbnail failed: {}", file.getThumbnailKey(), e);
        return ResponseEntity.notFound().build();
    }
}
```

- [ ] **Step 6: 修改 upload() 添加 SSE 推送**

在 `fileService.upload()` 成功后：
```java
Map<String, Object> respData = toFileResponse(saved);
notifySse("file-created", Map.of("fileId", saved.getId(), "parentId", saved.getParentId()));
```

- [ ] **Step 7: 修改 watchFiles() (SSE 端点)**

```java
@GetMapping("/watch")
public SseEmitter watchFiles(@RequestParam(defaultValue = "") String token) {
    // Token 校验（如果 jwtTokenUtil 有 validate 方法）
    // ...
    return subscribe();
}
```

- [ ] **Step 8: Commit**

```bash
git add allahpan-core/src/main/java/com/allahpan/controller/FileController.java
git commit -m "refactor: switch FileController from local filesystem to MinIO

Replace FileSystemResource with InputStreamResource from MinioUtil.
Move SSE emitter management from deleted FileSystemWatcher to
FileController. Push file-created/file-deleted events at business
operation points instead of watching filesystem events.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 改造处理组件（ThumbnailGenerator + TextExtractor + OllamaService）

**Files:**
- Modify: `allahpan-core/src/main/java/com/allahpan/component/ThumbnailGenerator.java`
- Modify: `allahpan-core/src/main/java/com/allahpan/component/TextExtractor.java`
- Modify: `allahpan-core/src/main/java/com/allahpan/component/OllamaService.java`
- Modify: `allahpan-core/src/main/java/com/allahpan/component/FileProcessReceiver.java`

- [ ] **Step 1: 修改 ThumbnailGenerator — imports 和依赖**

移除 `import com.allahpan.service.LocalStorageService`。
新增 `import com.allahpan.component.MinioUtil`。

替换字段：
```java
@Autowired
private MinioUtil minioUtil;
// 删除: @Autowired private LocalStorageService localStorageService;
```

- [ ] **Step 2: ThumbnailGenerator — 修改 generateImageThumbnail**

改为从 MinIO 读取：
```java
private String generateImageThumbnail(File file) throws Exception {
    InputStream is = minioUtil.getObject(file.getStorageKey());
    BufferedImage original = ImageIO.read(is);
    is.close();
    if (original == null) return null;
    return resizeAndUpload(original);
}
```

- [ ] **Step 3: ThumbnailGenerator — 修改 generatePdfThumbnail**

```java
private String generatePdfThumbnail(File file) throws Exception {
    InputStream is = minioUtil.getObject(file.getStorageKey());
    byte[] pdfBytes = is.readAllBytes();
    is.close();
    try (PDDocument document = Loader.loadPDF(pdfBytes)) {
        PDFRenderer renderer = new PDFRenderer(document);
        BufferedImage image = renderer.renderImageWithDPI(0, pdfThumbnailDpi);
        return resizeAndUpload(image);
    }
}
```

- [ ] **Step 4: ThumbnailGenerator — 修改 resizeAndUpload**

```java
private String resizeAndUpload(BufferedImage original) throws Exception {
    int width = THUMB_WIDTH;
    int height = original.getHeight() * width / original.getWidth();
    BufferedImage thumb = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
    Graphics2D g = thumb.createGraphics();
    g.drawImage(original.getScaledInstance(width, height, java.awt.Image.SCALE_SMOOTH), 0, 0, null);
    g.dispose();

    String thumbnailKey = java.util.UUID.randomUUID().toString() + ".jpg";

    ByteArrayOutputStream baos = new ByteArrayOutputStream();
    ImageIO.write(thumb, "jpg", baos);
    byte[] bytes = baos.toByteArray();

    try (InputStream uploadStream = new ByteArrayInputStream(bytes)) {
        minioUtil.putThumbnail(thumbnailKey, uploadStream, bytes.length, "image/jpeg");
    }

    return thumbnailKey;
}
```

- [ ] **Step 5: 修改 TextExtractor — readFromLocal**

```java
private byte[] readFromMinio(File file) throws Exception {
    try (InputStream is = minioUtil.getObject(file.getStorageKey())) {
        return is.readAllBytes();
    }
}
```

方法重命名 + 替换：`readFromLocal` → `readFromMinio`，所有 8 个 `extract*` 方法内部调用改为 `readFromMinio(file)`。

移除 `@Autowired LocalStorageService localStorageService`，新增 `@Autowired MinioUtil minioUtil`。

- [ ] **Step 6: 修改 OllamaService — ocr() 方法**

```java
public String ocr(File file) {
    try (InputStream is = minioUtil.getObject(file.getStorageKey())) {
        byte[] imageBytes = is.readAllBytes();
        // base64 编码等后续逻辑不变
        String base64 = java.util.Base64.getEncoder().encodeToString(imageBytes);
        // ... 调用 Ollama API
    } catch (Exception e) {
        log.error("OCR read failed: {}", file.getStorageKey(), e);
        return null;
    }
}
```

移除 `@Autowired LocalStorageService localStorageService`，新增 `@Autowired MinioUtil minioUtil`。

- [ ] **Step 7: 修改 FileProcessReceiver — SSE 通知路径**

将 `fileSystemWatcher.notifyAll(...)` 改为 `fileController.notifySse(...)`。

```java
@Autowired
private FileController fileController;

// 在 notifyStatusChange 方法中:
fileController.notifySse("file-updated", dataMap);
```

移除 `@Autowired FileSystemWatcher fileSystemWatcher`。

- [ ] **Step 8: Commit**

```bash
git add allahpan-core/src/main/java/com/allahpan/component/ThumbnailGenerator.java \
    allahpan-core/src/main/java/com/allahpan/component/TextExtractor.java \
    allahpan-core/src/main/java/com/allahpan/component/OllamaService.java \
    allahpan-core/src/main/java/com/allahpan/component/FileProcessReceiver.java
git commit -m "refactor: switch processing components to read/write via MinIO

ThumbnailGenerator: read from MinIO, write thumbnail to thumbnail bucket.
TextExtractor: read from MinIO instead of local file.
OllamaService: read image bytes from MinIO.
FileProcessReceiver: push SSE via FileController instead of deleted
FileSystemWatcher.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: 改造 TrashCleanupTask

**Files:**
- Modify: `allahpan-core/src/main/java/com/allahpan/task/TrashCleanupTask.java`

**改动点：** 定时清理逻辑本身不变，但它依赖 `FileService.permanentDelete()`，而后者的实现已改为 MinIO 操作。只需确认不再有本地文件系统引用残留。

- [ ] **Step 1: 检查并清理 TrashCleanupTask**

确认 `TrashCleanupTask` 没有任何 `LocalStorageService`、`FileSystemWatcher`、`java.nio.file.*` 引用。如果有，移除。

如果原来直接用 `localStorageService`，全部改为通过 `FileService` 代理（`fileService.permanentDelete(fileId)`）。

- [ ] **Step 2: Commit**

```bash
git add allahpan-core/src/main/java/com/allahpan/task/TrashCleanupTask.java
git commit -m "refactor: clean up TrashCleanupTask local storage references

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: 编译验证 + 修复编译错误

**Files:**
- Any file with compilation errors

- [ ] **Step 1: 全量编译**

```bash
mvn compile -pl allahpan-core -DskipTests
```

- [ ] **Step 2: 修复编译错误**

逐一修复报错文件的残余 `LocalStorageService`、`FileSystemWatcher`、`LocalStorageConfig`、`java.nio.file.Path` 引用。

常见残留点：
- 其他 Service 类可能有 `@Autowired LocalStorageService`
- 测试类可能有 `LocalStorageService` 引用
- `GlobalExceptionHandler` 或其他 Controller 可能有 `FileSystemWatcher` 引用
- `StorageKeyMigration` 引用（确认已删除）

- [ ] **Step 3: 确认编译通过**

```bash
mvn compile -pl allahpan-core -DskipTests
# 期望: BUILD SUCCESS
```

- [ ] **Step 4: 运行测试**

```bash
mvn test -pl allahpan-core
```

修复测试中可能引用旧组件的代码（如 mock `LocalStorageService` → mock `MinioUtil`）。

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "fix: resolve compilation errors from MinIO migration

Fix remaining references to deleted components in all files.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 确保所有 Docker 容器运行**

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# 期望: mysql-allahpan, redis-allahpan, rabbitmq, elasticsearch, minio 全部 Up
```

- [ ] **Step 2: 验证 MinIO bucket 自动创建**

启动 core 应用后检查日志：
```
MinIO bucket created: allahpan-files
MinIO bucket created: allahpan-thumbnails
MinIO bucket created: allahpan-trash
MinIO storage ready: files=..., thumbnails=..., trash=...
```

或直接检查 MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

- [ ] **Step 3: 启动服务**

```bash
# Terminal 1
cd allahpan-core && mvn spring-boot:run
# Terminal 2
cd allahpan-search && mvn spring-boot:run
# Terminal 3
cd allahpan-web && npm run dev
```

- [ ] **Step 4: 功能验证清单**

| # | 测试项 | 方法 | 预期 |
|---|--------|------|------|
| 1 | 上传图片 | 浏览器上传一张图片 | 成功，MinIO allahpan-files bucket 有新对象 |
| 2 | 缩略图 | 等待处理完成 | allahpan-thumbnails bucket 有缩略图，前端显示 |
| 3 | 搜索 | 搜索文件名 | ES 返回结果 |
| 4 | 下载 | 点击下载 | 文件正常下载 |
| 5 | 预览 | 点击预览 | 在线预览正常 |
| 6 | 删除 | 删除文件 | 对象出现在 allahpan-trash bucket |
| 7 | 恢复 | 从回收站恢复 | 对象回到 allahpan-files bucket |
| 8 | 永久删除 | 从回收站永久删除 | 对象从 trash bucket 消失 |

---

## 总体 Commit 序列

```
chore: add MinIO dependency, config, and docker-compose service
feat: add MinioUtil and MinioConfig for MinIO object storage
refactor: remove local storage components (pre-MinIO migration)
refactor: switch FileServiceImpl from local storage to MinIO
refactor: switch FileController from local filesystem to MinIO
refactor: switch processing components to read/write via MinIO
refactor: clean up TrashCleanupTask local storage references
fix: resolve compilation errors from MinIO migration
```
