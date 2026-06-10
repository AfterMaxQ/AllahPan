package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.service.RedisService;
import com.allahpan.component.MailService;
import com.allahpan.security.annotation.CacheException;
import com.allahpan.service.AuthCodeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;

@Service
public class AuthCodeServiceImpl implements AuthCodeService {
    @Autowired
    private RedisService redisService;
    @Autowired
    private MailService mailService;

    @Value("${redis.database}")
    private String REDIS_DATABASE;
    @Value("${redis.key.authCode}")
    private String REDIS_KEY_AUTH_CODE;
    @Value("${redis.expire.authCode}")
    private Long REDIS_EXPIRE_AUTH_CODE;

    private static final int SEND_LIMIT_SECONDS = 30;
    private static final int MAX_ATTEMPTS_PER_HOUR = 50;
    private static final int ATTEMPTS_TTL = 3600; // 1小时

    private String codeKey(String email) {
        return REDIS_DATABASE + ":" + REDIS_KEY_AUTH_CODE + ":" + email;
    }
    private String sendLimitKey(String email) {
        return REDIS_DATABASE + ":sendLimit:" + email;
    }
    private String attemptsKey(String email) {
        return REDIS_DATABASE + ":attempts:" + email;
    }

    @Override
    public void sendCode(String email) {
        // ① 检查发送频率
        if (redisService.hasKey(sendLimitKey(email))) {
            Asserts.fail(ResultCode.CODE_SEND_LIMIT);
        }
        // ② 生成 6 位验证码
        String code = String.format("%06d", new SecureRandom().nextInt(1000000));
        // ③ 存入 Redis，5 分钟过期
        redisService.set(codeKey(email), code, REDIS_EXPIRE_AUTH_CODE);
        // ④ 设置 30 秒发送间隔
        redisService.set(sendLimitKey(email), "1", SEND_LIMIT_SECONDS);
        // ⑤ 发送验证码邮件
        mailService.send(email, code);
    }

    @Override
    @CacheException  // Redis 挂了直接抛异常，不降级
    public void verifyCode(String email, String code) {
        // ① 检查小时重试次数
        Object attemptsObj = redisService.get(attemptsKey(email));
        long attempts = attemptsObj instanceof Number ? ((Number) attemptsObj).longValue() : 0;
        if (attempts >= MAX_ATTEMPTS_PER_HOUR) {
            Asserts.fail(ResultCode.TOO_MANY_REQUESTS);
        }
        // ② 比对验证码
        Object stored = redisService.get(codeKey(email));
        if (stored == null) {
            Asserts.fail(ResultCode.CODE_EXPIRED);
        }
        if (!stored.toString().equals(code)) {
            // 失败：递增错误计数并设置过期时间
            redisService.incr(attemptsKey(email), 1);
            redisService.expire(attemptsKey(email), ATTEMPTS_TTL);
            Asserts.fail(ResultCode.CODE_ERROR);
        }
        // ③ 验证成功：删除验证码（不删 attempts，保留小时计数）
        redisService.del(codeKey(email));
    }
}
