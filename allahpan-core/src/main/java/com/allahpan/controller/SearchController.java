package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.log.LogContext;
import com.allahpan.common.log.StructuredLog;
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
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.http.HttpClient;
import java.net.URI;
import java.time.Duration;
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
        UriComponentsBuilder builder = UriComponentsBuilder
                .fromUriString(searchServiceUrl + "/search")
                .queryParam("keyword", keyword)
                .queryParam("pageNum", pageNum)
                .queryParam("pageSize", pageSize);
        addQueryParam(builder, "fileType", fileType);
        addQueryParam(builder, "minSize", minSize);
        addQueryParam(builder, "maxSize", maxSize);
        addQueryParam(builder, "startTime", startTime);
        addQueryParam(builder, "endTime", endTime);
        addQueryParam(builder, "searchScope", searchScope);
        addQueryParam(builder, "sortBy", sortBy);
        addQueryParam(builder, "sortOrder", sortOrder);
        addQueryParam(builder, "filterExpression", filterExpression);
        URI uri = builder.encode(StandardCharsets.UTF_8).build().toUri();
        long started = System.nanoTime();
        try {
            HttpHeaders headers = new HttpHeaders();
            if (LogContext.requestId() != null) headers.set("X-Request-ID", LogContext.requestId());
            if (LogContext.operationId() != null) headers.set("X-Operation-ID", LogContext.operationId());
            ResponseEntity<Map> response = restTemplate.exchange(uri, HttpMethod.GET,
                    new HttpEntity<>(headers), Map.class);
            Map<String, Object> result = response.getBody();
            Object total = result == null ? null : result.get("totalCount");
            LOG.info(StructuredLog.event("search.completed", "keywordLength", keyword.length(),
                    "fileType", fileType, "pageNum", pageNum, "pageSize", pageSize,
                    "resultCount", total, "durationMs", elapsedMs(started)));
            return CommonResult.success(result);
        } catch (HttpClientErrorException.BadRequest e) {
            LOG.warn(StructuredLog.event("search.invalid_filter", "keywordLength", keyword.length(),
                    "durationMs", elapsedMs(started)));
            return CommonResult.failed("搜索筛选条件无效，请检查后重试");
        } catch (RestClientException e) {
            LOG.warn(StructuredLog.event("search.failed", "keywordLength", keyword.length(),
                    "fileType", fileType, "errorType", e.getClass().getSimpleName(),
                    "durationMs", elapsedMs(started)));
            return CommonResult.failed("搜索服务暂不可用，请稍后重试");
        }
    }

    private void addQueryParam(UriComponentsBuilder builder, String name, Object value) {
        if (value == null) return;
        if (value instanceof String text && text.isBlank()) return;
        builder.queryParam(name, value);
    }

    @PostMapping("/rebuild-index")
    @Operation(summary = "重建 ES 搜索索引（清空孤儿文档，重新索引全部有效文件）")
    public CommonResult<Map<String, Object>> rebuildIndex() {
        assertInitialAdmin();
        long count = esIndexService.rebuildAll();
        LOG.info(StructuredLog.event("search.index.rebuilt", "indexedCount", count));
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

    private long elapsedMs(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }
}
