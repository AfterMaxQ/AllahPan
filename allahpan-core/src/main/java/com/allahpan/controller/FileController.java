package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.component.FileProcessSender;
import com.allahpan.component.SseBroadcaster;
import com.allahpan.domain.FileProcessMessage;
import com.allahpan.mbg.model.File;
import com.allahpan.security.util.JwtTokenUtil;
import com.allahpan.service.FileService;
import com.allahpan.component.MinioUtil;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Tag(name = "FileController", description = "文件管理")
@RestController
@RequestMapping("/api/file")
public class FileController {

    private static final Logger LOG = LoggerFactory.getLogger(FileController.class);

    @Autowired
    private FileService fileService;
    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private FileProcessSender fileProcessSender;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;
    @Autowired
    private SseBroadcaster sseBroadcaster;

    @Operation(summary = "上传文件（multipart 单步上传）")
    @PostMapping("/upload")
    public CommonResult<Map<String, Object>> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "0") Long parentId) {
        File saved = fileService.upload(file, parentId);
        if (!"FOLDER".equals(saved.getFileType()) && (saved.getProcessStatus() == null || saved.getProcessStatus() != 3)) {
            fileProcessSender.sendProcess(new FileProcessMessage(saved.getId(), FileProcessMessage.Stage.UPLOADED));
        }
        // Notify SSE clients about the new file
        Map<String, Object> sseData = new LinkedHashMap<>();
        sseData.put("fileId", saved.getId());
        sseData.put("parentId", saved.getParentId());
        sseBroadcaster.broadcast("file-created", sseData);

        return CommonResult.success(toFileResponse(saved));
    }

    @Operation(summary = "创建文件夹")
    @PostMapping("/create-folder")
    public CommonResult<File> createFolder(@RequestBody Map<String, Object> req) {
        String folderName = (String) req.get("folderName");
        Long parentId = req.get("parentId") != null
                ? ((Number) req.get("parentId")).longValue() : 0L;
        return CommonResult.success(fileService.createFolder(folderName, parentId));
    }

    @Operation(summary = "文件列表")
    @GetMapping("/list")
    public CommonResult<?> listFiles(@RequestParam(defaultValue = "0") Long parentId) {
        var list = fileService.listFiles(parentId);
        var result = list.stream().map(this::toFileResponse).toList();
        return CommonResult.success(result);
    }

    @Operation(summary = "目录树（面包屑导航）")
    @GetMapping("/tree/{folderId}")
    public CommonResult<?> getDirectoryTree(@PathVariable Long folderId) {
        return CommonResult.success(fileService.getDirectoryTree(folderId));
    }

    @Operation(summary = "删除文件")
    @DeleteMapping("/{fileId}")
    public CommonResult<Void> deleteFile(@PathVariable Long fileId) {
        fileService.deleteFile(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "文件详情")
    @GetMapping("/{fileId}")
    public CommonResult<Map<String, Object>> getFile(@PathVariable Long fileId) {
        File file = fileService.getFileById(fileId);
        if (file == null) {
            return CommonResult.failed("文件不存在");
        }
        return CommonResult.success(toFileResponse(file));
    }

    @Operation(summary = "下载文件（MinIO 流式返回）")
    @GetMapping("/{fileId}/download")
    public ResponseEntity<Resource> downloadFile(@PathVariable Long fileId) {
        File file = fileService.getFileById(fileId);
        validateDownloadable(file);
        String encodedName = URLEncoder.encode(file.getFileName(), StandardCharsets.UTF_8)
                .replace("+", "%20");
        return streamResponse(file, "attachment; filename*=UTF-8''" + encodedName);
    }

    @Operation(summary = "预览文件（inline）")
    @GetMapping("/{fileId}/stream")
    public ResponseEntity<Resource> streamFile(@PathVariable Long fileId) {
        File file = fileService.getFileById(fileId);
        validateDownloadable(file);
        return streamResponse(file, "inline");
    }

    private void validateDownloadable(File file) {
        com.allahpan.common.exception.Asserts.isTrue(file != null, "文件不存在");
        com.allahpan.common.exception.Asserts.isTrue(file.getDeleteTime() == null, "文件已删除");
        com.allahpan.common.exception.Asserts.isTrue(file.getIsFolder() != 1, "文件夹不支持下载");
        com.allahpan.common.exception.Asserts.isTrue(file.getStorageKey() != null, "文件无存储对象");
    }

    private ResponseEntity<Resource> streamResponse(File file, String contentDisposition) {
        String key = file.getStorageKey();
        LOG.info("stream request: fileId={} storageKey='{}' contentType='{}' disposition={}",
                file.getId(), key, file.getContentType(), contentDisposition);
        try {
            // 防御性检查：确认 MinIO 对象存在再读取
            if (!minioUtil.objectExists(key)) {
                LOG.error("MinIO object NOT FOUND for stream: fileId={} storageKey='{}' fileName='{}' filePath='{}'",
                        file.getId(), key, file.getFileName(), file.getFilePath());
                return ResponseEntity.notFound().build();
            }
            InputStream stream = minioUtil.getObject(key);
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
            LOG.error("Failed to stream file: fileId={} storageKey='{}' error={}",
                    file.getId(), key, e.toString(), e);
            return ResponseEntity.internalServerError().build();
        }
    }

    @Operation(summary = "缩略图（MinIO）")
    @GetMapping("/{fileId}/thumbnail")
    public ResponseEntity<Resource> getThumbnail(@PathVariable Long fileId) {
        File file = fileService.getFileById(fileId);
        if (file == null || file.getThumbnailKey() == null) {
            return ResponseEntity.notFound().build();
        }
        try {
            InputStream stream = minioUtil.getThumbnail(file.getThumbnailKey());
            InputStreamResource resource = new InputStreamResource(stream);
            return ResponseEntity.ok()
                    .contentType(MediaType.IMAGE_JPEG)
                    .body(resource);
        } catch (Exception e) {
            LOG.warn("Failed to stream thumbnail: fileId={} thumbnailKey='{}' error={}",
                    file.getId(), file.getThumbnailKey(), e.toString());
            return ResponseEntity.notFound().build();
        }
    }

    @Operation(summary = "实时文件变更监听（SSE）")
    @GetMapping("/watch")
    public SseEmitter watchFiles(@RequestParam(required = false) String token) {
        // EventSource 不支持自定义请求头，JWT 通过查询参数传递
        SseEmitter emitter = new SseEmitter(0L);
        if (token == null || token.isBlank() || jwtTokenUtil.getUserIdFromToken(token) == null) {
            emitter.completeWithError(new SecurityException("未授权的访问"));
            return emitter;
        }
        return sseBroadcaster.subscribe();
    }

    @Operation(summary = "重命名文件")
    @PutMapping("/{fileId}/rename")
    public CommonResult<File> renameFile(@PathVariable Long fileId, @RequestBody Map<String, Object> req) {
        String newName = (String) req.get("newName");
        return CommonResult.success(fileService.renameFile(fileId, newName));
    }

    @Operation(summary = "移动文件")
    @PutMapping("/{fileId}/move")
    public CommonResult<File> moveFile(@PathVariable Long fileId, @RequestBody Map<String, Object> req) {
        Long targetParentId = req.get("targetParentId") != null
                ? ((Number) req.get("targetParentId")).longValue() : 0L;
        return CommonResult.success(fileService.moveFile(fileId, targetParentId));
    }

    @Operation(summary = "批量删除")
    @DeleteMapping("/batch")
    public CommonResult<Map<String, Object>> batchDelete(@RequestBody Map<String, Object> req) {
        @SuppressWarnings("unchecked")
        List<Number> rawIds = (List<Number>) req.get("fileIds");
        com.allahpan.common.exception.Asserts.isTrue(rawIds != null && !rawIds.isEmpty(), "请选择要删除的文件");
        List<Long> fileIds = rawIds.stream().map(Number::longValue).toList();
        return CommonResult.success(fileService.batchDelete(fileIds));
    }

    // ========== 垃圾站 ==========

    @Operation(summary = "垃圾站列表")
    @GetMapping("/trash")
    public CommonResult<List<File>> listTrash(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return CommonResult.success(fileService.listTrash(pageNum, pageSize));
    }

    @Operation(summary = "恢复文件")
    @PutMapping("/trash/{fileId}/restore")
    public CommonResult<Void> restoreFile(@PathVariable Long fileId) {
        fileService.restoreFile(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "永久删除")
    @DeleteMapping("/trash/{fileId}")
    public CommonResult<Void> permanentDelete(@PathVariable Long fileId) {
        fileService.permanentDelete(fileId);
        return CommonResult.success(null);
    }

    // ========== 响应转换 ==========

    /**
     * 将 File 实体转换为前端友好的响应 Map。
     * 缩略图 key 替换为可访问的 URL。
     */
    private Map<String, Object> toFileResponse(File f) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("id", f.getId());
        map.put("uploaderId", f.getUploaderId());
        map.put("parentId", f.getParentId());
        map.put("fileName", f.getFileName());
        map.put("filePath", f.getFilePath());
        map.put("storageKey", f.getStorageKey());
        map.put("fileType", f.getFileType());
        map.put("fileSize", f.getFileSize());
        map.put("contentType", f.getContentType());
        map.put("thumbnailKey", f.getThumbnailKey());
        if (f.getThumbnailKey() != null) {
            map.put("thumbnailUrl", "/api/file/" + f.getId() + "/thumbnail");
        }
        map.put("isFolder", f.getIsFolder());
        map.put("processStatus", f.getProcessStatus());
        map.put("originText", f.getOriginText() != null ? f.getOriginText() : "");
        map.put("md5", f.getMd5());
        map.put("createTime", f.getCreateTime());
        map.put("updateTime", f.getUpdateTime());
        map.put("deleteTime", f.getDeleteTime());
        return map;
    }
}
