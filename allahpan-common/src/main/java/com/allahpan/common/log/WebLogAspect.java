package com.allahpan.common.log;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import com.allahpan.common.domain.WebLog;

import jakarta.servlet.http.HttpServletRequest;

/** Controller 请求日志切面，统一记录所有 API 请求 */
@Aspect
@Component
public class WebLogAspect {

    private static final Logger log = LoggerFactory.getLogger(WebLogAspect.class);

    /** 定义切入点：com.allahpan 包下所有 controller 包的 public 方法 */
    @Pointcut("execution(public * com.allahpan..controller..*.*(..))")
    public void controllerPointcut() {}

    /** 拦截 Controller 方法，记录请求和响应信息 */
    @Around("controllerPointcut()")
    public Object doAround(ProceedingJoinPoint joinPoint) throws Throwable {
        long startTime = System.currentTimeMillis();
        WebLog webLog = new WebLog();

        ServletRequestAttributes attributes =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attributes != null) {
            HttpServletRequest request = attributes.getRequest();
            webLog.setUrl(request.getRequestURL().toString());
            webLog.setMethod(request.getMethod());
            webLog.setIp(request.getRemoteAddr());
        }
        webLog.setClassName(joinPoint.getTarget().getClass().getName());
        webLog.setMethodName(joinPoint.getSignature().getName());
        webLog.setArgs(joinPoint.getArgs());

        Object result;
        try {
            result = joinPoint.proceed();
            webLog.setResult(result);
            webLog.setSpendTime(System.currentTimeMillis() - startTime);
            log.info("{}", webLog);
        } catch (Throwable e) {
            webLog.setSpendTime(System.currentTimeMillis() - startTime);
            webLog.setErrorMessage(e.getMessage());
            log.error("{}", webLog);
            throw e;
        }
        return result;
    }
}
