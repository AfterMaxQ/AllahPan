package com.allahpan.service.impl;

import java.util.concurrent.ThreadLocalRandom;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.allahpan.common.service.BloomFilterService;
import com.allahpan.common.service.RedisService;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.service.UserCacheService;

@Service
public class UserCacheServiceImpl implements UserCacheService {

    @Autowired
    private RedisService redisService;
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private BloomFilterService bloomFilterService;

    @Value("${redis.database}")
    private String REDIS_DATABASE;
    @Value("${redis.key.member}")
    private String REDIS_KEY_MEMBER;
    @Value("${redis.expire.common}")
    private Long REDIS_EXPIRE;

    // TTL 随机偏移范围（0~300秒），防止大量 key 同时过期导致缓存雪崩
    private static final int TTL_RANDOM_RANGE = 300;

    private String memberKey(String email) {
        return REDIS_DATABASE + ":" + REDIS_KEY_MEMBER + ":" + email;
    }

    /**
     * 计算带随机偏移的 TTL，打散过期时间
     * 例：基础 86400s + 随机 0~300s = 86400~86700s
     */
    private long randomTtl() {
        return REDIS_EXPIRE + ThreadLocalRandom.current().nextInt(TTL_RANDOM_RANGE);
    }

    // ===================== 1. 从Redis获取用户信息（布隆过滤 + 读穿透）=====================
    @Override
    public User getUser(String email) {
        // 第一层：布隆过滤器判断 email 是否可能存在，不存在则直接返回 null
        if (!bloomFilterService.mightContain(email)) {
            return null;
        }
        // 第二层：查 Redis 缓存
        User user = (User) redisService.get(memberKey(email));
        if (user == null) {
            // 第三层：缓存未命中，回源 MySQL 并回填缓存
            com.allahpan.mbg.model.UserExample example = new com.allahpan.mbg.model.UserExample();
            example.createCriteria().andEmailEqualTo(email).andStatusEqualTo((byte) 1);
            var list = userMapper.selectByExample(example);
            if (!list.isEmpty()) {
                user = list.get(0);
                redisService.set(memberKey(email), user, randomTtl());
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
        redisService.set(memberKey(user.getEmail()), user, randomTtl());
    }

    // ===================== 3. 删除Redis用户信息 =====================
    @Override
    public void delUser(Long userId) {
        User user = userMapper.selectByPrimaryKey(userId);
        if (user != null) {
            redisService.del(memberKey(user.getEmail()));
        }
    }

    // ===================== 4. 根据邮箱删除缓存（调用方已有 email，无需再查 DB）=====================
    @Override
    public void delUserByEmail(String email) {
        redisService.del(memberKey(email));
    }
}