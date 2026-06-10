package com.allahpan.security.aspect;

import com.allahpan.security.annotation.CacheException;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.aspectj.lang.reflect.MethodSignature;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

/**
 * Redis 缓存切面
 * 拦截 com.allahpan.service.*CacheService 的方法调用
 * 出现异常时:标注了 @CacheException 的方法直接抛出,其余仅记日志不阻断
 */
@Aspect
@Component
@Order(2)
public class RedisCacheAspect {
    private static final Logger LOGGER = LoggerFactory.getLogger(RedisCacheAspect.class);

    @Pointcut("execution(public * com.allahpan.service.*CacheService.*(..))")
    public void cacheAspect() {}

    @Around("cacheAspect()")
    public Object doAround(ProceedingJoinPoint joinPoint) throws Throwable {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        java.lang.reflect.Method method = signature.getMethod();
        Object result = null;
        try {
            result = joinPoint.proceed();
        } catch (Throwable throwable) {
            // 显式标注 @CacheException 的方法,异常需向上抛出
            if (method.isAnnotationPresent(CacheException.class)) {
                throw throwable;
            }
            // 其余缓存异常仅记录,避免影响主业务
            LOGGER.error("Redis cache error: {}", throwable.getMessage());
        }
        return result;
    }
}
