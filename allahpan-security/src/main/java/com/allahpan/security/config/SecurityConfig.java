package com.allahpan.security.config;

import com.allahpan.security.component.JwtAuthenticationTokenFilter;
import com.allahpan.security.component.RestAuthenticationEntryPoint;
import com.allahpan.security.component.RestfulAccessDeniedHandler;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import java.util.List;

/**
 * Spring Security 配置
 * - 无状态会话（JWT）
 * - BCrypt 密码编码
 * - 自定义白名单/异常处理/JWT 过滤器
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    /** 绑定 secure.ignored.urls 配置项 */
    @Bean
    @ConfigurationProperties(prefix = "secure.ignored")
    public IgnoredUrlsConfig ignoredUrlsConfig() {
        return new IgnoredUrlsConfig();
    }

    /** 密码编码器 */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    /** 安全过滤链配置 */
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http,
            JwtAuthenticationTokenFilter jwtFilter) throws Exception {
        List<String> urls = ignoredUrlsConfig().getUrls();
        http
            .csrf(AbstractHttpConfigurer::disable)
            .headers(headers -> headers.frameOptions(frameOptions -> frameOptions.sameOrigin()))
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(org.springframework.security.web.util.matcher.AntPathRequestMatcher
                    .antMatcher("/api/share/**")).permitAll()
                .requestMatchers(urls.toArray(new String[0])).permitAll()
                .requestMatchers(HttpMethod.OPTIONS).permitAll()
                .anyRequest().authenticated())
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(new RestAuthenticationEntryPoint())
                .accessDeniedHandler(new RestfulAccessDeniedHandler()))
            .addFilterBefore(jwtFilter,
                UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    /** 白名单配置属性映射 */
    public static class IgnoredUrlsConfig {
        private List<String> urls;
        public List<String> getUrls() { return urls; }
        public void setUrls(List<String> urls) { this.urls = urls; }
    }
}
