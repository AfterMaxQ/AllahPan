package com.allahpan.common.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

/**
 * 基于 Redis Bitmap 的布隆过滤器
 * 用于防止缓存穿透：查询不存在的用户 email 时，直接拦截，不穿透到 MySQL
 *
 * 参数设计（预期 10000 个元素，误判率 1%）：
 * - 位数组大小 m ≈ 95850 bits ≈ 12KB
 * - 哈希函数数量 k ≈ 7
 */
@Service
public class BloomFilterService {

    private static final Logger LOGGER = LoggerFactory.getLogger(BloomFilterService.class);

    private static final String BLOOM_KEY_SUFFIX = "bloom:user:email";
    private static final long EXPECTED_INSERTIONS = 10000;
    private static final double FPP = 0.01;
    // m = -n*ln(p) / (ln2)^2 ≈ 95850
    private static final long BIT_SIZE = 95850;
    // k = (m/n)*ln2 ≈ 7
    private static final int HASH_FUNCTIONS = 7;

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Value("${redis.database}")
    private String REDIS_DATABASE;

    private String bloomKey() {
        return REDIS_DATABASE + ":" + BLOOM_KEY_SUFFIX;
    }

    /**
     * 添加元素到布隆过滤器
     */
    public void add(String value) {
        long[] offsets = getOffsets(value);
        for (long offset : offsets) {
            redisTemplate.opsForValue().setBit(bloomKey(), offset, true);
        }
    }

    /**
     * 判断元素是否可能存在
     * @return true=可能存在（有误判率），false=一定不存在
     */
    public boolean mightContain(String value) {
        try {
            long[] offsets = getOffsets(value);
            for (long offset : offsets) {
                Boolean bit = redisTemplate.opsForValue().getBit(bloomKey(), offset);
                if (!Boolean.TRUE.equals(bit)) {
                    return false;
                }
            }
            return true;
        } catch (Exception e) {
            // Redis 异常时降级：跳过布隆过滤，走后续缓存/DB 查询
            LOGGER.error("BloomFilter check failed, fallback to cache/DB: {}", e.getMessage());
            return true;
        }
    }

    /**
     * 重置布隆过滤器（启动时重建使用）
     */
    public void reset() {
        redisTemplate.delete(bloomKey());
    }

    /**
     * 使用 SHA-256 生成多个哈希偏移量
     * SHA-256 产生 32 字节，可拆出 7 个 4 字节整数作为 7 个哈希值
     */
    private long[] getOffsets(String value) {
        long[] offsets = new long[HASH_FUNCTIONS];
        byte[] hashBytes = sha256(value.getBytes(StandardCharsets.UTF_8));
        for (int i = 0; i < HASH_FUNCTIONS; i++) {
            int start = i * 4;
            long hash = ((hashBytes[start] & 0xFFL) << 24)
                      | ((hashBytes[start + 1] & 0xFFL) << 16)
                      | ((hashBytes[start + 2] & 0xFFL) << 8)
                      | (hashBytes[start + 3] & 0xFFL);
            offsets[i] = Math.abs(hash % BIT_SIZE);
        }
        return offsets;
    }

    private byte[] sha256(byte[] input) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(input);
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 not available", e);
        }
    }
}
