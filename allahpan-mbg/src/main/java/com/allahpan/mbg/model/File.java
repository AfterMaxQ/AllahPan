package com.allahpan.mbg.model;

import java.util.Date;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * files
 * @author MyBatis Generator
 * @date 2026-06-07 02:17:12
 */
public class File {
    /**
     * 
     * 表字段 : files.id
     */
    private Long id;

    /**
     * 上传者
     * 表字段 : files.uploader_id
     */
    private Long uploaderId;

    /**
     * 父目录ID，0=根目录
     * 表字段 : files.parent_id
     */
    private Long parentId;

    /**
     * 文件名
     * 表字段 : files.file_name
     */
    private String fileName;

    /**
     * 虚拟路径
     * 表字段 : files.file_path
     */
    private String filePath;

    /**
     * MinIO 存储 key
     * 表字段 : files.storage_key
     */
    private String storageKey;

    /**
     * FOLDER/IMAGE/VIDEO/DOCUMENT/OTHER
     * 表字段 : files.file_type
     */
    private String fileType;

    /**
     * 文件大小（字节）
     * 表字段 : files.file_size
     */
    private Long fileSize;

    /**
     * MIME 类型
     * 表字段 : files.content_type
     */
    private String contentType;

    /**
     * 缩略图 MinIO key
     * 表字段 : files.thumbnail_key
     */
    private String thumbnailKey;

    /**
     * 0=文件 1=文件夹
     * 表字段 : files.is_folder
     */
    private Byte isFolder;

    /**
     * 0=待处理 1=缩略图完成 2=文本提取完成 3=索引完成 -1=失败
     * 表字段 : files.process_status
     */
    private Byte processStatus;

    /**
     * 文件 MD5
     * 表字段 : files.md5
     */
    private String md5;

    /**
     * 
     * 表字段 : files.create_time
     */
    private Date createTime;

    /**
     * 
     * 表字段 : files.update_time
     */
    private Date updateTime;

    /**
     * 软删除时间
     * 表字段 : files.delete_time
     */
    private Date deleteTime;

    /**
     * PDF 解析/OCR 提取的文本
     * 表字段 : files.origin_text
     */
    private String originText;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getUploaderId() {
        return uploaderId;
    }

    public void setUploaderId(Long uploaderId) {
        this.uploaderId = uploaderId;
    }

    public Long getParentId() {
        return parentId;
    }

    public void setParentId(Long parentId) {
        this.parentId = parentId;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }

    public String getFilePath() {
        return filePath;
    }

    public void setFilePath(String filePath) {
        this.filePath = filePath;
    }

    public String getStorageKey() {
        return storageKey;
    }

    public void setStorageKey(String storageKey) {
        this.storageKey = storageKey;
    }

    public String getFileType() {
        return fileType;
    }

    public void setFileType(String fileType) {
        this.fileType = fileType;
    }

    public Long getFileSize() {
        return fileSize;
    }

    public void setFileSize(Long fileSize) {
        this.fileSize = fileSize;
    }

    public String getContentType() {
        return contentType;
    }

    public void setContentType(String contentType) {
        this.contentType = contentType;
    }

    public String getThumbnailKey() {
        return thumbnailKey;
    }

    public void setThumbnailKey(String thumbnailKey) {
        this.thumbnailKey = thumbnailKey;
    }

    public Byte getIsFolder() {
        return isFolder;
    }

    public void setIsFolder(Byte isFolder) {
        this.isFolder = isFolder;
    }

    public Byte getProcessStatus() {
        return processStatus;
    }

    public void setProcessStatus(Byte processStatus) {
        this.processStatus = processStatus;
    }

    public String getMd5() {
        return md5;
    }

    public void setMd5(String md5) {
        this.md5 = md5;
    }

    public Date getCreateTime() {
        return createTime;
    }

    public void setCreateTime(Date createTime) {
        this.createTime = createTime;
    }

    public Date getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(Date updateTime) {
        this.updateTime = updateTime;
    }

    public Date getDeleteTime() {
        return deleteTime;
    }

    public void setDeleteTime(Date deleteTime) {
        this.deleteTime = deleteTime;
    }

    public String getOriginText() {
        return originText;
    }

    public void setOriginText(String originText) {
        this.originText = originText;
    }
}