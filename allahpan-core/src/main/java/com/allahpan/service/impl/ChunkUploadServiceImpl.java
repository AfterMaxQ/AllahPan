package com.allahpan.service.impl;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.log.StructuredLog;
import com.allahpan.common.log.LogContext;
import com.allahpan.common.service.RedisService;
import com.allahpan.component.FileProcessSender;
import com.allahpan.component.EsIndexService;
import com.allahpan.component.MinioUtil;
import com.allahpan.component.SseBroadcaster;
import com.allahpan.domain.FileProcessMessage;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.ChunkUploadService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Service
public class ChunkUploadServiceImpl implements ChunkUploadService {

    private static final Logger log = LoggerFactory.getLogger(ChunkUploadServiceImpl.class);
    private static final int MAX_FILE_NAME_LENGTH = 255;
    private static final int MAX_TOTAL_CHUNKS = 10_000;
    private static final int MAX_CHUNK_SIZE = 32 * 1024 * 1024;

    @Value("${allahpan.chunk.temp-dir:${java.io.tmpdir}/allahpan-chunks}")
    private String tempDir;

    @Value("${allahpan.chunk.expire-hours:24}")
    private int expireHours;

    @Value("${allahpan.chunk.max-file-size:53687091200}")
    private long maxFileSize;

    @Autowired
    private RedisService redisService;
    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileProcessSender fileProcessSender;
    @Autowired
    private EsIndexService esIndexService;
    @Autowired
    private SseBroadcaster sseBroadcaster;

    // ==================== Redis Key ====================

    private String hashKey(String uploadId) { return "chunk:upload:" + uploadId; }
    private String setKey(String uploadId) { return "chunk:upload:" + uploadId + ":chunks"; }
    private String lockKey(String uploadId) { return "chunk:upload:" + uploadId + ":complete-lock"; }
    private String resultKey(String uploadId) { return "chunk:upload:" + uploadId + ":result"; }

    // ==================== init ====================

