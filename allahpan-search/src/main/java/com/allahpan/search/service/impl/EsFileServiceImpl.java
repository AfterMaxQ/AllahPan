package com.allahpan.search.service.impl;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.query_dsl.TextQueryType;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import com.allahpan.search.domain.EsFile;
import com.allahpan.search.repository.EsFileRepository;
import com.allahpan.search.service.EsFileService;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.elasticsearch.core.ElasticsearchOperations;
import org.springframework.data.elasticsearch.core.IndexOperations;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class EsFileServiceImpl implements EsFileService {

    private static final Logger log = LoggerFactory.getLogger(EsFileServiceImpl.class);

    @Autowired
    private EsFileRepository repository;
    @Autowired
    private ElasticsearchClient elasticsearchClient;
    @Autowired
    private ElasticsearchOperations elasticsearchOperations;

    @PostConstruct
    public void ensureIndexExists() {
        try {
            IndexOperations indexOps = elasticsearchOperations.indexOps(EsFile.class);
            if (!indexOps.exists()) {
                indexOps.createWithMapping();
                log.info("ES 索引 {} 已按实体映射创建", EsFile.INDEX_NAME);
            } else {
                // 只补充兼容字段，不删除现有文档，重启期间搜索持续可用。
                indexOps.putMapping(indexOps.createMapping());
                log.info("ES 索引 {} 已存在，保留数据并校验映射", EsFile.INDEX_NAME);
            }
        } catch (Exception e) {
            log.warn("ES 索引初始化失败（不会删除现有索引）: {}", e.getMessage());
        }
    }

    @Override
    public void index(Map<String, Object> data) {
        EsFile f = new EsFile();
        f.setFileId(toLong(data.get("fileId")));
        f.setFileName((String) data.get("fileName"));
        f.setFileType((String) data.get("fileType"));
        f.setOriginText((String) data.getOrDefault("originText", ""));
        f.setFilePath((String) data.get("filePath"));
        f.setUploaderId(toLong(data.get("uploaderId")));
        f.setUploaderName((String) data.get("uploaderName"));
        f.setFileSize(toLong(data.get("fileSize")));
        f.setIsFolder((Boolean) data.getOrDefault("isFolder", false));
        f.setCreateTime(parseDate(data.get("createTime")));
        repository.save(f);
    }

    @Override
    public void delete(Long fileId) {
        repository.deleteById(fileId);
    }

    @Override
    public long deleteAll() {
        try {
            var response = elasticsearchClient.deleteByQuery(d -> d
                    .index(EsFile.INDEX_NAME)
                    .query(q -> q.matchAll(m -> m)));
            return response.deleted();
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage() : "";
            if (msg.contains("index_not_found_exception")) {
                return 0;
            }
            throw new RuntimeException("ES 全量删除失败", e);
        }
    }

    @Override
    public long count() {
        return repository.count();
    }

    @Override
    public Map<String, Object> search(String keyword, String fileType, int pageNum, int pageSize) {
        var request = co.elastic.clients.elasticsearch.core.SearchRequest.of(s -> s
                .index(EsFile.INDEX_NAME)
                .query(q -> q
                        .bool(b -> {
                            // must: 至少匹配一个字段（标题或内容）
                            b.must(m -> m
                                    .multiMatch(mm -> mm
                                            .fields("fileName^10", "originText^5", "originText.char^2")
                                            .query(keyword)
                                            .type(TextQueryType.BestFields)));
                            // should: 标题命中额外加分，确保标题匹配优先于纯内容匹配
                            b.should(sh -> sh
                                    .match(mt -> mt
                                            .field("fileName")
                                            .query(keyword)
                                            .boost(50.0f)));
                            if (fileType != null && !fileType.isEmpty()) {
                                b.filter(f -> f.term(t -> t.field("fileType").value(fileType)));
                            }
                            return b;
                        }))
                .highlight(h -> h
                        .fields("fileName", hf -> hf.numberOfFragments(0)
                                .preTags("<mark>").postTags("</mark>"))
                        .fields("originText", hf -> hf.numberOfFragments(3).fragmentSize(100)
                                .preTags("<mark>").postTags("</mark>"))
                        .fields("originText.char", hf -> hf.numberOfFragments(3).fragmentSize(100)
                                .preTags("<mark>").postTags("</mark>")))
                .aggregations("fileTypes", a -> a
                        .terms(t -> t.field("fileType").size(10)))
                .from((pageNum - 1) * pageSize)
                .size(pageSize));

        SearchResponse<EsFile> response;
        try {
            response = elasticsearchClient.search(request, EsFile.class);
        } catch (Exception e) {
            String msg = e.getMessage() != null ? e.getMessage() : "";
            Throwable cause = e.getCause();
            String causeMsg = cause != null ? cause.getMessage() : "";
            log.error("ES 搜索失败: keyword={}, error={}, cause={}", keyword, msg, causeMsg);
            if (msg.contains("index_not_found_exception")) {
                return emptyResult();
            }
            throw new RuntimeException("Elasticsearch search failed", e);
        }

        List<Map<String, Object>> list = response.hits().hits().stream()
                .map(hit -> {
                    Map<String, Object> item = new HashMap<>();
                    EsFile f = hit.source();
                    item.put("fileId", f.getFileId());
                    item.put("fileName", f.getFileName());
                    item.put("fileType", f.getFileType());
                    item.put("filePath", f.getFilePath());
                    item.put("uploaderName", f.getUploaderName());
                    item.put("fileSize", f.getFileSize());
                    item.put("createTime", f.getCreateTime());
                    // 高亮
                    if (hit.highlight() != null) {
                        if (hit.highlight().containsKey("fileName")) {
                            item.put("fileNameHighlight",
                                    String.join("", hit.highlight().get("fileName")));
                        }
                        if (hit.highlight().containsKey("originText")) {
                            item.put("contentSnippets", hit.highlight().get("originText"));
                        } else if (hit.highlight().containsKey("originText.char")) {
                            item.put("contentSnippets", hit.highlight().get("originText.char"));
                        }
                    }
                    item.put("score", hit.score());
                    return item;
                }).toList();

        Map<String, Object> result = new HashMap<>();
        result.put("list", list);
        result.put("totalCount", response.hits().total() != null ? response.hits().total().value() : 0);

        // 聚合
        if (response.aggregations() != null && response.aggregations().containsKey("fileTypes")) {
            var buckets = response.aggregations().get("fileTypes").sterms().buckets().array();
            var aggList = buckets.stream()
                    .map(b -> Map.of("type", b.key().stringValue(), "count", b.docCount()))
                    .toList();
            result.put("aggregations", Map.of("fileTypes", aggList));
        }
        return result;
    }

    private Map<String, Object> emptyResult() {
        Map<String, Object> result = new HashMap<>();
        result.put("list", List.of());
        result.put("totalCount", 0L);
        return result;
    }

    private Long toLong(Object v) {
        if (v instanceof Number n) return n.longValue();
        if (v instanceof String s) return Long.parseLong(s);
        return 0L;
    }

    private Date parseDate(Object value) {
        if (value == null) return new Date();
        if (value instanceof Date date) return date;
        if (value instanceof Number number) return new Date(number.longValue());
        String s = value.toString();
        try {
            return Date.from(Instant.parse(s));
        } catch (Exception e) {
            try {
                return Date.from(LocalDateTime.parse(s,
                        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
                        .atZone(ZoneId.systemDefault()).toInstant());
            } catch (Exception e2) {
                return new Date();
            }
        }
    }
}
