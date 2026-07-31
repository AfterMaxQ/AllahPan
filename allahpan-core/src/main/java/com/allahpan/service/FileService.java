package com.allahpan.service;

import java.util.List;
import java.util.Map;

import com.allahpan.mbg.model.File;

import org.springframework.web.multipart.MultipartFile;

public interface FileService {
    File upload(MultipartFile file, Long parentId);
    File createFolder(String folderName, Long parentId);
    List<File> listFiles(Long parentId);
    List<File> getDirectoryTree(Long folderId);
    void deleteFile(Long fileId);
    File getFileById(Long fileId);

    List<File> listTrash(int pageNum, int pageSize);
    void restoreFile(Long fileId);
    void permanentDelete(Long fileId);

    File renameFile(Long fileId, String newName);
    File moveFile(Long fileId, Long targetParentId);
    Map<String, Object> batchDelete(List<Long> fileIds);

    /**
     * 递归计算文件夹下所有子孙文件的总大小（字节）
     */
    Long getFolderSize(Long folderId);

    /**
     * 一键清空垃圾站，返回删除的文件数量
     */
    int emptyTrash();

}