    @Override
    public Map<String, Object> init(String fileName, long fileSize, String fileMd5,
                                    String contentType, Long parentId, int chunkSize, int totalChunks) {
        Long userId = getCurrentUserId();
        Long pid = parentId != null ? parentId : 0L;
        validateUploadRequest(fileName, fileSize, fileMd5, pid, chunkSize, totalChunks);
        String uploadId = computeUploadId(userId, fileMd5, fileSize, fileName, pid);
        String hk = hashKey(uploadId);

        Map<String, Object> completed = getCompletedResult(uploadId, userId);
        if (completed != null) {
            completed.put("uploadId", uploadId);
            completed.put("uploadedChunks", List.of());
            completed.put("status", "completed");
            return completed;
        }

        if (Boolean.TRUE.equals(redisService.hasKey(hk))) {
            Map<Object, Object> meta = redisService.hGetAll(hk);
            validateSessionOwner(meta, userId);
            validateResumeParams(meta, fileName, fileSize, fileMd5, pid, chunkSize, totalChunks);
            // 已有会话 → 返回已上传的分片列表
            Set<Object> uploaded = redisService.sMembers(setKey(uploadId));
            List<Integer> uploadedList = uploaded.stream()
                    .map(o -> Integer.parseInt(o.toString()))
                    .sorted()
                    .collect(Collectors.toList());
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("uploadId", uploadId);
            result.put("uploadedChunks", uploadedList);
            result.put("status", "resumed");
            return result;
        }

        // 新会话。先记录元数据，再检查是否可以真正秒传。
        redisService.hSet(hk, "fileName", fileName, expireHours * 3600L);
        redisService.hSet(hk, "fileSize", String.valueOf(fileSize));
        redisService.hSet(hk, "fileMd5", fileMd5);
        redisService.hSet(hk, "contentType", contentType != null ? contentType : "application/octet-stream");
        redisService.hSet(hk, "parentId", String.valueOf(pid));
        redisService.hSet(hk, "chunkSize", String.valueOf(chunkSize));
        redisService.hSet(hk, "totalChunks", String.valueOf(totalChunks));
        redisService.hSet(hk, "uploadedCount", "0");
        redisService.hSet(hk, "status", "uploading");
        redisService.hSet(hk, "userId", String.valueOf(userId));
        redisService.expire(hk, expireHours * 3600L);

        File existing = findActiveByMd5(fileMd5, fileSize);
        if (existing != null) {
            redisService.hSet(hk, "status", "instant");
            redisService.hSet(hk, "sourceFileId", String.valueOf(existing.getId()));
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("uploadId", uploadId);
            result.put("uploadedChunks", List.of());
            result.put("status", "instant");
            return result;
        }

        Path chunkDir = Path.of(tempDir, uploadId);
        try {
            Files.createDirectories(chunkDir);
            long usableSpace = Files.getFileStore(chunkDir).getUsableSpace();
            Asserts.isTrue(usableSpace > fileSize + Math.min(fileSize / 10, 1024L * 1024 * 1024),
                    "服务器临时空间不足，请稍后重试");
        } catch (IOException e) {
            log.error(StructuredLog.event("file.upload.chunk.init_failed",
                    "errorType", e.getClass().getSimpleName()), e);
            Asserts.fail("上传初始化失败");
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("uploadId", uploadId);
        result.put("uploadedChunks", List.of());
        result.put("status", "new");
        return result;
    }

    // ==================== uploadChunk ====================

    @Override
    public void uploadChunk(String uploadId, int chunkIndex, MultipartFile chunk) {
        String hk = hashKey(uploadId);
        Asserts.isTrue(Boolean.TRUE.equals(redisService.hasKey(hk)), "上传会话不存在或已过期");

        Map<Object, Object> meta = redisService.hGetAll(hk);
        validateSessionOwner(meta, getCurrentUserId());
        Asserts.isTrue(!"instant".equals(meta.get("status")), "该文件可秒传，无需上传分片");
        int totalChunks = Integer.parseInt((String) meta.get("totalChunks"));
        long fileSize = Long.parseLong((String) meta.get("fileSize"));
        int chunkSize = Integer.parseInt((String) meta.get("chunkSize"));
        Asserts.isTrue(chunkIndex >= 0 && chunkIndex < totalChunks, "分片序号无效");

        long expectedSize = chunkIndex == totalChunks - 1
                ? fileSize - (long) chunkIndex * chunkSize
                : chunkSize;
        Asserts.isTrue(chunk.getSize() == expectedSize,
                String.format("分片大小不匹配: %d/%d", chunk.getSize(), expectedSize));

        Path chunkDir = Path.of(tempDir, uploadId);
        Path chunkFile = Path.of(tempDir, uploadId, String.valueOf(chunkIndex));
        try {
            Files.createDirectories(chunkDir);
            chunk.transferTo(chunkFile);
        } catch (IOException e) {
            log.error(StructuredLog.event("file.upload.chunk.write_failed",
                    "errorType", e.getClass().getSimpleName()), e);
            Asserts.fail("分片保存失败");
        }

        redisService.sAdd(setKey(uploadId), String.valueOf(chunkIndex));
        redisService.expire(setKey(uploadId), expireHours * 3600L);

        // 刷新主 hash TTL
        redisService.expire(hk, expireHours * 3600L);
    }

    // ==================== complete ====================

    @Override
    public Map<String, Object> complete(String uploadId) {
        Long currentUserId = getCurrentUserId();
        Map<String, Object> completed = getCompletedResult(uploadId, currentUserId);
        if (completed != null) return completed;

        String hk = hashKey(uploadId);
        Asserts.isTrue(Boolean.TRUE.equals(redisService.hasKey(hk)), "上传会话不存在或已过期");
        Asserts.isTrue(Boolean.TRUE.equals(redisService.setIfAbsent(lockKey(uploadId), "1", 600)),
                "上传正在合并，请勿重复提交");

        completed = getCompletedResult(uploadId, currentUserId);
        if (completed != null) {
            redisService.del(lockKey(uploadId));
            return completed;
        }

        Map<Object, Object> meta = redisService.hGetAll(hk);
        validateSessionOwner(meta, currentUserId);
        String fileName = (String) meta.get("fileName");
        long fileSize = Long.parseLong((String) meta.get("fileSize"));
        String fileMd5 = (String) meta.get("fileMd5");
        String contentType = (String) meta.get("contentType");
        Long parentId = Long.parseLong((String) meta.get("parentId"));
        int totalChunks = Integer.parseInt((String) meta.get("totalChunks"));
        Long userId = Long.parseLong((String) meta.get("userId"));
        String status = String.valueOf(meta.get("status"));

        if ("instant".equals(status)) {
            try {
                Long sourceFileId = Long.parseLong(String.valueOf(meta.get("sourceFileId")));
                File existing = fileMapper.selectByPrimaryKey(sourceFileId);
                Asserts.isTrue(existing != null && existing.getDeleteTime() == null,
                        "秒传源文件已失效，请重新上传");
                File dup = createDuplicateRecord(existing, userId, parentId, fileName);
                fileMapper.insert(dup);
                Map<String, Object> result = cacheCompletedResult(uploadId, dup);
                cleanup(uploadId, Path.of(tempDir, uploadId));
                esIndexService.index(dup);
                broadcastCreated(dup);
                return result;
            } finally {
                redisService.del(lockKey(uploadId));
            }
        }

        // 验证所有分片已上传
        long uploadedCount = redisService.sMembers(setKey(uploadId)).size();
        Asserts.isTrue(uploadedCount == totalChunks,
                String.format("分片未完整上传 (%d/%d)", uploadedCount, totalChunks));

        Path chunkDir = Path.of(tempDir, uploadId);
        String storageKey = null;
        File insertedRecord = null;

        try {
            // 分片按序直接流入 MinIO，同时计算 MD5；不再生成一个等大的 merged 文件。
            String finalName = resolveAvailableName(parentId, fileName);
            storageKey = createObjectKey(finalName);
            String actualMd5 = storeChunksAndCalculateMd5(
                    chunkDir, totalChunks, storageKey, fileSize, contentType);
            Asserts.isTrue(fileMd5 == null || fileMd5.isBlank() || fileMd5.equalsIgnoreCase(actualMd5),
                    "文件校验失败，请重新上传");

            // 初始化后另一上传刚好先完成时，复用它的处理结果。
            if (!actualMd5.isEmpty()) {
                FileExample md5Example = new FileExample();
                md5Example.createCriteria().andMd5EqualTo(actualMd5).andIsFolderEqualTo((byte) 0)
                        .andDeleteTimeIsNull();
                var dupList = fileMapper.selectByExample(md5Example);
                if (!dupList.isEmpty()) {
                    File existing = dupList.get(0);
                    File dup = createDuplicateRecord(existing, userId, parentId, finalName);
                    // 本次对象已完整上传，保留独立 key。
                    dup.setStorageKey(storageKey);
                    fileMapper.insert(dup);
                    insertedRecord = dup;
                    Map<String, Object> result = cacheCompletedResult(uploadId, dup);
                    cleanup(uploadId, chunkDir);
                    esIndexService.index(dup);
                    broadcastCreated(dup);
                    return result;
                }
            }

            File record = new File();
            record.setUploaderId(userId);
            record.setParentId(parentId);
            record.setFileName(finalName);
            record.setStorageKey(storageKey);
            record.setFileSize(fileSize);
            record.setContentType(contentType);
            record.setMd5(actualMd5);
            record.setIsFolder((byte) 0);
            record.setProcessStatus((byte) 0);
            record.setFileType(detectFileType(contentType, finalName));
            record.setCreateTime(new Date());
            record.setFilePath(buildPath(finalName, parentId));
            fileMapper.insert(record);
            insertedRecord = record;

            Map<String, Object> result = cacheCompletedResult(uploadId, record);
            try {
                fileProcessSender.sendProcess(
                        new FileProcessMessage(record.getId(), FileProcessMessage.Stage.UPLOADED,
                                LogContext.requestId(), LogContext.ensureOperationId("upload")));
            } catch (Exception messageError) {
                // DB 与 MinIO 已一致，保留文件让 PendingFileProcessTask 补发，避免悬空记录。
                log.warn(StructuredLog.event("file.process.queue_failed", "fileId", record.getId(),
                        "errorType", messageError.getClass().getSimpleName()), messageError);
            }
            cleanup(uploadId, chunkDir);
            broadcastCreated(record);
            return result;

        } catch (Exception e) {
            log.error(StructuredLog.event("file.upload.failed", "mode", "chunked",
                    "errorType", e.getClass().getSimpleName()), e);
            if (insertedRecord == null && storageKey != null) {
                try { minioUtil.removeObject(storageKey); } catch (Exception ex) {
                    log.warn(StructuredLog.event("storage.rollback.failed",
                            "errorType", ex.getClass().getSimpleName()), ex);
                }
            }
            if (e instanceof RuntimeException runtimeException) {
                throw runtimeException;
            }
            Asserts.fail("文件处理失败，请重试");
            return null;
        } finally {
            redisService.del(lockKey(uploadId));
        }
    }

    // ==================== getStatus ====================

    @Override
    public Map<String, Object> getStatus(String uploadId) {
        String hk = hashKey(uploadId);
        Map<String, Object> completed = getCompletedResult(uploadId, getCurrentUserId());
        if (completed != null) {
            completed.put("uploadId", uploadId);
            completed.put("status", "completed");
            return completed;
        }
        Asserts.isTrue(Boolean.TRUE.equals(redisService.hasKey(hk)), "上传会话不存在或已过期");

        Map<Object, Object> meta = redisService.hGetAll(hk);
        validateSessionOwner(meta, getCurrentUserId());
        Set<Object> members = redisService.sMembers(setKey(uploadId));
        List<Integer> uploadedList = members.stream()
                .map(o -> Integer.parseInt(o.toString()))
                .sorted()
                .collect(Collectors.toList());

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("uploadId", uploadId);
        result.put("fileName", meta.get("fileName"));
        result.put("totalChunks", Integer.parseInt((String) meta.get("totalChunks")));
        result.put("uploadedCount", uploadedList.size());
        result.put("uploadedChunks", uploadedList);
        result.put("status", meta.get("status"));
        return result;
    }

    // ==================== Cleanup ====================

    @Scheduled(cron = "0 0 * * * ?") // 每小时执行
    public void cleanupExpiredChunks() {
        Path root = Path.of(tempDir);
        if (!Files.exists(root)) return;

        long expireMs = expireHours * 3600_000L;
        long now = System.currentTimeMillis();

        try (var dirs = Files.newDirectoryStream(root)) {
            for (Path dir : dirs) {
                if (!Files.isDirectory(dir)) continue;
                try {
                    BasicFileAttributes attrs = Files.readAttributes(dir, BasicFileAttributes.class);
                    if (now - attrs.lastModifiedTime().toMillis() > expireMs) {
                        deleteDir(dir);
                        log.debug(StructuredLog.event("file.upload.chunk.cleaned"));
                    }
                } catch (IOException e) {
                        log.warn(StructuredLog.event("file.upload.chunk.cleanup_skipped",
                                "errorType", e.getClass().getSimpleName()), e);
                }
            }
        } catch (IOException e) {
            log.warn(StructuredLog.event("file.upload.chunk.scan_failed",
                    "errorType", e.getClass().getSimpleName()), e);
        }
    }

    private void cleanup(String uploadId, Path chunkDir) {
        redisService.del(List.of(hashKey(uploadId), setKey(uploadId)));
        deleteDir(chunkDir);
    }

    private void deleteDir(Path dir) {
        try {
            if (Files.exists(dir)) {
                try (var files = Files.walk(dir)) {
                    files.sorted(java.util.Comparator.reverseOrder())
                            .forEach(p -> {
                                try { Files.deleteIfExists(p); } catch (IOException ignored) {}
                            });
                }
            }
        } catch (IOException e) {
            log.warn(StructuredLog.event("file.upload.chunk.cleanup_failed",
                    "errorType", e.getClass().getSimpleName()), e);
        }
    }

    // ==================== Helpers ====================

    private String computeUploadId(Long userId, String md5, long fileSize, String fileName, Long parentId) {
        String input = userId + ":" + md5 + ":" + fileSize + ":" + fileName + ":" + parentId;
        return UUID.nameUUIDFromBytes(input.getBytes(StandardCharsets.UTF_8)).toString();
    }

    private void validateUploadRequest(String fileName, long fileSize, String fileMd5,
                                       Long parentId, int chunkSize, int totalChunks) {
        Asserts.isTrue(fileName != null && !fileName.isBlank(), "文件名不能为空");
        Asserts.isTrue(fileName.length() <= MAX_FILE_NAME_LENGTH,
                "文件名过长（最大" + MAX_FILE_NAME_LENGTH + "字符）");
        Asserts.isTrue(fileSize > 0, "文件大小无效");
        Asserts.isTrue(fileSize <= maxFileSize, "文件超过服务器允许的最大大小");
        Asserts.isTrue(fileMd5 != null && !fileMd5.isBlank(), "文件 MD5 不能为空");
        Asserts.isTrue(chunkSize > 0 && chunkSize <= MAX_CHUNK_SIZE, "分片大小无效");
        Asserts.isTrue(totalChunks > 0 && totalChunks <= MAX_TOTAL_CHUNKS, "分片数量无效");
        long expectedChunks = (fileSize + chunkSize - 1) / chunkSize;
        Asserts.isTrue(expectedChunks == totalChunks, "分片数量与文件大小不匹配");
        validateParentFolder(parentId);
    }

    private void validateParentFolder(Long parentId) {
        if (parentId == null || parentId <= 0) return;
        File parent = fileMapper.selectByPrimaryKey(parentId);
        Asserts.isTrue(parent != null && parent.getIsFolder() != null && parent.getIsFolder() == 1,
                "父目录不存在或不是文件夹");
        Asserts.isTrue(parent.getDeleteTime() == null, "父目录已在垃圾站中");
    }

    private void validateSessionOwner(Map<Object, Object> meta, Long userId) {
        Object owner = meta.get("userId");
        Asserts.isTrue(owner != null && String.valueOf(userId).equals(String.valueOf(owner)),
                "无权访问该上传会话");
    }

    private void validateResumeParams(Map<Object, Object> meta, String fileName, long fileSize, String fileMd5,
                                      Long parentId, int chunkSize, int totalChunks) {
        Asserts.isTrue(Objects.equals(meta.get("fileName"), fileName)
                        && Objects.equals(meta.get("fileSize"), String.valueOf(fileSize))
                        && Objects.equals(meta.get("fileMd5"), fileMd5)
                        && Objects.equals(meta.get("parentId"), String.valueOf(parentId))
                        && Objects.equals(meta.get("chunkSize"), String.valueOf(chunkSize))
                        && Objects.equals(meta.get("totalChunks"), String.valueOf(totalChunks)),
                "上传会话参数不一致，请重新上传");
    }

    private String storeChunksAndCalculateMd5(Path chunkDir, int totalChunks, String objectKey,
                                              long fileSize, String contentType) throws Exception {
        for (int i = 0; i < totalChunks; i++) {
            Asserts.isTrue(Files.isRegularFile(chunkDir.resolve(String.valueOf(i))),
                    "缺少分片: " + i);
        }
        MessageDigest digest = MessageDigest.getInstance("MD5");
        try (InputStream in = new ChunkSequenceInputStream(chunkDir, totalChunks);
             DigestInputStream dis = new DigestInputStream(in, digest)) {
            minioUtil.putObject(objectKey, dis, fileSize, contentType);
        }
        return java.util.HexFormat.of().formatHex(digest.digest());
    }

    private File findActiveByMd5(String md5, long fileSize) {
        FileExample example = new FileExample();
        example.createCriteria().andMd5EqualTo(md5).andFileSizeEqualTo(fileSize)
                .andIsFolderEqualTo((byte) 0).andDeleteTimeIsNull();
        List<File> files = fileMapper.selectByExample(example);
        return files.isEmpty() ? null : files.get(0);
    }

    private File createDuplicateRecord(File existing, Long userId, Long parentId, String requestedName) {
        String finalName = resolveAvailableName(parentId, requestedName);
        File dup = new File();
        dup.setUploaderId(userId);
        dup.setParentId(parentId);
        dup.setFileName(finalName);
        dup.setStorageKey(existing.getStorageKey());
        dup.setFileSize(existing.getFileSize());
        dup.setContentType(existing.getContentType());
        dup.setMd5(existing.getMd5());
        dup.setFileType(existing.getFileType());
        dup.setThumbnailKey(existing.getThumbnailKey());
        dup.setPreviewKey(existing.getPreviewKey());
        dup.setOriginText(existing.getOriginText());
        dup.setIsFolder((byte) 0);
        dup.setProcessStatus((byte) 3);
        dup.setCreateTime(new Date());
        dup.setFilePath(buildPath(finalName, parentId));
        return dup;
    }

    private String resolveAvailableName(Long parentId, String requestedName) {
        if (!activeNameExists(parentId, requestedName)) return requestedName;
        String body = requestedName;
        String ext = "";
        int dot = requestedName.lastIndexOf('.');
        if (dot > 0) {
            body = requestedName.substring(0, dot);
            ext = requestedName.substring(dot);
        }
        int counter = 1;
        String candidate;
        do {
            candidate = body + " (" + counter++ + ")" + ext;
        } while (activeNameExists(parentId, candidate));
        return candidate;
    }

    private String createObjectKey(String fileName) {
        String ext = "";
        int dot = fileName.lastIndexOf('.');
        if (dot > 0 && dot < fileName.length() - 1) {
            ext = fileName.substring(dot);
        }
        return "objects/" + UUID.randomUUID() + ext;
    }

    private Map<String, Object> cacheCompletedResult(String uploadId, File file) {
        Map<String, Object> cached = toFileResponse(file);
        cached.put("_userId", file.getUploaderId());
        redisService.set(resultKey(uploadId), cached, expireHours * 3600L);
        cached.remove("_userId");
        return cached;
    }

    private Map<String, Object> getCompletedResult(String uploadId, Long userId) {
        Object value = redisService.get(resultKey(uploadId));
        if (!(value instanceof Map<?, ?> raw)) return null;
        Object owner = raw.get("_userId");
        if (owner != null && !String.valueOf(userId).equals(String.valueOf(owner))) return null;
        Map<String, Object> result = new LinkedHashMap<>();
        raw.forEach((key, item) -> {
            if (!"_userId".equals(String.valueOf(key))) {
                result.put(String.valueOf(key), item);
            }
        });
        return result;
    }

    /** 任意时刻只打开一个分片，避免分片数较多时耗尽文件描述符。 */
    private static final class ChunkSequenceInputStream extends InputStream {
        private final Path chunkDir;
        private final int totalChunks;
        private int nextIndex;
        private InputStream current;

        private ChunkSequenceInputStream(Path chunkDir, int totalChunks) {
            this.chunkDir = chunkDir;
            this.totalChunks = totalChunks;
        }

        private boolean ensureCurrent() throws IOException {
            if (current == null && nextIndex < totalChunks) {
                current = Files.newInputStream(chunkDir.resolve(String.valueOf(nextIndex++)));
            }
            return current != null;
        }

        @Override
        public int read() throws IOException {
            while (ensureCurrent()) {
                int value = current.read();
                if (value >= 0) return value;
                current.close();
                current = null;
            }
            return -1;
        }

        @Override
        public int read(byte[] buffer, int offset, int length) throws IOException {
            while (ensureCurrent()) {
                int read = current.read(buffer, offset, length);
                if (read >= 0) return read;
                current.close();
                current = null;
            }
            return -1;
        }

        @Override
        public void close() throws IOException {
            if (current != null) current.close();
            current = null;
        }
    }

    /** 与 FileServiceImpl.resolveRelativePath 一致：从 parent 链回溯构建 MinIO key */
    private String resolveStorageKey(Long parentId, String fileName) {
        StringBuilder sb = new StringBuilder();
        Long pid = parentId;
        ArrayList<String> parts = new ArrayList<>();
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            parts.add(0, parent.getFileName());
            pid = parent.getParentId();
        }
        for (String part : parts) {
            sb.append(part).append('/');
        }
        sb.append(fileName);
        return resolveConflict(sb.toString(), parentId);
    }

