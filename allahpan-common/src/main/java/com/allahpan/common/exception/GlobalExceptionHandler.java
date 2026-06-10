package com.allahpan.common.exception;

import com.allahpan.common.api.CommonResult;
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

    /**
     * 处理自定义业务异常 ApiException
     */
    @ResponseBody
    @ExceptionHandler(ApiException.class)
    public CommonResult<Object> handleApiException(ApiException e){
        if (e.getResultCode() != null){
            // 有标准错误码，用标准返回
            return CommonResult.failed(e.getResultCode());
        }
        // 修复2：为空时返回错误信息，而不是空的resultCode
        return CommonResult.failed(e.getMessage());
    }

    /**
     * 处理 JSON 参数校验异常 (@Valid @RequestBody)
     */
    @ResponseBody
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public CommonResult<Object> handleValidException(MethodArgumentNotValidException e) {
        BindingResult bindingResult = e.getBindingResult();
        String message = bindingResult.getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .reduce((a, b) -> a + "; " + b)
                .orElse("参数校验失败");
        return CommonResult.validateFailed(message);
    }

    /**
     * 处理表单参数绑定异常
     */
    @ResponseBody
    @ExceptionHandler(BindException.class)
    public CommonResult<Object> handleBindException(BindException e) {
        return CommonResult.validateFailed(e.getBindingResult().getAllErrors().get(0).getDefaultMessage());
    }

    /**
     * 兜底异常处理器 — 避免未捕获异常以 Spring Boot 默认 500 页面返回
     */
    @ResponseBody
    @ExceptionHandler(Exception.class)
    public CommonResult<Object> handleGeneralException(Exception e) {
        return CommonResult.failed(e.getMessage() != null ? e.getMessage() : "服务器内部错误");
    }
}