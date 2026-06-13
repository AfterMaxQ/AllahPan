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

    // ===================== 1. 从Redis获取用户信息（读穿透：miss 时回源 MySQL）=====================
    @Override
    public User getUser(String email) {
        User user = (User) redisService.get(memberKey(email));
        if (user == null) {
            // 缓存未命中，回源 MySQL 并回填缓存
            com.allahpan.mbg.model.UserExample example = new com.allahpan.mbg.model.UserExample();
            example.createCriteria().andEmailEqualTo(email).andStatusEqualTo((byte) 1);
            var list = userMapper.selectByExample(example);
            if (!list.isEmpty()) {
                user = list.get(0);
                redisService.set(memberKey(email), user, REDIS_EXPIRE);
            }
        }
        return user;
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