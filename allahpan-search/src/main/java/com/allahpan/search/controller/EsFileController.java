package com.allahpan.search.controller;

import com.allahpan.search.service.EsFileService;
import org.springframework.beans.factory.annotation.Autowired;
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
    public Map<String, Object> search(
            @RequestParam String keyword,
            @RequestParam(required = false) String fileType,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return esFileService.search(keyword, fileType, pageNum, pageSize);
    }
}
