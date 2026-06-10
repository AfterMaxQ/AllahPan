package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.component.EsIndexService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@Tag(name = "SearchController", description = "搜索管理")
@RestController
@RequestMapping("/api/search")
public class SearchController {

    private static final Logger LOG = LoggerFactory.getLogger(SearchController.class);
    private static final String SEARCH_SERVICE = "http://localhost:8081/es-admin/files/search";

    @Autowired
    private EsIndexService esIndexService;

    @GetMapping
    @Operation(summary = "搜索文件（ES 全文检索）")
    public CommonResult<Map<String, Object>> search(
            @RequestParam String keyword,
            @RequestParam(required = false) String fileType,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        RestTemplate rt = new RestTemplate();
        // 手动构建 URI（URLEncoder + URI 构造器确保中文参数正确编码）
        String encodedKeyword = URLEncoder.encode(keyword, StandardCharsets.UTF_8);
        String query = "keyword=" + encodedKeyword + "&pageNum=" + pageNum + "&pageSize=" + pageSize;
        if (fileType != null && !fileType.isEmpty()) {
            query += "&fileType=" + URLEncoder.encode(fileType, StandardCharsets.UTF_8);
        }
        URI uri = URI.create(SEARCH_SERVICE + "?" + query);
        LOG.info("搜索请求: keyword={}", keyword);
        try {
            Map<String, Object> result = rt.getForObject(uri, Map.class);
            return CommonResult.success(result);
        } catch (RestClientException e) {
            LOG.warn("搜索服务不可用: {}", e.getMessage());
            return CommonResult.failed("搜索服务暂不可用，请稍后重试");
        }
    }

    @PostMapping("/rebuild-index")
    @Operation(summary = "重建 ES 搜索索引（清空孤儿文档，重新索引全部有效文件）")
    public CommonResult<Map<String, Object>> rebuildIndex() {
        long count = esIndexService.rebuildAll();
        LOG.info("搜索索引已重建: {} 个文件", count);
        return CommonResult.success(Map.of("indexedCount", count));
    }
}
