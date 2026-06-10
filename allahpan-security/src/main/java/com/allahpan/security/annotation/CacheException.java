package com.allahpan.security.annotation;

import java.lang.annotation.*;

/**
 * 标注 Redis 缓存调用中允许抛出的异常
 * 配合 RedisCacheAspect 使用:标注后缓存异常将直接抛出而不被吞掉
 */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface CacheException {
}
