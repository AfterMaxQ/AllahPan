package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.log.StructuredLog;
import com.allahpan.component.EsIndexService;
import com.allahpan.component.MinioUtil;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.FileService;
import com.github.pagehelper.PageHelper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class FileServiceImpl implements FileService {
    private static final Logger log = LoggerFactory.getLogger(FileServiceImpl.class);
    private static final int MAX_FILE_NAME_LENGTH = 255;
    private static final int MAX_PATH_LENGTH = 500;
    private static final int DELETE_BATCH_SIZE = 500;

    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private EsIndexService esIndexService;

    @Override
    public File upload(MultipartFile file, Long parentId) {
        Long uploaderId = getCurrentUserId();
        Long pid = parentId != null ? parentId : 0L;

        // 验证 parentId 指向文件夹
        if (pid > 0) {
            validateActiveFolder(pid);
        }

        String originalName = file.getOriginalFilename();
        Asserts.isTrue(originalName != null && !originalName.isBlank(), "文件名不能为空");
        Asserts.isTrue(originalName.length() <= MAX_FILE_NAME_LENGTH,
                "文件名过长（最大" + MAX_FILE_NAME_LENGTH + "字符）");

        // 展示名与对象键分离：重命名/移动只改元数据，不再复制大对象。
        String finalName = resolveAvailableName(pid, originalName);
        String relativePath = createObjectKey(finalName);

        // 上传到 MinIO + 同时计算 MD5
        String contentType = file.getContentType();
        if (contentType == null) contentType = "application/octet-stream";
        String md5;
        try {
            md5 = storeAndCalculateMd5(file.getInputStream(), relativePath,
                    file.getSize(), contentType);
        } catch (Exception e) {
            log.error(StructuredLog.event("file.upload.failed", "errorType", e.getClass().getSimpleName()), e);
            Asserts.fail("文件保存失败，请重试");
            return null; // unreachable
        }

        // MD5 秒传检测（仅当 MD5 计算成功时）
        if (!md5.isEmpty()) {
            FileExample md5Example = new FileExample();
            md5Example.createCriteria().andMd5EqualTo(md5).andIsFolderEqualTo((byte) 0)
                    .andDeleteTimeIsNull();
            var dupList = fileMapper.selectByExample(md5Example);
            if (!dupList.isEmpty()) {
                File existing = dupList.get(0);
                // 秒传：复用已有文件的元数据，但保留独立 MinIO 对象避免删除源文件后断链
                // relativePath 已在上传阶段存储到 MinIO，不删除，确保路径与 filePath 一致
                File dup = new File();
                dup.setUploaderId(uploaderId);
                dup.setParentId(pid);
                dup.setFileName(finalName);
                dup.setStorageKey(relativePath);
                dup.setFileSize(existing.getFileSize());
                dup.setContentType(existing.getContentType());
                dup.setMd5(md5);
                dup.setFileType(existing.getFileType());
                dup.setThumbnailKey(existing.getThumbnailKey());
                dup.setPreviewKey(existing.getPreviewKey());
                dup.setOriginText(existing.getOriginText());
                dup.setIsFolder((byte) 0);
                dup.setProcessStatus((byte) 3);
                dup.setCreateTime(new Date());
                dup.setFilePath(buildPath(finalName, pid));
                try {
                    fileMapper.insert(dup);
                } catch (Exception e) {
                    log.error(StructuredLog.event("file.upload.failed", "mode", "instant",
                            "errorType", e.getClass().getSimpleName()), e);
                    try { minioUtil.removeObject(relativePath); } catch (Exception ex) {
                        log.warn(StructuredLog.event("storage.rollback.failed", "errorType", ex.getClass().getSimpleName()), ex);
                    }
                    Asserts.fail("文件保存失败");
                }
                esIndexService.index(dup);
                return dup;
            }
        }

        // 创建 DB 记录
        File record = new File();
        record.setUploaderId(uploaderId);
        record.setParentId(pid);
        record.setFileName(finalName);
        record.setStorageKey(relativePath);
        record.setFileSize(file.getSize());
        record.setContentType(contentType);
        record.setMd5(md5);
        record.setIsFolder((byte) 0);
        record.setProcessStatus((byte) 0);
        record.setFileType(detectFileType(contentType, finalName));
        record.setCreateTime(new Date());
        record.setFilePath(buildPath(finalName, pid));
        try {
            fileMapper.insert(record);
        } catch (Exception e) {
            log.error(StructuredLog.event("file.upload.failed", "errorType", e.getClass().getSimpleName()), e);
            try { minioUtil.removeObject(relativePath); } catch (Exception ex) {
                log.warn(StructuredLog.event("storage.rollback.failed", "errorType", ex.getClass().getSimpleName()), ex);
            }
            Asserts.fail("文件保存失败");
        }
        return record;
    }

    @Override
    public File createFolder(String folderName, Long parentId) {
        Asserts.isTrue(folderName != null && !folderName.isBlank(), "文件夹名不能为空");
        Asserts.isTrue(folderName.length() <= MAX_FILE_NAME_LENGTH,
                "文件夹名过长（最大" + MAX_FILE_NAME_LENGTH + "字符）");
        Long pid = parentId != null ? parentId : 0L;
        if (pid > 0) {
            validateActiveFolder(pid);
        }
        assertNameUnique(pid, folderName);

        File file = new File();
        file.setUploaderId(getCurrentUserId());
        file.setParentId(pid);
        file.setFileName(folderName);
        file.setIsFolder((byte) 1);
        file.setFileType("FOLDER");
        file.setProcessStatus((byte) 3);
        file.setCreateTime(new Date());
        file.setFilePath(buildPath(folderName, pid));

        // MinIO 无需目录：storageKey 仅作为逻辑路径存储在 DB
        String relativePath = resolveRelativePath(pid, folderName);
        file.setStorageKey(relativePath);
        fileMapper.insert(file);
        return file;
    }

    @Override
    public List<File> listFiles(Long parentId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(parentId)
                .andDeleteTimeIsNull();
        // 分页前先给数据库一个稳定的全局顺序，避免翻页时记录漂移或重复。
        example.setOrderByClause("is_folder DESC, file_name ASC, id ASC");
        List<File> files = fileMapper.selectByExample(example);
        populateFolderSizes(files, false);
        files.sort(this::compareFiles);
        return files;
    }

    @Override
    public List<File> getDirectoryTree(Long folderId) {
        var list = new java.util.ArrayList<File>();
        Set<Long> visited = new HashSet<>();
        Long current = folderId;
        while (current != null && current > 0 && visited.add(current)) {
            File f = fileMapper.selectByPrimaryKey(current);
            if (f == null) break;
            list.add(0, f);
            current = f.getParentId();
        }
        return list;
    }

    @Override
    public void deleteFile(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        // MySQL 优先：先标记软删除，再尝试移动 MinIO 对象到回收站
        // MinIO 移动失败不阻塞：文件已标记删除，物理对象保留在 files bucket 安全
        file.setDeleteTime(new Date());
        fileMapper.updateByPrimaryKeySelective(file);
        try {
            moveToTrash(file);
        } catch (Exception e) {
            log.warn(StructuredLog.event("file.delete.degraded", "fileId", file.getId(),
                    "dependency", "minio", "errorType", e.getClass().getSimpleName()), e);
        }
        // 从 ES 移除，避免搜索到已删除文件
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            esIndexService.delete(fileId);
        }
        if (file.getIsFolder() == 1) {
            deleteChildren(fileId, new java.util.concurrent.atomic.AtomicInteger(0));
        }
    }

    private void deleteChildren(Long folderId, java.util.concurrent.atomic.AtomicInteger counter) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId).andDeleteTimeIsNull();
        var children = fileMapper.selectByExample(example);
        for (File child : children) {
            // MySQL 优先：先标记软删除
            child.setDeleteTime(new Date(System.currentTimeMillis() + counter.getAndIncrement()));
            fileMapper.updateByPrimaryKeySelective(child);
            try {
                moveToTrash(child);
            } catch (Exception e) {
                log.warn(StructuredLog.event("file.delete.degraded", "fileId", child.getId(),
                        "dependency", "minio", "errorType", e.getClass().getSimpleName()), e);
            }
            if (child.getIsFolder() == null || child.getIsFolder() != 1) {
                esIndexService.delete(child.getId());
            }
            if (child.getIsFolder() == 1) {
                deleteChildren(child.getId(), counter);
            }
        }
    }

    /** 统计其他活跃记录（delete_time IS NULL）共享同一 storageKey 的数量 */
    private long countActiveRefs(String storageKey, Long excludeId) {
        if (storageKey == null) return 0;
        FileExample example = new FileExample();
        example.createCriteria()
                .andStorageKeyEqualTo(storageKey)
                .andDeleteTimeIsNull()
                .andIdNotEqualTo(excludeId);
        return fileMapper.countByExample(example);
    }

    /** 将文件移至回收站（MinIO: 复制到 trash bucket，仅当无其他活跃引用时删除源对象） */
    private void moveToTrash(File file) throws Exception {
        if (file.getStorageKey() == null) return;
        // 非文件夹 → 复制到 trash bucket
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            minioUtil.copyToTrash(file.getStorageKey());
            // 仅当无其他活跃记录引用同一 storageKey 时才从 files bucket 删除
            if (countActiveRefs(file.getStorageKey(), file.getId()) == 0) {
                minioUtil.removeObject(file.getStorageKey());
            }
        }
    }

    /** 从回收站恢复文件（MinIO: trash bucket → files bucket 后删除 trash 副本） */
    private void restoreFromTrash(File file) throws Exception {
        if (file.getStorageKey() == null) return;
        // 非文件夹 → 从 trash bucket 恢复到 files bucket
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            // 如果已有其他活跃记录引用同一 storageKey，对象已在 files bucket 中，无需恢复
            if (countActiveRefs(file.getStorageKey(), file.getId()) == 0) {
                minioUtil.restoreFromTrash(file.getStorageKey());
                minioUtil.removeFromTrash(file.getStorageKey());
            }
        }
    }

    @Override
    public File getFileById(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        if (file != null && file.getIsFolder() != null && file.getIsFolder() == 1
                && file.getDeleteTime() == null) {
            file.setFileSize(getFolderSize(file.getId()));
        }
        return file;
    }

    @Override
    public List<File> listTrash(int pageNum, int pageSize) {
        Long userId = getCurrentUserId();
        FileExample example = new FileExample();
        example.createCriteria()
                .andDeleteTimeIsNotNull()
                .andUploaderIdEqualTo(userId);
        example.setOrderByClause("delete_time DESC");
        PageHelper.startPage(pageNum, pageSize);
        List<File> files = fileMapper.selectByExample(example);
        populateFolderSizes(files, true);
        return files;
    }

    @Override
    public void restoreFile(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        Asserts.isTrue(file.getDeleteTime() != null, "文件不在垃圾站中");
        if (file.getParentId() != null && file.getParentId() > 0) {
            File parent = fileMapper.selectByPrimaryKey(file.getParentId());
            if (parent != null && parent.getDeleteTime() != null) {
                Asserts.fail("父文件夹在垃圾站中，请先恢复父文件夹");
            }
        }
        Date oldDeleteTime = file.getDeleteTime();
        file.setDeleteTime(null);
        fileMapper.updateByPrimaryKey(file);
        try {
            restoreFromTrash(file);
        } catch (Exception e) {
            log.error(StructuredLog.event("file.restore.failed", "fileId", fileId,
                    "dependency", "minio", "errorType", e.getClass().getSimpleName()), e);
            file.setDeleteTime(oldDeleteTime);
            fileMapper.updateByPrimaryKey(file);
            Asserts.fail("文件恢复失败，请重试");
        }
        // 重新索引到 ES，搜索可再次找到恢复的文件
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            esIndexService.index(file);
        }
        if (file.getIsFolder() == 1) {
            restoreChildren(fileId, oldDeleteTime);
        }
    }

    private void restoreChildren(Long folderId, Date cascadeDeleteTime) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId).andDeleteTimeIsNotNull();
        var children = fileMapper.selectByExample(example);
        for (File child : children) {
            if (child.getDeleteTime() != null && child.getDeleteTime().before(cascadeDeleteTime)) {
                continue;
            }
            Date oldDeleteTime = child.getDeleteTime();
            child.setDeleteTime(null);
            fileMapper.updateByPrimaryKey(child);
            try {
                restoreFromTrash(child);
            } catch (Exception e) {
                log.error(StructuredLog.event("file.restore.failed", "fileId", child.getId(),
                        "dependency", "minio", "errorType", e.getClass().getSimpleName()), e);
                child.setDeleteTime(oldDeleteTime);
                fileMapper.updateByPrimaryKey(child);
                continue;
            }
            if (child.getIsFolder() == null || child.getIsFolder() != 1) {
                esIndexService.index(child);
            }
            if (child.getIsFolder() == 1) {
                restoreChildren(child.getId(), cascadeDeleteTime);
            }
        }
    }

    @Override
    @Transactional
    public void permanentDelete(Long fileId) {
        Map<String, Object> result = batchPermanentDelete(List.of(fileId));
        @SuppressWarnings("unchecked")
        List<Long> failedIds = (List<Long>) result.get("failedIds");
        Asserts.isTrue(failedIds == null || failedIds.isEmpty(), "文件不存在或不在垃圾站中");
    }

    // ========== 路径工具 ==========

    /**
     * 构建 MinIO 对象键（逻辑路径）。
     * 格式: folderA/folderB/filename.txt
     */
    private String resolveRelativePath(Long parentId, String fileName) {
        StringBuilder sb = new StringBuilder();
        Long pid = parentId;
        java.util.ArrayList<String> parts = new java.util.ArrayList<>();
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            Asserts.isTrue(parent.getDeleteTime() == null, "父目录已在垃圾站中");
            parts.add(0, parent.getFileName());
            pid = parent.getParentId();
        }
        for (String part : parts) {
            sb.append(part).append('/');
        }
        sb.append(fileName);
        return sb.toString();
    }

    /**
     * 从 parent 链向根回溯，拼接完整虚拟路径（用于 DB file_path 字段）
     */
    private String buildPath(String fileName, Long parentId) {
        StringBuilder path = new StringBuilder("/" + fileName);
        Long pid = parentId;
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            Asserts.isTrue(parent.getDeleteTime() == null, "父目录已在垃圾站中");
            path.insert(0, "/" + parent.getFileName());
            pid = parent.getParentId();
        }
        String result = path.toString();
        Asserts.isTrue(result.length() <= MAX_PATH_LENGTH,
                "文件路径过长（最大" + MAX_PATH_LENGTH + "字符），请缩短文件夹或文件名");
        return result;
    }

    /**
     * 检查同一父目录下是否已存在同名文件/文件夹（未删除）
     */
    private void assertNameUnique(Long parentId, String fileName) {
        FileExample example = new FileExample();
        example.createCriteria()
                .andParentIdEqualTo(parentId)
                .andFileNameEqualTo(fileName)
                .andDeleteTimeIsNull();
        Asserts.isTrue(fileMapper.selectByExample(example).isEmpty(),
                "同名文件或文件夹已存在");
    }

    private void validateActiveFolder(Long folderId) {
        File parent = fileMapper.selectByPrimaryKey(folderId);
        Asserts.isTrue(parent != null && parent.getIsFolder() != null && parent.getIsFolder() == 1,
                "父目录不存在或不是文件夹");
        Asserts.isTrue(parent.getDeleteTime() == null, "父目录已在垃圾站中");
    }

    /**
     * 递归重建文件夹下所有子孙节点的虚拟路径。对象键保持不变。
     */
    private void rebuildDescendantPaths(Long folderId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId).andDeleteTimeIsNull();
        List<File> children = fileMapper.selectByExample(example);
        for (File child : children) {
            child.setFilePath(buildPath(child.getFileName(), child.getParentId()));
            fileMapper.updateByPrimaryKeySelective(child);

            // 更新 ES 中子文件的路径（非文件夹）
            if (child.getIsFolder() == null || child.getIsFolder() != 1) {
                esIndexService.index(child);
            }

            if (child.getIsFolder() == 1) {
                rebuildDescendantPaths(child.getId());
            }
        }
    }

    /**
     * 检查 candidateId 是否是 ancestorId 的后代节点（用于循环检测）
     */
    private boolean isDescendant(Long ancestorId, Long candidateId) {
        Long current = candidateId;
        while (current != null && current > 0) {
            if (current.equals(ancestorId)) return true;
            File f = fileMapper.selectByPrimaryKey(current);
            if (f == null) break;
            current = f.getParentId();
        }
        return false;
    }

    private String resolveAvailableName(Long parentId, String requestedName) {
        if (!activeNameExists(parentId, requestedName)) return requestedName;
        String nameBody = requestedName;
        String ext = "";
        int dotIdx = requestedName.lastIndexOf('.');
        if (dotIdx > 0) {
            nameBody = requestedName.substring(0, dotIdx);
            ext = requestedName.substring(dotIdx);
        }
        int counter = 1;
        String candidate;
        do {
            candidate = nameBody + " (" + counter++ + ")" + ext;
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

    private boolean activeNameExists(Long parentId, String fileName) {
        FileExample example = new FileExample();
        example.createCriteria()
                .andParentIdEqualTo(parentId != null ? parentId : 0L)
                .andFileNameEqualTo(fileName)
                .andDeleteTimeIsNull();
        return !fileMapper.selectByExample(example).isEmpty();
    }

    // ========== 工具方法 ==========

    /**
     * MIME 类型由浏览器提供，部分浏览器/客户端上传 Word 文件时会退化成
     * application/octet-stream，因此 DOC/DOCX 需要用文件扩展名兜底识别。
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

    /**
     * 上传到 MinIO 并同时计算 MD5。使用 DigestInputStream 流式传输，避免将大文件全部加载到内存。
     */
    private String storeAndCalculateMd5(InputStream inputStream, String objectKey,
                                        long size, String contentType) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("MD5");
        try (DigestInputStream dis = new DigestInputStream(inputStream, digest)) {
            minioUtil.putObject(objectKey, dis, size, contentType);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private Long getCurrentUserId() {
        var auth = org.springframework.security.core.context.SecurityContextHolder
                .getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof com.allahpan.bo.AdminUserDetails details) {
            return details.getUserId();
        }
        Asserts.fail(ResultCode.UNAUTHORIZED);
        return 0L;
    }

    // ========== 重命名 ==========

    @Override
    public File renameFile(Long fileId, String newName) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        Asserts.isTrue(file.getDeleteTime() == null, "文件已删除，无法重命名");
        Asserts.isTrue(newName != null && !newName.isBlank(), "文件名不能为空");
        Asserts.isTrue(newName.length() <= MAX_FILE_NAME_LENGTH,
                "文件名过长（最大" + MAX_FILE_NAME_LENGTH + "字符）");
        Long parentId = file.getParentId() != null ? file.getParentId() : 0L;
        if (!newName.equals(file.getFileName())) {
            assertNameUnique(parentId, newName);
        }

        // storageKey 是稳定对象 ID；重命名只修改元数据，避免复制整个大文件。
        file.setFileName(newName);
        file.setFilePath(buildPath(newName, file.getParentId()));
        fileMapper.updateByPrimaryKeySelective(file);

        // 更新 ES 中的文件名/路径（非文件夹）
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            esIndexService.index(file);
        }
        if (file.getIsFolder() == 1) {
            rebuildDescendantPaths(fileId);
        }
        return file;
    }

    // ========== 移动 ==========

    @Override
    public File moveFile(Long fileId, Long targetParentId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        Asserts.isTrue(file.getDeleteTime() == null, "文件已删除，无法移动");

        if (targetParentId != null && targetParentId > 0) {
            File target = fileMapper.selectByPrimaryKey(targetParentId);
            Asserts.isTrue(target != null && target.getIsFolder() == 1, "目标目录无效");
            Asserts.isTrue(target.getDeleteTime() == null, "目标目录在垃圾站中");
            Asserts.isTrue(!targetParentId.equals(fileId), "不能移动到自身");
            Asserts.isTrue(!isDescendant(fileId, targetParentId), "不能移动到子文件夹");
        }

        Long newParentId = targetParentId != null && targetParentId > 0 ? targetParentId : 0L;
        Long currentParentId = file.getParentId() != null ? file.getParentId() : 0L;
        if (newParentId.equals(currentParentId)) {
            return file;
        }
        assertNameUnique(newParentId, file.getFileName());

        // 移动同样只修改虚拟目录元数据，storageKey 始终稳定。
        file.setParentId(newParentId);
        file.setFilePath(buildPath(file.getFileName(), newParentId));
        fileMapper.updateByPrimaryKeySelective(file);

        // 更新 ES 中的文件路径（非文件夹）
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            esIndexService.index(file);
        }
        if (file.getIsFolder() == 1) {
            rebuildDescendantPaths(fileId);
        }
        return file;
    }

    // ========== 批量删除 ==========

    @Override
    public Map<String, Object> batchDelete(List<Long> fileIds) {
        List<Long> failedIds = new ArrayList<>();
        int deleted = 0;
        for (Long fileId : fileIds) {
            try {
                deleteFile(fileId);
                deleted++;
            } catch (Exception e) {
                log.warn("批量删除失败: fileId={}", fileId, e);
                failedIds.add(fileId);
            }
        }
        Map<String, Object> result = new HashMap<>();
        result.put("deletedCount", deleted);
        result.put("failedIds", failedIds);
        return result;
    }

    @Override
    @Transactional
    public Map<String, Object> batchPermanentDelete(List<Long> fileIds) {
        LinkedHashSet<Long> requestedIds = new LinkedHashSet<>();
        if (fileIds != null) {
            for (Long fileId : fileIds) {
                if (fileId != null) requestedIds.add(fileId);
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        if (requestedIds.isEmpty()) {
            result.put("deletedCount", 0);
            result.put("failedIds", List.of());
            return result;
        }

        List<File> trashFiles = fileMapper.selectTrashSubtree(new ArrayList<>(requestedIds));
        Set<Long> foundIds = new HashSet<>();
        for (File file : trashFiles) {
            foundIds.add(file.getId());
        }
        List<Long> failedIds = requestedIds.stream()
                .filter(id -> !foundIds.contains(id))
                .toList();

        result.put("deletedCount", purgeTrashFiles(trashFiles));
        result.put("failedIds", failedIds);
        return result;
    }

    @Override
    public Long getFolderSize(Long folderId) {
        Long size = fileMapper.getFolderSize(folderId);
        return size != null ? size : 0L;
    }

    @Override
    @Transactional
    public int emptyTrash() {
        FileExample example = new FileExample();
        example.createCriteria().andDeleteTimeIsNotNull();
        List<File> trashFiles = fileMapper.selectByExample(example);
        return purgeTrashFiles(trashFiles);
    }

    /**
     * 先用批量 SQL 删除数据库记录，再按去重后的对象 key 清理外部索引与 MinIO。
     * 外部清理失败由现有补偿/孤儿扫描兜底，不会造成数据库半删状态。
     */
    private int purgeTrashFiles(List<File> trashFiles) {
        if (trashFiles == null || trashFiles.isEmpty()) return 0;

        LinkedHashMap<Long, File> uniqueFiles = new LinkedHashMap<>();
        for (File file : trashFiles) {
            if (file != null && file.getId() != null) {
                uniqueFiles.putIfAbsent(file.getId(), file);
            }
        }
        if (uniqueFiles.isEmpty()) return 0;

        List<Long> ids = new ArrayList<>(uniqueFiles.keySet());
        int deleted = 0;
        for (int start = 0; start < ids.size(); start += DELETE_BATCH_SIZE) {
            int end = Math.min(start + DELETE_BATCH_SIZE, ids.size());
            deleted += fileMapper.deleteByIds(ids.subList(start, end));
        }

        Set<String> storageKeys = new LinkedHashSet<>();
        Set<String> imageKeys = new LinkedHashSet<>();
        for (File file : uniqueFiles.values()) {
            if (file.getIsFolder() == null || file.getIsFolder() != 1) {
                esIndexService.delete(file.getId());
                if (file.getStorageKey() != null) storageKeys.add(file.getStorageKey());
            }
            if (file.getThumbnailKey() != null) imageKeys.add(file.getThumbnailKey());
            if (file.getPreviewKey() != null) imageKeys.add(file.getPreviewKey());
        }

        for (String storageKey : storageKeys) {
            try {
                if (!hasStorageReference(storageKey)) {
                    minioUtil.removeFromTrash(storageKey);
                }
            } catch (Exception e) {
                log.warn(StructuredLog.event("file.delete.failed", "dependency", "minio",
                        "errorType", e.getClass().getSimpleName()), e);
            }
        }

        for (String imageKey : imageKeys) {
            try {
                if (!hasThumbnailReference(imageKey) && !hasPreviewReference(imageKey)) {
                    minioUtil.removeThumbnail(imageKey);
                }
            } catch (Exception e) {
                log.warn(StructuredLog.event("file.preview.delete_failed", "dependency", "minio",
                        "errorType", e.getClass().getSimpleName()), e);
            }
        }
        return deleted;
    }

    private boolean hasStorageReference(String storageKey) {
        FileExample example = new FileExample();
        example.createCriteria().andStorageKeyEqualTo(storageKey);
        return fileMapper.countByExample(example) > 0;
    }

    private boolean hasThumbnailReference(String thumbnailKey) {
        FileExample example = new FileExample();
        example.createCriteria().andThumbnailKeyEqualTo(thumbnailKey);
        return fileMapper.countByExample(example) > 0;
    }

    private boolean hasPreviewReference(String previewKey) {
        FileExample example = new FileExample();
        example.createCriteria().andPreviewKeyEqualTo(previewKey);
        return fileMapper.countByExample(example) > 0;
    }

    private void populateFolderSizes(List<File> files, boolean includeDeleted) {
        List<Long> folderIds = files.stream()
                .filter(file -> file.getIsFolder() != null && file.getIsFolder() == 1)
                .map(File::getId)
                .toList();
        if (folderIds.isEmpty()) return;

        Map<Long, Long> sizes = new HashMap<>();
        List<File> sizeRows = includeDeleted
                ? fileMapper.getTrashFolderSizes(folderIds)
                : fileMapper.getFolderSizes(folderIds);
        for (File sizeRow : sizeRows) {
            sizes.put(sizeRow.getId(), sizeRow.getFileSize() != null ? sizeRow.getFileSize() : 0L);
        }
        for (File file : files) {
            if (file.getIsFolder() != null && file.getIsFolder() == 1) {
                file.setFileSize(sizes.getOrDefault(file.getId(), 0L));
            }
        }
    }

    private int compareFiles(File left, File right) {
        int leftFolder = left.getIsFolder() != null && left.getIsFolder() == 1 ? 0 : 1;
        int rightFolder = right.getIsFolder() != null && right.getIsFolder() == 1 ? 0 : 1;
        int compared = Integer.compare(leftFolder, rightFolder);
        if (compared != 0) return compared;

        compared = Integer.compare(fileTypeRank(left.getFileType()), fileTypeRank(right.getFileType()));
        if (compared != 0) return compared;

        compared = compareNaturalNames(left.getFileName(), right.getFileName());
        if (compared != 0) return compared;
        if (left.getId() == null) return right.getId() == null ? 0 : 1;
        if (right.getId() == null) return -1;
        return left.getId().compareTo(right.getId());
    }

    private int fileTypeRank(String fileType) {
        if ("IMAGE".equals(fileType)) return 0;
        if ("VIDEO".equals(fileType)) return 1;
        if ("DOCUMENT".equals(fileType)) return 2;
        if ("OTHER".equals(fileType)) return 3;
        return 4;
    }

    /**
     * 不做数据库正则和数值转换，在内存中稳定地按自然文件名排序。
     */
    private int compareNaturalNames(String left, String right) {
        String a = left != null ? left : "";
        String b = right != null ? right : "";
        int ai = 0;
        int bi = 0;
        while (ai < a.length() && bi < b.length()) {
            char ac = a.charAt(ai);
            char bc = b.charAt(bi);
            if (Character.isDigit(ac) && Character.isDigit(bc)) {
                int aStart = ai;
                int bStart = bi;
                while (aStart < a.length() && a.charAt(aStart) == '0') aStart++;
                while (bStart < b.length() && b.charAt(bStart) == '0') bStart++;
                int aEnd = aStart;
                int bEnd = bStart;
                while (aEnd < a.length() && Character.isDigit(a.charAt(aEnd))) aEnd++;
                while (bEnd < b.length() && Character.isDigit(b.charAt(bEnd))) bEnd++;
                int aDigits = aEnd - aStart;
                int bDigits = bEnd - bStart;
                if (aDigits != bDigits) return Integer.compare(aDigits, bDigits);
                int numberCompared = a.regionMatches(aStart, b, bStart, aDigits) ? 0
                        : a.substring(aStart, aEnd).compareTo(b.substring(bStart, bEnd));
                if (numberCompared != 0) return numberCompared;
                while (ai < a.length() && Character.isDigit(a.charAt(ai))) ai++;
                while (bi < b.length() && Character.isDigit(b.charAt(bi))) bi++;
                continue;
            }
            int charCompared = Character.compare(Character.toLowerCase(ac), Character.toLowerCase(bc));
            if (charCompared != 0) return charCompared;
            ai++;
            bi++;
        }
        return Integer.compare(a.length(), b.length());
    }
}
