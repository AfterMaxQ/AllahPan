package com.allahpan.service.impl;

import com.allahpan.common.service.RedisService;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.service.UserCacheService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

// 1. 标记为Service层，交给Spring管理
// 2. 实现 UserCacheService 接口（定义了缓存的规范）
@Service
public class UserCacheServiceImpl implements UserCacheService {

    // 注入通用的Redis操作工具类（封装了set/get/delete）
    @Autowired
    private RedisService redisService;
    @Autowired
    private UserMapper userMapper;

    // 从application-dev.yml读取Redis配置
    @Value("${redis.database}")
    private String REDIS_DATABASE;  // 取值：allahpan
    @Value("${redis.key.member}")
    private String REDIS_KEY_MEMBER; // 取值：member
    @Value("${redis.expire.common}")
    private Long REDIS_EXPIRE;       // 取值：86400（24小时）

    // ===================== 核心：生成Redis的唯一Key =====================
    // 拼接规则：库名:键名:邮箱
    // 例子：allahpan:member:family@qq.com
    private String memberKey(String email) {
        return REDIS_DATABASE + ":" + REDIS_KEY_MEMBER + ":" + email;
    }

    // ===================== 1. 从Redis获取用户信息 =====================
    @Override
    public User getUser(String email) {
        // 根据邮箱生成key，从Redis取值，强转为User对象
        return (User) redisService.get(memberKey(email));
    }

    // ===================== 2. 把用户信息存入Redis =====================
    @Override
    public void setUser(User user) {
        // key：拼接后的唯一key
        // value：用户对象（会自动序列化存Redis）
        // 过期时间：24小时
        redisService.set(memberKey(user.getEmail()), user, REDIS_EXPIRE);
    }

    // ===================== 3. 删除Redis用户信息 =====================
    @Override
    public void delUser(Long userId) {
        User user = userMapper.selectByPrimaryKey(userId);
        if (user != null) {
            redisService.del(memberKey(user.getEmail()));
        }
    }
}