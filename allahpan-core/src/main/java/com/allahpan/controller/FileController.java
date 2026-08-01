package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.component.FileProcessSender;
import com.allahpan.component.SseBroadcaster;
import com.allahpan.domain.FileProcessMessage;
import com.allahpan.mbg.model.File;
import com.allahpan.security.util.JwtTokenUtil;
import com.allahpan.service.FileService;
import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import com.allahpan.component.MinioUtil;
import com.allahpan.common.log.LogContext;
import com.allahpan.common.log.StructuredLog;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
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
        String operationId = LogContext.ensureOperationId("upload");
        File saved = fileService.upload(file, parentId);
        if (!"FOLDER".equals(saved.getFileType()) && (saved.getProcessStatus() == null || saved.getProcessStatus() != 3)) {
            fileProcessSender.sendProcess(new FileProcessMessage(saved.getId(), FileProcessMessage.Stage.UPLOADED,
                    LogContext.requestId(), operationId));
        }
        LOG.info(StructuredLog.event("file.upload.completed", "fileId", saved.getId(),
                "fileType", saved.getFileType(), "fileSize", file.getSize(), "parentId", parentId));
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
    public CommonResult<?> listFiles(
            @RequestParam(defaultValue = "0") Long parentId,
            @RequestParam(defaultValue = "false") boolean paged,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "100") int pageSize) {
        if (paged) {
            pageNum = Math.max(pageNum, 1);
            pageSize = Math.max(1, Math.min(pageSize, 200));
            PageHelper.startPage(pageNum, pageSize);
        }
        var list = fileService.listFiles(parentId);
        var result = list.stream().map(this::toFileResponse).toList();
        if (paged) {
            PageInfo<File> page = new PageInfo<>(list);
            return CommonResult.success(Map.of(
                    "list", result,
                    "total", page.getTotal(),
                    "pageNum", page.getPageNum(),
                    "pageSize", page.getPageSize(),
                    "pages", page.getPages()));
        }
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
    public ResponseEntity<Resource> downloadFile(
            @PathVariable Long fileId,
            @RequestHeader(value = HttpHeaders.RANGE, required = false) String rangeHeader) {
        File file = fileService.getFileById(fileId);
        validateDownloadable(file);
        String encodedName = URLEncoder.encode(file.getFileName(), StandardCharsets.UTF_8)
                .replace("+", "%20");
        return streamResponse(file, "attachment; filename*=UTF-8''" + encodedName, rangeHeader);
    }

    @Operation(summary = "预览文件（inline）")
    @GetMapping("/{fileId}/stream")
    public ResponseEntity<Resource> streamFile(
            @PathVariable Long fileId,
            @RequestHeader(value = HttpHeaders.RANGE, required = false) String rangeHeader) {
        File file = fileService.getFileById(fileId);
        validateDownloadable(file);
        return streamResponse(file, "inline", rangeHeader);
    }

    private void validateDownloadable(File file) {
        com.allahpan.common.exception.Asserts.isTrue(file != null, "文件不存在");
        com.allahpan.common.exception.Asserts.isTrue(file.getDeleteTime() == null, "文件已删除");
        com.allahpan.common.exception.Asserts.isTrue(!Integer.valueOf(1).equals(file.getIsFolder()), "文件夹不支持下载");
        com.allahpan.common.exception.Asserts.isTrue(file.getStorageKey() != null, "文件无存储对象");
    }

    private ResponseEntity<Resource> streamResponse(
            File file, String contentDisposition, String rangeHeader) {
        String key = file.getStorageKey();
        LOG.info(StructuredLog.event("file.download.started", "fileId", file.getId(),
                "contentType", file.getContentType(), "range", rangeHeader != null));
        try {
            long totalSize = file.getFileSize() != null && file.getFileSize() >= 0
                    ? file.getFileSize()
                    : minioUtil.statObject(key).size();
            ByteRange range;
            try {
                range = parseRange(rangeHeader, totalSize);
            } catch (IllegalArgumentException e) {
                return ResponseEntity.status(HttpStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        .header(HttpHeaders.CONTENT_RANGE, "bytes */" + totalSize)
                        .build();
            }

            InputStream stream = range == null
                    ? minioUtil.getObject(key)
                    : minioUtil.getObject(key, range.start(), range.length());
            InputStreamResource resource = new InputStreamResource(stream);
            MediaType contentType;
            try {
                contentType = MediaType.parseMediaType(
                        file.getContentType() != null ? file.getContentType() : "application/octet-stream");
            } catch (IllegalArgumentException ignored) {
                contentType = MediaType.APPLICATION_OCTET_STREAM;
            }

            ResponseEntity.BodyBuilder response = range == null
                    ? ResponseEntity.ok()
                    : ResponseEntity.status(HttpStatus.PARTIAL_CONTENT);
            response.contentType(contentType)
                    .header(HttpHeaders.CONTENT_DISPOSITION, contentDisposition)
                    .header(HttpHeaders.ACCEPT_RANGES, "bytes")
                    .contentLength(range == null ? totalSize : range.length());
            if (range != null) {
                response.header(HttpHeaders.CONTENT_RANGE,
                        "bytes " + range.start() + "-" + range.end() + "/" + totalSize);
            }
            return response.body(resource);
        } catch (Exception e) {
            LOG.error(StructuredLog.event("file.download.failed", "fileId", file.getId(),
                    "errorType", e.getClass().getSimpleName()), e);
            return ResponseEntity.internalServerError().build();
        }
    }

    static ByteRange parseRange(String rangeHeader, long totalSize) {
        if (rangeHeader == null || rangeHeader.isBlank()) return null;
        if (totalSize <= 0 || !rangeHeader.startsWith("bytes=") || rangeHeader.contains(",")) {
            throw new IllegalArgumentException("unsupported range");
        }
        String value = rangeHeader.substring("bytes=".length()).trim();
        int dash = value.indexOf('-');
        if (dash < 0) throw new IllegalArgumentException("invalid range");

        String startValue = value.substring(0, dash).trim();
        String endValue = value.substring(dash + 1).trim();
        long start;
        long end;
        try {
            if (startValue.isEmpty()) {
                long suffixLength = Long.parseLong(endValue);
                if (suffixLength <= 0) throw new IllegalArgumentException("invalid suffix range");
                start = Math.max(0, totalSize - suffixLength);
                end = totalSize - 1;
            } else {
                start = Long.parseLong(startValue);
                if (start < 0 || start >= totalSize) {
                    throw new IllegalArgumentException("range starts past end");
                }
                end = endValue.isEmpty()
                        ? totalSize - 1
                        : Math.min(Long.parseLong(endValue), totalSize - 1);
                if (end < start) throw new IllegalArgumentException("range end before start");
            }
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("invalid range number", e);
        }
        return new ByteRange(start, end);
    }

    record ByteRange(long start, long end) {
        long length() {
            return end - start + 1;
        }
    }

    @Operation(summary = "缩略图（MinIO）")
    @GetMapping("/{fileId}/thumbnail")
    public ResponseEntity<Resource> getThumbnail(
            @PathVariable Long fileId,
            @RequestHeader(value = HttpHeaders.IF_NONE_MATCH, required = false) String ifNoneMatch) {
        File file = fileService.getFileById(fileId);
        if (file == null || file.getThumbnailKey() == null) {
            return ResponseEntity.notFound().build();
        }
        return streamThumbnail(file.getThumbnailKey(), fileId, "thumbnail", ifNoneMatch);
    }

    @Operation(summary = "预览高清图（MinIO）")
    @GetMapping("/{fileId}/preview")
    public ResponseEntity<Resource> getPreview(
            @PathVariable Long fileId,
            @RequestHeader(value = HttpHeaders.IF_NONE_MATCH, required = false) String ifNoneMatch) {
        File file = fileService.getFileById(fileId);
        if (file == null || file.getPreviewKey() == null) {
            return ResponseEntity.notFound().build();
        }
        return streamThumbnail(file.getPreviewKey(), fileId, "preview", ifNoneMatch);
    }

    private ResponseEntity<Resource> streamThumbnail(
            String objectKey, Long fileId, String label, String ifNoneMatch) {
        try {
            var stat = minioUtil.statObject(minioUtil.getThumbnailBucket(), objectKey);
            String etag = "\"" + stat.etag() + "\"";
            if (etag.equals(ifNoneMatch)) {
                return ResponseEntity.status(HttpStatus.NOT_MODIFIED)
                        .header(HttpHeaders.ETAG, etag)
                        .header(HttpHeaders.CACHE_CONTROL, "private, max-age=86400")
                        .build();
            }
            InputStream stream = minioUtil.getThumbnail(objectKey);
            InputStreamResource resource = new InputStreamResource(stream);
            return ResponseEntity.ok()
                    .contentType(MediaType.IMAGE_JPEG)
                    .contentLength(stat.size())
                    .header(HttpHeaders.ETAG, etag)
                    .header(HttpHeaders.CACHE_CONTROL, "private, max-age=86400")
                    .body(resource);
        } catch (Exception e) {
            LOG.warn(StructuredLog.event("file.preview.failed", "fileId", fileId,
                    "kind", label, "errorType", e.getClass().getSimpleName()), e);
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

    @Operation(summary = "一键清空垃圾站")
    @DeleteMapping("/trash/empty")
    public CommonResult<?> emptyTrash() {
        int count = fileService.emptyTrash();
        return CommonResult.success(
                Map.of("deletedCount", count, "message", "已清空 " + count + " 个文件"),
                "已清空 " + count + " 个文件");
    }

    @Operation(summary = "批量永久删除垃圾站文件")
    @DeleteMapping("/trash/batch")
    public CommonResult<?> batchPermanentDelete(@RequestBody Map<String, List<Long>> req) {
        List<Long> ids = req.get("ids");
        if (ids == null || ids.isEmpty()) {
            return CommonResult.failed("请选择要删除的文件");
        }
        Map<String, Object> result = fileService.batchPermanentDelete(ids);
        int count = ((Number) result.getOrDefault("deletedCount", 0)).intValue();
        result.put("message", "已删除 " + count + " 个文件");
        return CommonResult.success(result, "已删除 " + count + " 个文件");
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
        map.put("fileType", f.getFileType());
        map.put("fileSize", f.getFileSize() != null ? f.getFileSize() : 0L);
        map.put("contentType", f.getContentType());
        map.put("thumbnailKey", f.getThumbnailKey());
        if (f.getThumbnailKey() != null) {
            map.put("thumbnailUrl", "/api/file/" + f.getId() + "/thumbnail");
        }
        map.put("previewKey", f.getPreviewKey());
        if (f.getPreviewKey() != null) {
            map.put("previewUrl", "/api/file/" + f.getId() + "/preview");
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
