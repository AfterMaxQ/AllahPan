package com.allahpan.search.controller;

import com.allahpan.search.service.EsFileService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * ES 索引管理接口
 */
@RestController
@RequestMapping("/es-admin")
public class EsAdminController {

    @Autowired
    private EsFileService esFileService;

    /**
     * 全量重建索引 —— 由 core 模块传入全量文件数据进行重新索引
     */
    @PostMapping("/rebuild")
    public Map<String, Object> rebuild(@RequestBody List<Map<String, Object>> files) {
        int success = 0;
        int fail = 0;
        for (Map<String, Object> fileData : files) {
            try {
                esFileService.index(fileData);
                success++;
            } catch (Exception e) {
                fail++;
            }
        }
        return Map.of("success", true, "total", files.size(),
                "indexed", success, "failed", fail);
    }
}