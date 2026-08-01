package com.allahpan.security.component;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.exception.ErrorResponse;
import com.allahpan.common.log.RequestLogFilter;
import com.allahpan.common.log.StructuredLog;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;

import java.io.IOException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class RestfulAccessDeniedHandler implements AccessDeniedHandler {
    private static final Logger LOG = LoggerFactory.getLogger(RestfulAccessDeniedHandler.class);
    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, AccessDeniedException e) throws IOException {
        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json");
        response.setStatus(HttpServletResponse.SC_OK);
        String errorId = ErrorResponse.newErrorId();
        request.setAttribute(RequestLogFilter.BUSINESS_STATUS, 403);
        request.setAttribute(RequestLogFilter.ERROR_ID, errorId);
        request.setAttribute(RequestLogFilter.ERROR_CODE, "FORBIDDEN");
        LOG.warn(StructuredLog.event("auth.request.forbidden", "errorId", errorId,
                "path", RequestLogFilter.safeRequestPath(request.getRequestURI())));
        response.getWriter().println(new ObjectMapper().writeValueAsString(
                CommonResult.forbidden(ErrorResponse.data(errorId))));
    }
}
