package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.log.StructuredLog;
import com.allahpan.security.util.JwtTokenUtil;
import com.allahpan.service.AuthCodeService;
import com.allahpan.service.UserService;
import com.allahpan.domain.LoginRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;

@Tag(name = "AuthController", description = "认证管理")
@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private static final Logger LOG = LoggerFactory.getLogger(AuthController.class);

    @Autowired
    private AuthCodeService authCodeService;
    @Autowired
    private UserService userService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;

    @Operation(summary = "发送验证码")
    @PostMapping("/send-code")
    public CommonResult<Void> sendCode(@Valid @RequestBody LoginRequest req) {
        authCodeService.sendCode(req.getEmail());
        return CommonResult.success(null, "验证码已发送");
    }

    @Operation(summary = "验证码登录")
    @PostMapping("/login-by-code")
    public CommonResult<Map<String, Object>> loginByCode(@Valid @RequestBody LoginRequest req) {
        authCodeService.verifyCode(req.getEmail(), req.getCode());
        var user = userService.loginByCode(req.getEmail());
        return buildLoginResponse(user.getId(), user.getEmail(), user.getFirstLogin() == 0);
    }

    @Operation(summary = "密码登录")
    @PostMapping("/login-by-password")
    public CommonResult<Map<String, Object>> loginByPassword(@Valid @RequestBody LoginRequest req) {
        var user = userService.loginByPassword(req.getEmail(), req.getPassword());
        return buildLoginResponse(user.getId(), user.getEmail(), true);
    }

    private CommonResult<Map<String, Object>> buildLoginResponse(Long userId, String email, boolean hasPassword) {
        String token = jwtTokenUtil.generateToken(userId, email, hasPassword);
        LOG.info(StructuredLog.event("auth.login.success", "userId", userId,
                "loginMethod", hasPassword ? "password" : "code"));
        return CommonResult.success(Map.of(
            "token", token,
            "tokenHead", "Bearer ",
            "userId", userId,
            "email", email,
            "hasPassword", hasPassword,
            "firstLogin", !hasPassword  // 前端据此判断是否跳转设置密码页
        ));
    }
}
