package com.allahpan.mbg.model;

import java.util.Date;
import lombok.Data;
import lombok.EqualsAndHashCode;

/**
 * users
 * @author MyBatis Generator
 * @date 2026-06-07 02:17:12
 */
public class User {
    /**
     * 
     * 表字段 : users.id
     */
    private Long id;

    /**
     * 邮箱（登录凭证）
     * 表字段 : users.email
     */
    private String email;

    /**
     * BCrypt 密文，首次登录前为 NULL
     * 表字段 : users.password
     */
    private String password;

    /**
     * 昵称
     * 表字段 : users.nickname
     */
    private String nickname;

    /**
     * 头像 MinIO key
     * 表字段 : users.avatar_url
     */
    private String avatarUrl;

    /**
     * 0=禁用 1=正常
     * 表字段 : users.status
     */
    private Byte status;

    /**
     * 0=已设密码 1=首次登录
     * 表字段 : users.first_login
     */
    private Byte firstLogin;

    /**
     * 
     * 表字段 : users.last_login_time
     */
    private Date lastLoginTime;

    /**
     * 
     * 表字段 : users.create_time
     */
    private Date createTime;

    /**
     * 
     * 表字段 : users.update_time
     */
    private Date updateTime;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getNickname() {
        return nickname;
    }

    public void setNickname(String nickname) {
        this.nickname = nickname;
    }

    public String getAvatarUrl() {
        return avatarUrl;
    }

    public void setAvatarUrl(String avatarUrl) {
        this.avatarUrl = avatarUrl;
    }

    public Byte getStatus() {
        return status;
    }

    public void setStatus(Byte status) {
        this.status = status;
    }

    public Byte getFirstLogin() {
        return firstLogin;
    }

    public void setFirstLogin(Byte firstLogin) {
        this.firstLogin = firstLogin;
    }

    public Date getLastLoginTime() {
        return lastLoginTime;
    }

    public void setLastLoginTime(Date lastLoginTime) {
        this.lastLoginTime = lastLoginTime;
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
}