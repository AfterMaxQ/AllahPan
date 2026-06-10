package com.allahpan.common.api;


public enum ResultCode {
    SUCCESS(200, "操作成功"),
    FAILED(500, "操作失败"),
    VALIDATE_FAILED(404, "参数校验失败"),
    UNAUTHORIZED(401, "暂未登录或token过期"),
    FORBIDDEN(403, "没有权限访问"),
    TOO_MANY_REQUESTS(429, "请求频率过快，请稍后重试"),
    CODE_SEND_LIMIT(429, "验证码发送次数超过限制,请30s后重试"),
    CODE_ERROR(400, "验证码错误"),
    CODE_EXPIRED(400, "验证码过期"),
    ;

    private final long code;
    private final String message;

    ResultCode(long code, String message) {
        this.code = code;
        this.message = message;
    }

    public long getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}