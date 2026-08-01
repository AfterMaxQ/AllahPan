package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.log.StructuredLog;
import com.allahpan.component.MinioUtil;
import com.allahpan.mbg.model.File;
import com.allahpan.service.ShareService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@Tag(name = "ShareController", description = "文件分享")
@RestController
@RequestMapping("/api/share")
public class ShareController {
    private static final Logger LOG = LoggerFactory.getLogger(ShareController.class);

    @Autowired
    private ShareService shareService;
    @Autowired
    private MinioUtil minioUtil;

    @Operation(summary = "创建分享链接")
    @PostMapping("/{fileId}")
    public CommonResult<Map<String, Object>> createShare(
            @PathVariable Long fileId,
            @RequestParam(defaultValue = "24") int expireHours) {
        Map<String, Object> result = shareService.createShare(fileId, expireHours);
        LOG.info(StructuredLog.event("share.created", "fileId", fileId, "expireHours", expireHours));
        return CommonResult.success(result);
    }

    @Operation(summary = "获取分享内容（公开）")
    @GetMapping("/{code}")
    public CommonResult<Map<String, Object>> getShare(@PathVariable String code) {
        Map<String, Object> result = shareService.getShare(code);
        LOG.info(StructuredLog.event("share.accessed", "fileId", result.get("fileId")));
        return CommonResult.success(result);
    }

    @Operation(summary = "下载分享文件（公开，需有效分享码）")
    @GetMapping("/{code}/download")
    public ResponseEntity<Resource> downloadSharedFile(@PathVariable String code) {
        File file = shareService.getSharedFile(code);
        String encodedName = URLEncoder.encode(file.getFileName(), StandardCharsets.UTF_8)
                .replace("+", "%20");
        return streamResponse(file, "attachment; filename*=UTF-8''" + encodedName);
    }

    @Operation(summary = "预览分享文件（公开，需有效分享码）")
    @GetMapping("/{code}/stream")
    public ResponseEntity<Resource> streamSharedFile(@PathVariable String code) {
        File file = shareService.getSharedFile(code);
        return streamResponse(file, "inline");
    }

    @Operation(summary = "删除分享链接")
    @DeleteMapping("/{code}")
    public CommonResult<Void> deleteShare(@PathVariable String code) {
        shareService.deleteShare(code);
        LOG.info(StructuredLog.event("share.deleted"));
        return CommonResult.success(null);
    }

    private ResponseEntity<Resource> streamResponse(File file, String contentDisposition) {
        try {
            if (!minioUtil.objectExists(file.getStorageKey())) {
                return ResponseEntity.notFound().build();
            }
            InputStream stream = minioUtil.getObject(file.getStorageKey());
            InputStreamResource resource = new InputStreamResource(stream);
            var response = ResponseEntity.ok()
                    .contentType(MediaType.parseMediaType(
                            file.getContentType() != null ? file.getContentType() : "application/octet-stream"))
                    .header(HttpHeaders.CONTENT_DISPOSITION, contentDisposition);
            if (file.getFileSize() != null && file.getFileSize() >= 0) {
                response.contentLength(file.getFileSize());
            }
            return response.body(resource);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
}
