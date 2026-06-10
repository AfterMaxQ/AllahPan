package com.allahpan.service;

import java.io.InputStream;
import java.nio.file.Path;

/**
 * 本地文件系统存储服务。
 * 文件直接存储在配置的根目录下，目录结构与前端文件夹树 1:1 对应。
 */
public interface LocalStorageService {

    /** 确保根目录和缩略图子目录存在 */
    void init();

    /** 将相对路径解析为绝对文件系统路径（含路径穿越防护） */
    Path resolve(String relativePath);

    /** 解析缩略图路径 */
    Path resolveThumbnail(String key);

    /** 写入文件到磁盘，自动创建父目录。返回实际写入的完整路径 */
    String store(String relativePath, InputStream data) throws Exception;

    /** 读取文件 */
    InputStream read(String relativePath) throws Exception;

    /** 删除文件 */
    void delete(String relativePath) throws Exception;

    /** 删除缩略图 */
    void deleteThumbnail(String key) throws Exception;

    /** 获取根目录 */
    Path getRootDir();

    /** 获取缩略图子目录 */
    Path getThumbnailDir();

    // ==================== 回收站 ====================

    /** 将本地文件移到回收站目录，保持目录结构 */
    void moveToTrash(String relativePath) throws Exception;

    /** 从回收站恢复文件到原位 */
    void restoreFromTrash(String relativePath) throws Exception;

    /** 从回收站永久删除文件 */
    void deleteFromTrash(String relativePath) throws Exception;

    /** 获取回收站目录 */
    Path getTrashDir();
}