    private String resolveConflict(String key, Long parentId) {
        if (!minioUtil.objectExists(key) && !activeNameExists(parentId, key.substring(key.lastIndexOf('/') + 1))) {
            return key;
        }

        int lastSlash = key.lastIndexOf('/');
        String dir = lastSlash >= 0 ? key.substring(0, lastSlash + 1) : "";
        String baseName = key.substring(lastSlash + 1);
        String nameBody = baseName;
        String ext = "";
        int dotIdx = baseName.lastIndexOf('.');
        if (dotIdx > 0) {
            nameBody = baseName.substring(0, dotIdx);
            ext = baseName.substring(dotIdx);
        }
        int counter = 1;
        String newKey;
        do {
            String newName = nameBody + " (" + counter + ")" + ext;
            newKey = dir + newName;
            counter++;
        } while (minioUtil.objectExists(newKey) || activeNameExists(parentId, newKey.substring(newKey.lastIndexOf('/') + 1)));
        return newKey;
    }

    private boolean activeNameExists(Long parentId, String fileName) {
        FileExample example = new FileExample();
        example.createCriteria()
                .andParentIdEqualTo(parentId != null ? parentId : 0L)
                .andFileNameEqualTo(fileName)
                .andDeleteTimeIsNull();
        return !fileMapper.selectByExample(example).isEmpty();
    }

