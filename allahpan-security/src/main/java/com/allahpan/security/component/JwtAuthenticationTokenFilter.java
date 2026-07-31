package com.allahpan.security.component;

import java.io.IOException;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import com.allahpan.security.util.JwtTokenUtil;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * JWT 认证过滤器
 * 每次请求时从请求头提取并验证 JWT Token，设置认证信息到 SecurityContext
 */
@Component
public class JwtAuthenticationTokenFilter extends OncePerRequestFilter {

    @Autowired
    private UserDetailsService userDetailsService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;
    @Value("${jwt.tokenHead}")
    private String tokenHead;
    @Value("${jwt.tokenHeader}")
    private String tokenHeader;

    @jakarta.annotation.PostConstruct
    public void init() {
        System.out.println("JwtAuthenticationTokenFilter initialized: tokenHeader=" + tokenHeader + ", tokenHead=" + tokenHead);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String authHeader = request.getHeader(tokenHeader);
        String token = null;
        if (authHeader != null && authHeader.startsWith(tokenHead)) {
            token = authHeader.substring(tokenHead.length());
        } else if (allowsQueryToken(request)) {
            token = request.getParameter("token");
        }
        if (token != null && !token.isBlank()) {
            String email = jwtTokenUtil.getSubjectFromToken(token);
            if (email != null && SecurityContextHolder.getContext().getAuthentication() == null) {
                UserDetails userDetails = userDetailsService.loadUserByUsername(email);
                if (jwtTokenUtil.validateToken(token, email)) {
                    UsernamePasswordAuthenticationToken authentication =
                            new UsernamePasswordAuthenticationToken(
                                    userDetails, null, userDetails.getAuthorities());
                    authentication.setDetails(
                            new WebAuthenticationDetailsSource().buildDetails(request));
                    SecurityContextHolder.getContext().setAuthentication(authentication);
                }
            }
        }
        chain.doFilter(request, response);
    }

    /**
     * 浏览器原生的 img/video/iframe 无法附加 Authorization 请求头。
     * 仅媒体 GET 接口沿用文件监听已有的查询参数 token 方式。
     */
    private boolean allowsQueryToken(HttpServletRequest request) {
        if (!"GET".equalsIgnoreCase(request.getMethod())
                && !"HEAD".equalsIgnoreCase(request.getMethod())) return false;
        String uri = request.getRequestURI();
        if (uri == null || !uri.startsWith("/api/file/")) return false;
        return uri.endsWith("/stream")
                || uri.endsWith("/thumbnail")
                || uri.endsWith("/preview")
                || uri.endsWith("/download");
    }

}
