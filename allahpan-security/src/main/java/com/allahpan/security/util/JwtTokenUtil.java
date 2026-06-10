package com.allahpan.security.util;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import cn.hutool.core.date.DateUtil;
import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import cn.hutool.jwt.signers.JWTSigner;
import cn.hutool.jwt.signers.JWTSignerUtil;

/**
 * JWT Token 工具类
 * 负责 Token 的生成、验证、刷新和解析
 */
@Component
public class JwtTokenUtil {
    /** Token 载荷中的用户 ID 字段名 */
    private static final String CLAIM_USER_ID = "user_id";
    /** Token 载荷中的密码设置状态字段名 */
    private static final String CLAIM_HAS_PASSWORD = "hasPassword";
    /** Token 载荷中的创建时间字段名 */
    private static final String CLAIM_CREATED = "created";

    /** JWT 签名密钥 */
    @Value("${jwt.secret}")
    private String secret;
    /** Token 有效期（秒） */
    @Value("${jwt.expiration}")
    private Long expiration;
    /** Token 前缀（如 "Bearer "） */
    @Value("${jwt.tokenHead}")
    private String tokenHead;

    /**
     * 验证签名并解析 Token。签名无效返回 null。
     */
    private JWT parseVerifiedToken(String token) {
        if (!JWTUtil.verify(token, JWTSignerUtil.hs512(secret.getBytes()))) {
            return null;
        }
        return JWTUtil.parseToken(token);
    }

    /**
     * 生成 JWT Token
     * @param userId 用户 ID
     * @param email 邮箱（作为 subject）
     * @param hasPassword 是否已设置密码
     */
    public String generateToken(Long userId, String email, boolean hasPassword) {
        Map<String, Object> claims = new HashMap<>();
        claims.put(CLAIM_USER_ID, userId);
        claims.put(CLAIM_HAS_PASSWORD, hasPassword);
        claims.put(CLAIM_CREATED, new Date());

        return generateToken(claims, email);
    }

    /**
     * 内部方法：根据载荷生成 Token
     */
    private String generateToken(Map<String, Object> claims, String subject) {
        JWTSigner signer = JWTSignerUtil.hs512(secret.getBytes());
        return JWT.create()
                .addHeaders(Map.of("typ", "JWT", "alg", "HS512"))
                .addPayloads(claims)
                .setPayload("sub", subject)
                .setExpiresAt(DateUtil.offsetSecond(new Date(), expiration.intValue()))
                .setSigner(signer)
                .sign();
    }

    /**
     * 验证 Token 是否有效
     * @param token JWT Token
     * @param email 邮箱（需与 subject 匹配）
     */
    public boolean validateToken(String token, String email) {
        JWT jwt = parseVerifiedToken(token);
        if (jwt == null) return false;
        String sub = (String) jwt.getPayload().getClaim("sub");
        return sub != null && sub.equals(email) && !isTokenExpired(token);
    }

    /**
     * 判断 Token 是否已过期
     * Hutool JWT 中 exp 可能是 Long(Unix 秒) 或 Date，需兼容处理
     */
    private boolean isTokenExpired(String token) {
        try {
            JWT jwt = parseVerifiedToken(token);
            if (jwt == null) return true;
            Object expObj = jwt.getPayload().getClaim("exp");
            if (expObj == null) return true;
            Date exp;
            if (expObj instanceof Date) {
                exp = (Date) expObj;
            } else if (expObj instanceof Number) {
                // exp 存储为 Unix 时间戳（秒）
                exp = new Date(((Number) expObj).longValue() * 1000);
            } else {
                return true;
            }
            return exp.before(new Date());
        } catch (Exception e) {
            return true;
        }
    }

    /**
     * 从 Token 中获取 subject（邮箱）
     */
    public String getSubjectFromToken(String token) {
        try {
            JWT jwt = parseVerifiedToken(token);
            return jwt != null ? (String) jwt.getPayload().getClaim("sub") : null;
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 判断 Token 是否可以刷新（未过期）
     */
    public boolean canRefresh(String token) {
        return !isTokenExpired(token);
    }

    /**
     * 刷新 Token
     * 距过期 < 30 分钟才允许刷新，否则返回 null
     */
    public String refreshToken(String token) {
        JWT jwt = parseVerifiedToken(token);
        if (jwt == null) return null;
        Date created = (Date) jwt.getPayload().getClaim(CLAIM_CREATED);
        // 距过期 < 30 分钟才刷新
        if (created != null && System.currentTimeMillis() - created.getTime() <
                (expiration - 1800) * 1000) {
            return null;
        }
        String email = (String) jwt.getPayload().getClaim("sub");
        Object uidObj = jwt.getPayload().getClaim(CLAIM_USER_ID);
        Long userId = uidObj instanceof Number ? ((Number) uidObj).longValue() : null;
        Object hpObj = jwt.getPayload().getClaim(CLAIM_HAS_PASSWORD);
        boolean hasPassword = hpObj instanceof Boolean ? (Boolean) hpObj : false;
        return generateToken(userId, email, hasPassword);
    }

    /**
     * 从 Token 中获取是否已设置密码
     */
    public boolean getHasPasswordFromToken(String token) {
        try {
            JWT jwt = parseVerifiedToken(token);
            if (jwt == null) return false;
            Object val = jwt.getPayload().getClaim(CLAIM_HAS_PASSWORD);
            return val instanceof Boolean ? (Boolean) val : false;
        } catch (Exception e) {
            return false;
        }
    }

    /**
     * 从 Token 中获取用户 ID
     */
    public Long getUserIdFromToken(String token) {
        try {
            JWT jwt = parseVerifiedToken(token);
            if (jwt == null) return null;
            Object userId = jwt.getPayload().getClaim(CLAIM_USER_ID);
            return userId instanceof Number ? ((Number) userId).longValue() : null;
        } catch (Exception e) {
            return null;
        }
    }
}