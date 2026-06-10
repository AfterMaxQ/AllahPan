package com.allahpan.service.impl;

import com.allahpan.service.LocalStorageService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.FileInputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;

public class LocalStorageServiceImpl implements LocalStorageService {

    private static final Logger log = LoggerFactory.getLogger(LocalStorageServiceImpl.class);

    private final Path rootDir;
    private final Path thumbnailDir;
    private final Path trashDir;

    public LocalStorageServiceImpl(String rootPath, String thumbnailSubdir) {
        this.rootDir = Paths.get(rootPath).toAbsolutePath().normalize();
        this.thumbnailDir = this.rootDir.resolve(thumbnailSubdir);
        this.trashDir = this.rootDir.resolve(".trash");
    }

    @Override
    public void init() {
        try {
            Files.createDirectories(rootDir);
            Files.createDirectories(thumbnailDir);
            Files.createDirectories(trashDir);
            log.info("本地存储已就绪: root={}, thumbnail={}, trash={}", rootDir, thumbnailDir, trashDir);
        } catch (Exception e) {
            throw new RuntimeException("无法创建本地存储目录: " + rootDir, e);
        }
    }

    @Override
    public Path resolve(String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            throw new IllegalArgumentException("相对路径不能为空");
        }
        Path resolved = rootDir.resolve(relativePath).normalize();
        if (!resolved.startsWith(rootDir)) {
            throw new SecurityException("路径穿越检测: " + relativePath);
        }
        return resolved;
    }

    @Override
    public Path resolveThumbnail(String key) {
        if (key == null || key.isBlank()) {
            throw new IllegalArgumentException("缩略图 key 不能为空");
        }
        Path resolved = thumbnailDir.resolve(key).normalize();
        if (!resolved.startsWith(thumbnailDir)) {
            throw new SecurityException("缩略图路径穿越检测: " + key);
        }
        return resolved;
    }

    @Override
    public String store(String relativePath, InputStream data) throws Exception {
        Path target = resolve(relativePath);
        Files.createDirectories(target.getParent());
        Files.copy(data, target, StandardCopyOption.REPLACE_EXISTING);
        log.debug("文件已写入: {}", target);
        return target.toString();
    }

    @Override
    public InputStream read(String relativePath) throws Exception {
        Path path = resolve(relativePath);
        return new FileInputStream(path.toFile());
    }

    @Override
    public void delete(String relativePath) throws Exception {
        Path path = resolve(relativePath);
        Files.deleteIfExists(path);
        log.debug("文件已删除: {}", path);
    }

    @Override
    public void deleteThumbnail(String key) throws Exception {
        Path path = resolveThumbnail(key);
        Files.deleteIfExists(path);
        log.debug("缩略图已删除: {}", path);
    }

    @Override
    public Path getRootDir() {
        return rootDir;
    }

    @Override
    public Path getThumbnailDir() {
        return thumbnailDir;
    }

    // ==================== 回收站 ====================

    @Override
    public void moveToTrash(String relativePath) throws Exception {
        Path src = resolve(relativePath);
        if (!Files.exists(src)) {
            throw new java.nio.file.NoSuchFileException("源文件不存在: " + src);
        }
        Path dst = trashDir.resolve(relativePath);
        Files.createDirectories(dst.getParent());
        Files.move(src, dst, StandardCopyOption.REPLACE_EXISTING);
        log.debug("已移至本地回收站: {} -> {}", relativePath, dst);
    }

    @Override
    public void restoreFromTrash(String relativePath) throws Exception {
        Path src = trashDir.resolve(relativePath);
        if (!Files.exists(src)) return;
        Path dst = resolve(relativePath);
        Files.createDirectories(dst.getParent());
        Files.move(src, dst, StandardCopyOption.REPLACE_EXISTING);
        log.debug("已从本地回收站恢复: {}", relativePath);
    }

    @Override
    public void deleteFromTrash(String relativePath) throws Exception {
        Path path = trashDir.resolve(relativePath);
        Files.deleteIfExists(path);
        log.debug("已从本地回收站永久删除: {}", relativePath);
    }

    @Override
    public Path getTrashDir() {
        return trashDir;
    }
}
