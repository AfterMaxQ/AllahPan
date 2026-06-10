package com.allahpan.mbg.model;

import java.util.Date;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * file_favorites
 * @author MyBatis Generator
 * @date 2026-06-07 02:17:12
 */
public class FileFavorite {
    /**
     * 
     * 表字段 : file_favorites.id
     */
    private Long id;

    /**
     * 
     * 表字段 : file_favorites.user_id
     */
    private Long userId;

    /**
     * 
     * 表字段 : file_favorites.file_id
     */
    private Long fileId;

    /**
     * 
     * 表字段 : file_favorites.create_time
     */
    private Date createTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public Long getFileId() {
        return fileId;
    }

    public void setFileId(Long fileId) {
        this.fileId = fileId;
    }

    public Date getCreateTime() {
        return createTime;
    }

    public void setCreateTime(Date createTime) {
        this.createTime = createTime;
    }
}