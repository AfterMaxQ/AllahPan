package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.exception.Asserts;
import com.allahpan.component.EsIndexService;
import com.allahpan.bo.AdminUserDetails;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.client.JdkClientHttpRequestFactory;

import java.net.http.HttpClient;
import java.net.URI;
import java.time.Duration;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@Tag(name = "SearchController", description = "搜索管理")
@RestController
@RequestMapping("/api/search")
public class SearchController {

    private static final Logger LOG = LoggerFactory.getLogger(SearchController.class);
    @Value("${allahpan.search.service-url:http://localhost:8081/es-admin/files}")
    private String searchServiceUrl;

    @Autowired
    private EsIndexService esIndexService;
    private final RestTemplate restTemplate;

    public SearchController() {
        HttpClient httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(3))
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(Duration.ofSeconds(10));
        this.restTemplate = new RestTemplate(factory);
    }

    @GetMapping
    @Operation(summary = "搜索文件（ES 全文检索）")
    public CommonResult<Map<String, Object>> search(
            @RequestParam String keyword,
            @RequestParam(required = false) String fileType,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        // 手动构建 URI（URLEncoder + URI 构造器确保中文参数正确编码）
        String encodedKeyword = URLEncoder.encode(keyword, StandardCharsets.UTF_8);
        String query = "keyword=" + encodedKeyword + "&pageNum=" + pageNum + "&pageSize=" + pageSize;
        if (fileType != null && !fileType.isEmpty()) {
            query += "&fileType=" + URLEncoder.encode(fileType, StandardCharsets.UTF_8);
        }
        URI uri = URI.create(searchServiceUrl + "/search?" + query);
        LOG.info("搜索请求: keyword={}", keyword);
        try {
            Map<String, Object> result = restTemplate.getForObject(uri, Map.class);
            return CommonResult.success(result);
        } catch (RestClientException e) {
            LOG.warn("搜索服务不可用: {}", e.getMessage());
            return CommonResult.failed("搜索服务暂不可用，请稍后重试");
        }
    }

    @PostMapping("/rebuild-index")
    @Operation(summary = "重建 ES 搜索索引（清空孤儿文档，重新索引全部有效文件）")
    public CommonResult<Map<String, Object>> rebuildIndex() {
        assertInitialAdmin();
        long count = esIndexService.rebuildAll();
        LOG.info("搜索索引已重建: {} 个文件", count);
        return CommonResult.success(Map.of("indexedCount", count));
    }

    private void assertInitialAdmin() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AdminUserDetails details) {
            Asserts.isTrue(Long.valueOf(1L).equals(details.getUserId()), "仅管理员可重建搜索索引");
            return;
        }
        Asserts.fail("未授权");
    }
}
