package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.security.util.JwtTokenUtil;
import com.allahpan.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Tag(name = "UserController", description = "用户管理")
@RestController
@RequestMapping("/api/user")
public class UserController {

    @Autowired
    private UserService userService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;

    @Operation(summary = "首次设置密码")
    @PostMapping("/set-password")
    public CommonResult<Map<String, Object>> setPassword(@Valid @RequestBody SetPasswordRequest req) {
        var user = userService.getCurrentUser();
        userService.setPassword(user.getId(), req.getNewPassword());
        String token = jwtTokenUtil.generateToken(user.getId(), user.getEmail(), true);
        return CommonResult.success(Map.of("token", token, "hasPassword", true));
    }

    @Operation(summary = "获取当前用户信息")
    @GetMapping("/me")
    public CommonResult<?> getCurrentUser() {
        var user = userService.getCurrentUser();
        user.setPassword(null); // 不返回密码
        return CommonResult.success(user);
    }

    public static class SetPasswordRequest {
        @NotBlank(message = "新密码不能为空")
        private String newPassword;
        public String getNewPassword() { return newPassword; }
        public void setNewPassword(String newPassword) { this.newPassword = newPassword; }
    }
}
