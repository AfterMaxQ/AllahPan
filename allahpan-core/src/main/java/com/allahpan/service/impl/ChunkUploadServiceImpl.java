package com.allahpan.service.impl;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.service.RedisService;
import com.allahpan.component.FileProcessSender;
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

    @Value("${allahpan.chunk.temp-dir:${java.io.tmpdir}/allahpan-chunks}")
    private String tempDir;

    @Value("${allahpan.chunk.expire-hours:24}")
    private int expireHours;

    @Autowired
    private RedisService redisService;
    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileProcessSender fileProcessSender;
    @Autowired
    private SseBroadcaster sseBroadcaster;

    // ==================== Redis Key ====================

    private String hashKey(String uploadId) { return "chunk:upload:" + uploadId; }
    private String setKey(String uploadId) { return "chunk:upload:" + uploadId + ":chunks"; }

    // ==================== init ====================

    @Override
    public Map<String, Object> init(String fileName, long fileSize, String fileMd5,
                                    String contentType, Long parentId, int chunkSize, int totalChunks) {
        Long userId = getCurrentUserId();
        String uploadId = computeUploadId(fileMd5, fileSize, fileName);
        String hk = hashKey(uploadId);

        if (Boolean.TRUE.equals(redisService.hasKey(hk))) {
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

        // 新会话 → 创建 Redis 记录 + 临时目录
        redisService.hSet(hk, "fileName", fileName, expireHours * 3600L);
        redisService.hSet(hk, "fileSize", String.valueOf(fileSize));
        redisService.hSet(hk, "fileMd5", fileMd5);
        redisService.hSet(hk, "contentType", contentType != null ? contentType : "application/octet-stream");
        redisService.hSet(hk, "parentId", String.valueOf(parentId != null ? parentId : 0L));
        redisService.hSet(hk, "chunkSize", String.valueOf(chunkSize));
        redisService.hSet(hk, "totalChunks", String.valueOf(totalChunks));
        redisService.hSet(hk, "uploadedCount", "0");
        redisService.hSet(hk, "status", "uploading");
        redisService.hSet(hk, "userId", String.valueOf(userId));
        redisService.expire(hk, expireHours * 3600L);

        Path chunkDir = Path.of(tempDir, uploadId);
        try {
            Files.createDirectories(chunkDir);
        } catch (IOException e) {
            log.error("创建临时目录失败: {}", chunkDir, e);
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
    public void uploadChunk(String uploadId, int chunkIndex, byte[] chunkBytes) {
        String hk = hashKey(uploadId);
        Asserts.isTrue(Boolean.TRUE.equals(redisService.hasKey(hk)), "上传会话不存在或已过期");

        Path chunkFile = Path.of(tempDir, uploadId, String.valueOf(chunkIndex));
        try {
            Files.write(chunkFile, chunkBytes);
        } catch (IOException e) {
            log.error("写入分片失败: {}", chunkFile, e);
            Asserts.fail("分片保存失败");
        }

        redisService.sAdd(setKey(uploadId), String.valueOf(chunkIndex));
        redisService.expire(setKey(uploadId), expireHours * 3600L);
        redisService.hIncr(hk, "uploadedCount", 1L);

        // 刷新主 hash TTL
        redisService.expire(hk, expireHours * 3600L);
    }

    // ==================== complete ====================

    @Override
    public Map<String, Object> complete(String uploadId) {
        String hk = hashKey(uploadId);
        Asserts.isTrue(Boolean.TRUE.equals(redisService.hasKey(hk)), "上传会话不存在或已过期");

        Map<Object, Object> meta = redisService.hGetAll(hk);
        String fileName = (String) meta.get("fileName");
        long fileSize = Long.parseLong((String) meta.get("fileSize"));
        String fileMd5 = (String) meta.get("fileMd5");
        String contentType = (String) meta.get("contentType");
        Long parentId = Long.parseLong((String) meta.get("parentId"));
        int totalChunks = Integer.parseInt((String) meta.get("totalChunks"));
        Long userId = Long.parseLong((String) meta.get("userId"));

        // 验证所有分片已上传
        long uploadedCount = redisService.sMembers(setKey(uploadId)).size();
        Asserts.isTrue(uploadedCount == totalChunks,
                String.format("分片未完整上传 (%d/%d)", uploadedCount, totalChunks));

        Path chunkDir = Path.of(tempDir, uploadId);
        Path mergedFile = chunkDir.resolve("merged");

        try {
            // 1. 合并分片
            mergeChunks(chunkDir, totalChunks, mergedFile);

            // 2. 上传到 MinIO + 计算 MD5
            String storageKey = resolveStorageKey(parentId, fileName);
            String actualMd5 = storeAndCalculateMd5(mergedFile, storageKey, contentType);

            // 3. 秒传检测
            if (!actualMd5.isEmpty()) {
                FileExample md5Example = new FileExample();
                md5Example.createCriteria().andMd5EqualTo(actualMd5).andIsFolderEqualTo((byte) 0)
                        .andDeleteTimeIsNull();
                var dupList = fileMapper.selectByExample(md5Example);
                if (!dupList.isEmpty()) {
                    File existing = dupList.get(0);
                    File dup = new File();
                    dup.setUploaderId(userId);
                    dup.setParentId(parentId);
                    dup.setFileName(fileName);
                    dup.setStorageKey(storageKey);
                    dup.setFileSize(existing.getFileSize());
                    dup.setContentType(existing.getContentType());
                    dup.setMd5(actualMd5);
                    dup.setFileType(existing.getFileType());
                    dup.setThumbnailKey(existing.getThumbnailKey());
                    dup.setIsFolder((byte) 0);
                    dup.setProcessStatus((byte) 3);
                    dup.setCreateTime(new Date());
                    dup.setFilePath(buildPath(fileName, parentId));
                    fileMapper.insert(dup);
                    cleanup(uploadId, chunkDir);
                    broadcastCreated(dup);
                    return toFileResponse(dup);
                }
            }

            // 4. 创建 DB 记录 + 发送处理消息
            File record = new File();
            record.setUploaderId(userId);
            record.setParentId(parentId);
            record.setFileName(fileName);
            record.setStorageKey(storageKey);
            record.setFileSize(fileSize);
            record.setContentType(contentType);
            record.setMd5(actualMd5);
            record.setIsFolder((byte) 0);
            record.setProcessStatus((byte) 0);
            record.setFileType(detectFileType(contentType));
            record.setCreateTime(new Date());
            record.setFilePath(buildPath(fileName, parentId));
            fileMapper.insert(record);

            fileProcessSender.sendProcess(new FileProcessMessage(record.getId(), FileProcessMessage.Stage.UPLOADED));
            cleanup(uploadId, chunkDir);
            broadcastCreated(record);
            return toFileResponse(record);

        } catch (Exception e) {
            log.error("合并完成上传失败: uploadId={}", uploadId, e);
            Asserts.fail("文件处理失败，请重试");
            return null;
        }
    }

    // ==================== getStatus ====================

    @Override
    public Map<String, Object> getStatus(String uploadId) {
        String hk = hashKey(uploadId);
        Asserts.isTrue(Boolean.TRUE.equals(redisService.hasKey(hk)), "上传会话不存在或已过期");

        Map<Object, Object> meta = redisService.hGetAll(hk);
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
                        log.info("清理过期分片目录: {}", dir.getFileName());
                    }
                } catch (IOException e) {
                    log.warn("无法读取目录属性: {}", dir, e);
                }
            }
        } catch (IOException e) {
            log.warn("分片目录扫描失败", e);
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
            log.warn("清理临时目录失败: {}", dir, e);
        }
    }

    // ==================== Helpers ====================

    private String computeUploadId(String md5, long fileSize, String fileName) {
        String input = md5 + fileSize + fileName;
        return UUID.nameUUIDFromBytes(input.getBytes(StandardCharsets.UTF_8)).toString();
    }

    private void mergeChunks(Path chunkDir, int totalChunks, Path mergedFile) throws IOException {
        try (OutputStream out = Files.newOutputStream(mergedFile)) {
            for (int i = 0; i < totalChunks; i++) {
                Path chunk = chunkDir.resolve(String.valueOf(i));
                if (!Files.exists(chunk)) {
                    throw new IOException("缺少分片: " + i);
                }
                Files.copy(chunk, out);
            }
        }
    }

    private String storeAndCalculateMd5(Path file, String objectKey, String contentType) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("MD5");
        try (InputStream in = Files.newInputStream(file);
             DigestInputStream dis = new DigestInputStream(in, digest)) {
            minioUtil.putObject(objectKey, dis, Files.size(file), contentType);
        }
        return java.util.HexFormat.of().formatHex(digest.digest());
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
        return resolveConflict(sb.toString());
    }

    private String resolveConflict(String key) {
        String base = key;
        int dotIdx = base.lastIndexOf('.');
        String nameBody = dotIdx > 0 ? base.substring(0, dotIdx) : base;
        String ext = dotIdx > 0 ? base.substring(dotIdx) : "";
        int counter = 1;
        while (minioUtil.objectExists(key)) {
            key = nameBody + " (" + counter + ")" + ext;
            counter++;
        }
        return key;
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

    private String detectFileType(String contentType) {
        if (contentType == null) return "OTHER";
        if (contentType.startsWith("image/")) return "IMAGE";
        if (contentType.startsWith("video/")) return "VIDEO";
        if (contentType.startsWith("application/pdf")) return "DOCUMENT";
        if (contentType.equals("application/msword")) return "DOCUMENT";
        if (contentType.equals("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
            return "DOCUMENT";
        if (contentType.equals("application/vnd.ms-excel")) return "DOCUMENT";
        if (contentType.equals("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
            return "DOCUMENT";
        if (contentType.equals("application/vnd.ms-powerpoint")) return "DOCUMENT";
        if (contentType.equals("application/vnd.openxmlformats-officedocument.presentationml.presentation"))
            return "DOCUMENT";
        if (contentType.startsWith("text/")) return "DOCUMENT";
        return "OTHER";
    }

    private Map<String, Object> toFileResponse(File f) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", f.getId());
        map.put("uploaderId", f.getUploaderId());
        map.put("parentId", f.getParentId());
        map.put("fileName", f.getFileName());
        map.put("filePath", f.getFilePath());
        map.put("storageKey", f.getStorageKey());
        map.put("fileType", f.getFileType());
        map.put("fileSize", f.getFileSize());
        map.put("contentType", f.getContentType());
        map.put("thumbnailKey", f.getThumbnailKey());
        if (f.getThumbnailKey() != null) {
            map.put("thumbnailUrl", "/api/file/" + f.getId() + "/thumbnail");
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
