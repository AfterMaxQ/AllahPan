package com.allahpan.common.log;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/** One request boundary for request IDs, MDC cleanup and HTTP summary logs. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestLogFilter extends OncePerRequestFilter {
    public static final String BUSINESS_STATUS = RequestLogFilter.class.getName() + ".businessStatus";
    public static final String ERROR_ID = RequestLogFilter.class.getName() + ".errorId";
    public static final String ERROR_CODE = RequestLogFilter.class.getName() + ".errorCode";

    private static final Logger LOG = LoggerFactory.getLogger(RequestLogFilter.class);

    @Value("${allahpan.logging.slow-request-ms:1000}")
    private long slowRequestMs;

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String requestId = normalizeRequestId(request.getHeader("X-Request-ID"));
        MDC.put(LogContext.REQUEST_ID, requestId);
        String operationId = normalizeOptional(request.getHeader("X-Operation-ID"));
        if (operationId != null) MDC.put(LogContext.OPERATION_ID, operationId);
        response.setHeader("X-Request-ID", requestId);

        long started = System.nanoTime();
        try {
            filterChain.doFilter(request, response);
        } finally {
            long durationMs = (System.nanoTime() - started) / 1_000_000;
            if (!skipSummary(request)) {
                logSummary(request, response, durationMs);
            }
            LogContext.clearAll();
        }
    }

    private void logSummary(HttpServletRequest request, HttpServletResponse response, long durationMs) {
        int status = response.getStatus();
        Object businessStatus = request.getAttribute(BUSINESS_STATUS);
        if (status == HttpServletResponse.SC_OK && businessStatus instanceof Number number) {
            status = number.intValue();
        }
        String event = status >= 500 ? "http.request.failed"
                : durationMs >= slowRequestMs ? "http.request.slow"
                : status >= 400 ? "http.request.rejected" : "http.request.completed";
        String message = StructuredLog.event(event,
                "method", request.getMethod(),
                "path", safeRequestPath(request.getRequestURI()),
                "status", status,
                "durationMs", durationMs,
                "errorId", request.getAttribute(ERROR_ID),
                "errorCode", request.getAttribute(ERROR_CODE));
        if (status >= 500) LOG.error(message);
        else if (status >= 400 || durationMs >= slowRequestMs) LOG.warn(message);
        else LOG.info(message);
    }

    private boolean skipSummary(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path == null || path.equals("/api/file/watch")
                || path.startsWith("/swagger-ui/") || path.startsWith("/v3/api-docs")
                || path.startsWith("/webjars/") || path.equals("/favicon.ico")
                || path.equals("/error") || path.equals("/actuator/health");
    }

    public static String safeRequestPath(String path) {
        if (path == null || !path.startsWith("/api/share/")) return path;
        String suffix = path.substring("/api/share/".length());
        int slash = suffix.indexOf('/');
        return "/api/share/{code}" + (slash >= 0 ? suffix.substring(slash) : "");
    }

    private String normalizeRequestId(String value) {
        String normalized = normalizeOptional(value);
        return normalized != null ? normalized : "req-" + UUID.randomUUID();
    }

    private String normalizeOptional(String value) {
        if (value == null || value.isBlank() || value.length() > 128
                || !value.matches("[A-Za-z0-9._:-]+")) return null;
        return value;
    }
}
