package com.allahpan.search.controller;

import com.allahpan.search.service.EsFileService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/es-admin/files")
public class EsFileController {

    @Autowired
    private EsFileService esFileService;

    @PostMapping("/index")
    public Map<String, Object> index(@RequestBody Map<String, Object> fileData) {
        esFileService.index(fileData);
        return Map.of("success", true);
    }

    @DeleteMapping("/{fileId}")
    public Map<String, Object> delete(@PathVariable Long fileId) {
        esFileService.delete(fileId);
        return Map.of("success", true);
    }

    @DeleteMapping("/_all")
    public Map<String, Object> deleteAll() {
        long deleted = esFileService.deleteAll();
        return Map.of("success", true, "deleted", deleted);
    }

    @GetMapping("/count")
    public Map<String, Object> count() {
        return Map.of("success", true, "count", esFileService.count());
    }

    @GetMapping("/search")
    public ResponseEntity<Map<String, Object>> search(
            @RequestParam String keyword,
            @RequestParam(required = false) String fileType,
            @RequestParam(required = false) Long minSize,
            @RequestParam(required = false) Long maxSize,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(required = false, defaultValue = "all") String searchScope,
            @RequestParam(required = false, defaultValue = "relevance") String sortBy,
            @RequestParam(required = false, defaultValue = "desc") String sortOrder,
            @RequestParam(required = false) String filterExpression,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        try {
            return ResponseEntity.ok(esFileService.search(keyword, fileType,
                    minSize, maxSize, startTime, endTime, searchScope,
                    sortBy, sortOrder, filterExpression, pageNum, pageSize));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "success", false,
                    "message", e.getMessage() == null ? "搜索筛选条件无效" : e.getMessage()));
        }
    }
}
