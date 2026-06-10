package com.allahpan.security.component;

import java.io.IOException;

import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;

import com.allahpan.common.api.CommonResult;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 未登录或 token 失效时的统一响应处理器
 */
public class RestAuthenticationEntryPoint implements AuthenticationEntryPoint {
    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
            AuthenticationException e) throws IOException {
        // 1. 设置响应的编码为 UTF-8 → 防止中文乱码
        response.setCharacterEncoding("UTF-8");

        // 2. 设置响应类型为 JSON → 告诉前端：我返回的是JSON数据，不是网页
        response.setContentType("application/json");

        // 3. 设置HTTP状态码为 200（前后端分离标准做法）
        // 用业务状态码表示未登录，而不是HTTP 401
        response.setStatus(HttpServletResponse.SC_OK);

        // 4. 获取响应输出流，返回统一格式的JSON提示
        // new ObjectMapper().writeValueAsString：把Java对象转成JSON字符串
        // CommonResult.unauthorized：项目的通用返回类，返回「未登录」的结果
        response.getWriter().println(
            new ObjectMapper().writeValueAsString(CommonResult.unauthorized("暂未登录或 token 已过期"))
        );
    }
}