    /** 与 FileServiceImpl.buildPath 一致：虚拟路径含斜杠前缀 */
    private String buildPath(String fileName, Long parentId) {
        StringBuilder path = new StringBuilder("/" + fileName);
        Long pid = parentId;
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            path.insert(0, "/" + parent.getFileName());
            pid = parent.getParentId();
        }
        return path.toString();
    }

    /**
     * 分片上传的 contentType 同样可能是 application/octet-stream，
     * DOC/DOCX 必须用最终文件名扩展名兜底，才能进入文本提取和在线预览流程。
     */
    private String detectFileType(String contentType, String fileName) {
        String type = contentType != null ? contentType.toLowerCase(java.util.Locale.ROOT) : "";
        if (type.startsWith("image/")) return "IMAGE";
        if (type.startsWith("video/")) return "VIDEO";
        if (type.startsWith("application/pdf")) return "DOCUMENT";
        if (type.equals("application/msword")) return "DOCUMENT";
        if (type.equals("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
            return "DOCUMENT";
        String extension = extensionOf(fileName);
        if ("doc".equals(extension) || "docx".equals(extension)) return "DOCUMENT";
        if (type.equals("application/vnd.ms-excel")) return "DOCUMENT";
        if (type.equals("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
            return "DOCUMENT";
        if (type.equals("application/vnd.ms-powerpoint")) return "DOCUMENT";
        if (type.equals("application/vnd.openxmlformats-officedocument.presentationml.presentation"))
            return "DOCUMENT";
        if (type.startsWith("text/")) return "DOCUMENT";
        return "OTHER";
    }

    private String extensionOf(String fileName) {
        if (fileName == null) return "";
        int dot = fileName.lastIndexOf('.');
        return dot >= 0 && dot < fileName.length() - 1
                ? fileName.substring(dot + 1).toLowerCase(java.util.Locale.ROOT)
                : "";
    }

    private Map<String, Object> toFileResponse(File f) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", f.getId());
        map.put("uploaderId", f.getUploaderId());
        map.put("parentId", f.getParentId());
        map.put("fileName", f.getFileName());
        map.put("filePath", f.getFilePath());
        map.put("fileType", f.getFileType());
        map.put("fileSize", f.getFileSize());
        map.put("contentType", f.getContentType());
        map.put("thumbnailKey", f.getThumbnailKey());
        if (f.getThumbnailKey() != null) {
            map.put("thumbnailUrl", "/api/file/" + f.getId() + "/thumbnail");
        }
        map.put("previewKey", f.getPreviewKey());
        if (f.getPreviewKey() != null) {
            map.put("previewUrl", "/api/file/" + f.getId() + "/preview");
        }
        map.put("isFolder", f.getIsFolder());
        map.put("processStatus", f.getProcessStatus());
        map.put("originText", f.getOriginText() != null ? f.getOriginText() : "");
        map.put("md5", f.getMd5());
        map.put("createTime", f.getCreateTime());
        map.put("updateTime", f.getUpdateTime());
        map.put("deleteTime", f.getDeleteTime());
        return map;
    }

    private void broadcastCreated(File file) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("fileId", file.getId());
        data.put("parentId", file.getParentId());
        sseBroadcaster.broadcast("file-created", data);
    }

    private Long getCurrentUserId() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AdminUserDetails details) {
            return details.getUserId();
        }
        Asserts.fail(ResultCode.UNAUTHORIZED);
        return 0L;
    }
}
