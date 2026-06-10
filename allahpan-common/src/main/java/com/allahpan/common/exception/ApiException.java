package com.allahpan.common.exception;

import com.allahpan.common.api.ResultCode;

public class ApiException extends RuntimeException {
    private final ResultCode resultCode;

    public ApiException(ResultCode resultCode) {
        super(resultCode.getMessage());
        this.resultCode = resultCode;
    }
    public ApiException(String message) {
        super(message);
        this.resultCode = null;
    }
    public ResultCode getResultCode() {
        return resultCode;
    }
}