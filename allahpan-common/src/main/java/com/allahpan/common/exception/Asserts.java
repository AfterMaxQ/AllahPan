package com.allahpan.common.exception;

import com.allahpan.common.api.ResultCode;

public class Asserts {
    public static void fail(String message) {
        throw new ApiException(message);
    }
    public static void fail(ResultCode resultCode) {
        throw new ApiException(resultCode);
    }
    public static void isTrue(boolean condition, String message) {
        if (!condition) throw new ApiException(message);
    }
    public static void isTrue(boolean condition, ResultCode resultCode) {
        if (!condition) throw new ApiException(resultCode);
    }
}