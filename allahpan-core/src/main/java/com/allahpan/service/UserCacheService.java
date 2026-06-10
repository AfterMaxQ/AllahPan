package com.allahpan.service;

import com.allahpan.mbg.model.User;

/**
 * 用户缓存服务接口
 * 基于 Redis 缓存用户信息，减少数据库查询
 */
public interface UserCacheService {
    /** 根据邮箱从缓存获取用户 */
    User getUser(String email);
    /** 将用户信息写入缓存 */
    void setUser(User user);
    /** 根据用户 ID 删除缓存 */
    void delUser(Long userId);
}
