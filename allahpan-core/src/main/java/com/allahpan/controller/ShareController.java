package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.service.ShareService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Tag(name = "ShareController", description = "文件分享")
@RestController
@RequestMapping("/api/share")
public class ShareController {

    @Autowired
    private ShareService shareService;

    @Operation(summary = "创建分享链接")
    @PostMapping("/{fileId}")
    public CommonResult<Map<String, Object>> createShare(
            @PathVariable Long fileId,
            @RequestParam(defaultValue = "24") int expireHours) {
        return CommonResult.success(shareService.createShare(fileId, expireHours));
    }

    @Operation(summary = "获取分享内容（公开）")
    @GetMapping("/{code}")
    public CommonResult<Map<String, Object>> getShare(@PathVariable String code) {
        return CommonResult.success(shareService.getShare(code));
    }

    @Operation(summary = "删除分享链接")
    @DeleteMapping("/{code}")
    public CommonResult<Void> deleteShare(@PathVariable String code) {
        shareService.deleteShare(code);
        return CommonResult.success(null);
    }
}
