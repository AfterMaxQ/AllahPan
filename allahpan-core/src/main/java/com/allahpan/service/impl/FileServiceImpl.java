package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.component.EsIndexService;
import com.allahpan.component.MinioUtil;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.FileService;
import com.github.pagehelper.PageHelper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

@Service
public class FileServiceImpl implements FileService {
    private static final Logger log = LoggerFactory.getLogger(FileServiceImpl.class);
    private static final int MAX_FILE_NAME_LENGTH = 255;
    private static final int MAX_PATH_LENGTH = 500;

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

        // 确定相对路径
        String relativePath = resolveRelativePath(pid, originalName);
        // 解决文件系统冲突
        relativePath = resolveConflict(relativePath, pid);
        String finalName = relativePath.substring(relativePath.lastIndexOf('/') + 1);

        // 上传到 MinIO + 同时计算 MD5
        String contentType = file.getContentType();
        if (contentType == null) contentType = "application/octet-stream";
        String md5;
        try {
            md5 = storeAndCalculateMd5(file.getInputStream(), relativePath,
                    file.getSize(), contentType);
        } catch (Exception e) {
            log.error("上传到 MinIO 失败: {}", relativePath, e);
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
                dup.setIsFolder((byte) 0);
                dup.setProcessStatus((byte) 3);
                dup.setCreateTime(new Date());
                dup.setFilePath(buildPath(finalName, pid));
                try {
                    fileMapper.insert(dup);
                } catch (Exception e) {
                    log.error("秒传记录插入失败，清理 MinIO: {}", relativePath, e);
                    try { minioUtil.removeObject(relativePath); } catch (Exception ex) { log.warn("清理失败", ex); }
                    Asserts.fail("文件保存失败");
                }
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
        record.setFileType(detectFileType(contentType));
        record.setCreateTime(new Date());
        record.setFilePath(buildPath(finalName, pid));
        try {
            fileMapper.insert(record);
        } catch (Exception e) {
            log.error("文件记录插入失败，清理 MinIO: {}", relativePath, e);
            try { minioUtil.removeObject(relativePath); } catch (Exception ex) { log.warn("清理失败", ex); }
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
        example.setOrderByClause("is_folder DESC, FIELD(file_type, 'IMAGE', 'DOCUMENT', 'OTHER'), file_name REGEXP '^[0-9]' DESC, CAST(file_name AS UNSIGNED), file_name ASC");
        return fileMapper.selectByExample(example);
    }

    @Override
    public List<File> getDirectoryTree(Long folderId) {
        var list = new java.util.ArrayList<File>();
        Long current = folderId;
        while (current != null && current > 0) {
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
            log.warn("无法将文件移至回收站: {} (id={})", file.getStorageKey(), file.getId(), e);
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
                log.warn("无法将子文件移至回收站，MinIO 对象保留在 files bucket: {} (id={})", child.getStorageKey(), child.getId(), e);
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

    /** 统计所有记录（含已删除）共享同一 storageKey 的数量 */
    private long countAllRefs(String storageKey, Long excludeId) {
        if (storageKey == null) return 0;
        FileExample example = new FileExample();
        example.createCriteria()
                .andStorageKeyEqualTo(storageKey)
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
    private void restoreFromTrash(File file) {
        if (file.getStorageKey() == null) return;
        // 非文件夹 → 从 trash bucket 恢复到 files bucket
        if (file.getIsFolder() == null || file.getIsFolder() != 1) {
            try {
                // 如果已有其他活跃记录引用同一 storageKey，对象已在 files bucket 中，无需恢复
                if (countActiveRefs(file.getStorageKey(), file.getId()) == 0) {
                    minioUtil.restoreFromTrash(file.getStorageKey());
                    minioUtil.removeFromTrash(file.getStorageKey());
                }
            } catch (Exception e) {
                log.warn("从 MinIO 回收站恢复失败: {}", file.getStorageKey(), e);
            }
        }
    }

    @Override
    public File getFileById(Long fileId) {
        return fileMapper.selectByPrimaryKey(fileId);
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
        return fileMapper.selectByExample(example);
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
            log.error("从 MinIO 回收站恢复失败，回滚 DB: {} (id={})", file.getStorageKey(), fileId, e);
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
                log.error("子文件从 MinIO 回收站恢复失败，回滚 DB: {} (id={})", child.getStorageKey(), child.getId(), e);
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
    public void permanentDelete(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        Asserts.isTrue(file.getDeleteTime() != null, "只能永久删除垃圾站中的文件");

        // MySQL 优先：先删除 DB 记录，再清理 MinIO 对象
        // MinIO 清理失败仅记 warning，由定时孤儿扫描兜底
        fileMapper.deleteByPrimaryKey(fileId);

        // 递归删除子节点
        if (file.getIsFolder() == 1) {
            permanentDeleteChildren(fileId);
        }

        // 清理 MinIO 对象（DB 记录已删除，清理失败不影响用户）
        if (file.getStorageKey() != null) {
            if (file.getIsFolder() == null || file.getIsFolder() != 1) {
                esIndexService.delete(fileId);
            }
            try {
                if (countAllRefs(file.getStorageKey(), file.getId()) == 0) {
                    minioUtil.removeFromTrash(file.getStorageKey());
                }
            } catch (Exception e) {
                log.warn("从 MinIO 回收站删除失败: {}", file.getStorageKey(), e);
            }
        }
        if (file.getThumbnailKey() != null) {
            try {
                minioUtil.removeThumbnail(file.getThumbnailKey());
            } catch (Exception e) {
                log.warn("删除 MinIO 缩略图失败: {}", file.getThumbnailKey(), e);
            }
        }
    }

    private void permanentDeleteChildren(Long folderId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId);
        var children = fileMapper.selectByExample(example);
        for (File child : children) {
            permanentDelete(child.getId());
        }
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
     * 递归重建文件夹下所有子孙节点的 filePath 和 storageKey
     */
    private void rebuildDescendantPaths(Long folderId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId).andDeleteTimeIsNull();
        List<File> children = fileMapper.selectByExample(example);
        for (File child : children) {
            child.setFilePath(buildPath(child.getFileName(), child.getParentId()));

            String oldKey = child.getStorageKey();
            if (oldKey != null) {
                String newKey = resolveRelativePath(child.getParentId(), child.getFileName());
                if (!newKey.equals(oldKey)) {
                    child.setStorageKey(newKey);
                }
            }

            // MySQL 优先：先更新 DB
            fileMapper.updateByPrimaryKeySelective(child);

            // MinIO 随后：复制到新 key + 删除旧 key（仅非文件夹），失败则回滚该子节点 DB
            if (oldKey != null && !oldKey.equals(child.getStorageKey())) {
                if (child.getIsFolder() == null || child.getIsFolder() != 1) {
                    try {
                        minioUtil.copyObject(oldKey, child.getStorageKey());
                        minioUtil.removeObject(oldKey);
                    } catch (Exception e) {
                        log.error("MinIO 重命名子孙文件失败，回滚 DB: {} -> {}", oldKey, child.getStorageKey(), e);
                        // 回滚 MySQL 对该子节点的修改
                        child.setStorageKey(oldKey);
                        fileMapper.updateByPrimaryKeySelective(child);
                    }
                }
            }

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

    /**
     * 解决文件名冲突：如果 MinIO 中已存在同名对象，追加序号
     */
    private String resolveConflict(String relativePath, Long parentId) {
        if (!minioUtil.objectExists(relativePath)
                && !activeNameExists(parentId, relativePath.substring(relativePath.lastIndexOf('/') + 1))) {
            return relativePath;
        }

        int lastSlash = relativePath.lastIndexOf('/');
        String dir = lastSlash >= 0 ? relativePath.substring(0, lastSlash + 1) : "";
        String baseName = relativePath.substring(lastSlash + 1);
        String nameBody = baseName;
        String ext = "";
        int dotIdx = baseName.lastIndexOf('.');
        if (dotIdx > 0) {
            nameBody = baseName.substring(0, dotIdx);
            ext = baseName.substring(dotIdx);
        }

        int counter = 1;
        String newPath;
        do {
            String newName = nameBody + " (" + counter + ")" + ext;
            newPath = dir + newName;
            counter++;
        } while (minioUtil.objectExists(newPath)
                || activeNameExists(parentId, newPath.substring(newPath.lastIndexOf('/') + 1)));

        return newPath;
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

        // 保存旧值用于 MinIO 失败时回滚
        String oldKey = file.getStorageKey();
        String oldName = file.getFileName();
        String oldPath = file.getFilePath();

        // MySQL 优先：先更新 DB storageKey + fileName + filePath
        if (oldKey != null) {
            String newKey = resolveRelativePath(parentId, newName);
            if (!newKey.equals(oldKey)) {
                file.setStorageKey(newKey);
            }
        }
        file.setFileName(newName);
        file.setFilePath(buildPath(newName, file.getParentId()));
        fileMapper.updateByPrimaryKeySelective(file);

        // MinIO 随后：复制到新 key + 删除旧 key（仅非文件夹）
        if (oldKey != null && file.getStorageKey() != null && !file.getStorageKey().equals(oldKey)) {
            if (file.getIsFolder() == null || file.getIsFolder() != 1) {
                try {
                    minioUtil.copyObject(oldKey, file.getStorageKey());
                    minioUtil.removeObject(oldKey);
                } catch (Exception e) {
                    log.error("MinIO 重命名失败，回滚 DB: {} -> {}", oldKey, file.getStorageKey(), e);
                    // 回滚 MySQL
                    file.setStorageKey(oldKey);
                    file.setFileName(oldName);
                    file.setFilePath(oldPath);
                    fileMapper.updateByPrimaryKeySelective(file);
                    Asserts.fail("文件重命名失败");
                }
            }
        }

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

        // 保存旧值用于 MinIO 失败时回滚
        String oldKey = file.getStorageKey();
        Long oldParentId = file.getParentId();
        String oldPath = file.getFilePath();

        // MySQL 优先：先更新 DB storageKey + parentId + filePath
        if (file.getStorageKey() != null) {
            String newKey = resolveRelativePath(newParentId, file.getFileName());
            file.setStorageKey(newKey);
        }
        file.setParentId(newParentId);
        file.setFilePath(buildPath(file.getFileName(), newParentId));
        fileMapper.updateByPrimaryKeySelective(file);

        // MinIO 随后：复制到新 key + 删除旧 key（仅非文件夹）
        if (oldKey != null && file.getStorageKey() != null && !file.getStorageKey().equals(oldKey)) {
            if (file.getIsFolder() == null || file.getIsFolder() != 1) {
                try {
                    minioUtil.copyObject(oldKey, file.getStorageKey());
                    minioUtil.removeObject(oldKey);
                } catch (Exception e) {
                    log.error("MinIO 移动失败，回滚 DB: {} -> {}", oldKey, file.getStorageKey(), e);
                    // 回滚 MySQL
                    file.setStorageKey(oldKey);
                    file.setParentId(oldParentId);
                    file.setFilePath(oldPath);
                    fileMapper.updateByPrimaryKeySelective(file);
                    Asserts.fail("文件移动失败");
                }
            }
        }

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
    public Long getFolderSize(Long folderId) {
        Long size = fileMapper.getFolderSize(folderId);
        return size != null ? size : 0L;
    }

    @Override
    public int emptyTrash() {
        FileExample example = new FileExample();
        example.createCriteria().andDeleteTimeIsNotNull();
        List<File> trashFiles = fileMapper.selectByExample(example);
        int count = 0;
        for (File f : trashFiles) {
            try {
                permanentDelete(f.getId());
                count++;
            } catch (Exception e) {
                log.warn("清空垃圾站失败: fileId={}", f.getId(), e);
            }
        }
        return count;
    }
}
