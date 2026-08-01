package com.allahpan.common.log;

import org.slf4j.MDC;

import java.util.UUID;

/**
 * MDC keys and small helpers shared by HTTP, scheduled and asynchronous work.
 * Values placed here are rendered by the application's logback configuration.
 */
public final class LogContext {
    public static final String REQUEST_ID = "requestId";
    public static final String OPERATION_ID = "operationId";
    public static final String JOB_ID = "jobId";
    public static final String USER_ID = "userId";

    private LogContext() {}

    public static String requestId() {
        return MDC.get(REQUEST_ID);
    }

    public static String operationId() {
        return MDC.get(OPERATION_ID);
    }

    public static String ensureOperationId(String prefix) {
        String current = operationId();
        if (current != null && !current.isBlank()) return current;
        String value = prefix + "-" + UUID.randomUUID();
        MDC.put(OPERATION_ID, value);
        return value;
    }

    public static String newJobId(String jobName) {
        return jobName + "-" + UUID.randomUUID();
    }

    public static void bindAsync(String requestId, String operationId) {
        MDC.put(REQUEST_ID, validOrFallback(requestId, "async"));
        MDC.put(OPERATION_ID, validOrFallback(operationId, "async-" + UUID.randomUUID()));
    }

    public static void bindScheduled(String jobId) {
        MDC.put(REQUEST_ID, "scheduled");
        MDC.put(JOB_ID, jobId);
        MDC.put(OPERATION_ID, jobId);
    }

    public static void clearNonRequestFields() {
        MDC.remove(OPERATION_ID);
        MDC.remove(JOB_ID);
        MDC.remove(USER_ID);
    }

    public static void clearAll() {
        MDC.clear();
    }

    public static String maskEmail(String email) {
        if (email == null || email.isBlank()) return "";
        int at = email.indexOf('@');
        if (at <= 0) return "***";
        String local = email.substring(0, at);
        return local.substring(0, 1) + "***" + email.substring(at);
    }

    public static String safeMessage(Throwable error) {
        if (error == null || error.getMessage() == null) return "";
        return error.getMessage().replace('\n', ' ').replace('\r', ' ');
    }

    private static String validOrFallback(String value, String fallback) {
        if (value == null || value.isBlank()) return fallback;
        return value.length() <= 128 ? value.replaceAll("[^A-Za-z0-9._:-]", "_") : fallback;
    }
}
