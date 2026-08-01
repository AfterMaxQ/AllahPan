package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.log.StructuredLog;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.allahpan.service.ChunkUploadService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

@Tag(name = "ChunkController", description = "分片上传")
@RestController
@RequestMapping("/api/file/chunk")
public class ChunkController {
    private static final Logger LOG = LoggerFactory.getLogger(ChunkController.class);

    @Autowired
    private ChunkUploadService chunkUploadService;

    @Operation(summary = "初始化上传会话（支持断点续传）")
    @PostMapping("/init")
    public CommonResult<Map<String, Object>> init(@RequestBody Map<String, Object> req) {
        String fileName = (String) req.get("fileName");
        long fileSize = ((Number) req.get("fileSize")).longValue();
        String fileMd5 = (String) req.get("fileMd5");
        String contentType = (String) req.get("contentType");
        Long parentId = req.get("parentId") != null
                ? ((Number) req.get("parentId")).longValue() : 0L;
        int chunkSize = ((Number) req.get("chunkSize")).intValue();
        int totalChunks = ((Number) req.get("totalChunks")).intValue();

        return CommonResult.success(
                chunkUploadService.init(fileName, fileSize, fileMd5, contentType, parentId, chunkSize, totalChunks));
    }

    @Operation(summary = "上传单个分片")
    @PostMapping("/upload")
    public CommonResult<Map<String, String>> uploadChunk(
            @RequestParam("uploadId") String uploadId,
            @RequestParam("chunkIndex") int chunkIndex,
            @RequestParam("chunk") MultipartFile chunk) {
        try {
            chunkUploadService.uploadChunk(uploadId, chunkIndex, chunk);
        } catch (Exception e) {
            LOG.warn(StructuredLog.event("file.upload.chunk.failed", "uploadId", uploadId,
                    "chunkIndex", chunkIndex,
                    "errorType", e.getClass().getSimpleName()), e);
            return CommonResult.failed("分片上传失败，请重试");
        }
        Map<String, String> result = new java.util.LinkedHashMap<>();
        result.put("uploadId", uploadId);
        result.put("chunkIndex", String.valueOf(chunkIndex));
        result.put("status", "ok");
        return CommonResult.success(result);
    }

    @Operation(summary = "合并分片并完成上传")
    @PostMapping("/complete")
    public CommonResult<Map<String, Object>> complete(@RequestBody Map<String, Object> req) {
        String uploadId = (String) req.get("uploadId");
        return CommonResult.success(chunkUploadService.complete(uploadId));
    }

    @Operation(summary = "查询上传会话状态")
    @GetMapping("/status/{uploadId}")
    public CommonResult<Map<String, Object>> status(@PathVariable String uploadId) {
        return CommonResult.success(chunkUploadService.getStatus(uploadId));
    }
}
