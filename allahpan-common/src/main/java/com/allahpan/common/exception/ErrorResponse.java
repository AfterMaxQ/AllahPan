package com.allahpan.common.exception;

import com.allahpan.common.log.LogContext;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Client-safe diagnostics for locating a server-side error. */
public final class ErrorResponse {
    private ErrorResponse() {}

    public static String newErrorId() {
        return "err-" + UUID.randomUUID();
    }

    public static Map<String, String> data(String errorId) {
        Map<String, String> data = new LinkedHashMap<>();
        data.put("requestId", LogContext.requestId() == null ? "" : LogContext.requestId());
        data.put("errorId", errorId);
        return data;
    }
}
