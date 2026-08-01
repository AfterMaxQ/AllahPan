package com.allahpan.common.exception;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.log.RequestLogFilter;
import com.allahpan.common.log.StructuredLog;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.validation.BindException;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseBody;

/**
 * 全局异常处理器：统一处理所有接口异常
 */
@ControllerAdvice // 修复1：必须加这个核心注解
public class GlobalExceptionHandler {
    private static final Logger LOG = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /**
     * 处理自定义业务异常 ApiException
     */
    @ResponseBody
    @ExceptionHandler(ApiException.class)
    public CommonResult<Object> handleApiException(ApiException e, HttpServletRequest request){
        String errorId = record(request, e.getResultCode() == null ? "BUSINESS_ERROR" : e.getResultCode().name(), e, false);
        if (e.getResultCode() != null){
            // 有标准错误码，用标准返回
            return CommonResult.failed(e.getResultCode().getMessage(), ErrorResponse.data(errorId));
        }
        return CommonResult.failed(e.getMessage() == null ? "操作失败" : e.getMessage(), ErrorResponse.data(errorId));
    }

    /**
     * 处理 JSON 参数校验异常 (@Valid @RequestBody)
     */
    @ResponseBody
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public CommonResult<Object> handleValidException(MethodArgumentNotValidException e, HttpServletRequest request) {
        BindingResult bindingResult = e.getBindingResult();
        String message = bindingResult.getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .reduce((a, b) -> a + "; " + b)
                .orElse("参数校验失败");
        String errorId = record(request, "VALIDATION_ERROR", e, false);
        return CommonResult.validateFailed(message, ErrorResponse.data(errorId));
    }

    /**
     * 处理表单参数绑定异常
     */
    @ResponseBody
    @ExceptionHandler(BindException.class)
    public CommonResult<Object> handleBindException(BindException e, HttpServletRequest request) {
        String message = e.getBindingResult().getAllErrors().isEmpty()
                ? "参数校验失败" : e.getBindingResult().getAllErrors().get(0).getDefaultMessage();
        String errorId = record(request, "VALIDATION_ERROR", e, false);
        return CommonResult.validateFailed(message, ErrorResponse.data(errorId));
    }

    /**
     * 兜底异常处理器 — 避免未捕获异常以 Spring Boot 默认 500 页面返回
     */
    @ResponseBody
    @ExceptionHandler(Exception.class)
    public CommonResult<Object> handleGeneralException(Exception e, HttpServletRequest request) {
        String errorId = record(request, "INTERNAL_ERROR", e, true);
        return CommonResult.failed("服务器内部错误", ErrorResponse.data(errorId));
    }

    private String record(HttpServletRequest request, String errorCode, Throwable error, boolean stacktrace) {
        String errorId = ErrorResponse.newErrorId();
        request.setAttribute(RequestLogFilter.BUSINESS_STATUS,
                error instanceof ApiException api && api.getResultCode() != null
                        ? api.getResultCode().getCode() : 500);
        request.setAttribute(RequestLogFilter.ERROR_ID, errorId);
        request.setAttribute(RequestLogFilter.ERROR_CODE, errorCode);
        String message = StructuredLog.event("http.request.failed",
                "errorId", errorId, "errorCode", errorCode,
                "path", RequestLogFilter.safeRequestPath(request.getRequestURI()),
                "reason", error.getClass().getSimpleName());
        if (stacktrace) LOG.error(message, error);
        else LOG.info(message);
        return errorId;
    }
}
