package com.allahpan.component;

import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.mbg.model.User;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

@Component
public class EsIndexServiceImpl implements EsIndexService {
    private static final Logger LOG = LoggerFactory.getLogger(EsIndexServiceImpl.class);

    @Autowired
    private UserMapper userMapper;
    @Autowired
    private FileMapper fileMapper;

    private final RestTemplate restTemplate = new RestTemplate();
    private static final String SEARCH_SERVICE_URL = "http://localhost:8081/es-admin/files";
    private static final int MAX_RETRIES = 3;

    /** ES 操作失败补偿队列：fileId → "index"|"delete"，定时重试 */
    private final Map<Long, String> pendingOps = new ConcurrentHashMap<>();

    /**
     * 启动时轮询等待搜索服务就绪，然后重建 ES 索引。
     * 单发 30s 延迟在搜索服务启动慢时会失败，改为轮询最多等 5 分钟。
     */
    @PostConstruct
    public void scheduleStartupCleanup() {
        Thread t = new Thread(() -> {
            for (int attempt = 0; attempt < 60; attempt++) {
                try {
                    // 用 GET /es-admin/files/search?keyword=__health_check__ 探测搜索服务
                    restTemplate.getForEntity(
                            SEARCH_SERVICE_URL + "/search?keyword=__health__&pageNum=1&pageSize=1",
                            String.class);
                    long count = rebuildAll();
                    LOG.info("ES 启动清理完成，索引 {} 个文件", count);
                    return;
                } catch (ResourceAccessException e) {
                    LOG.debug("等待搜索服务就绪 ({}/60)...", attempt + 1);
                } catch (Exception e) {
                    LOG.debug("搜索服务探测失败 ({}/60): {}", attempt + 1, e.getMessage());
                }
                try { Thread.sleep(5000); } catch (InterruptedException ignored) {}
            }
            LOG.warn("ES 启动清理超时（搜索服务 5 分钟未就绪），跳过");
        }, "es-cleanup");
        t.setDaemon(true);
        t.start();
    }

    @Override
    public void index(File file) {
        for (int attempt = 0; attempt < MAX_RETRIES; attempt++) {
            try {
                doIndex(file);
                return;
            } catch (Exception e) {
                if (attempt == MAX_RETRIES - 1) {
                    LOG.warn("ES 索引失败（重试 {} 次后放弃）: {}, 原因: {}",
                            MAX_RETRIES, file.getFileName(), e.getMessage());
                    pendingOps.put(file.getId(), "index");
                } else {
                    try { Thread.sleep(2000L * (attempt + 1)); } catch (InterruptedException ignored) {}
                }
            }
        }
    }

    private void doIndex(File file) {
        String uploaderName = "未知";
        if (file.getUploaderId() != null) {
            User user = userMapper.selectByPrimaryKey(file.getUploaderId());
            if (user != null) uploaderName = user.getNickname();
        }
        Map<String, Object> body = new HashMap<>();
        body.put("fileId", file.getId());
        body.put("fileName", file.getFileName() != null ? file.getFileName() : "");
        body.put("fileType", file.getFileType() != null ? file.getFileType() : "OTHER");
        body.put("filePath", file.getFilePath() != null ? file.getFilePath() : "");
        body.put("fileSize", file.getFileSize() != null ? file.getFileSize() : 0L);
        body.put("isFolder", file.getIsFolder() != null && file.getIsFolder() == 1);
        body.put("uploaderId", file.getUploaderId() != null ? file.getUploaderId() : 0L);
        body.put("uploaderName", uploaderName);
        body.put("originText", file.getOriginText() != null ? file.getOriginText() : "");
        body.put("createTime", file.getCreateTime() != null ? file.getCreateTime().toString() : "");
        restTemplate.postForEntity(SEARCH_SERVICE_URL + "/index", body, String.class);
    }

    @Override
    public void delete(Long fileId) {
        for (int attempt = 0; attempt < MAX_RETRIES; attempt++) {
            try {
                restTemplate.delete(SEARCH_SERVICE_URL + "/" + fileId);
                return;
            } catch (Exception e) {
                if (attempt == MAX_RETRIES - 1) {
                    LOG.warn("ES 删除失败（重试 {} 次后放弃）: fileId={}", MAX_RETRIES, fileId);
                    pendingOps.put(fileId, "delete");
                } else {
                    try { Thread.sleep(2000L * (attempt + 1)); } catch (InterruptedException ignored) {}
                }
            }
        }
    }

    @Override
    public long rebuildAll() {
        // 1. 清空 ES 索引
        try {
            restTemplate.delete(SEARCH_SERVICE_URL + "/_all");
        } catch (Exception e) {
            LOG.warn("清空 ES 索引失败: {}", e.getMessage());
            throw new RuntimeException("ES 全量删除失败，放弃重建", e);
        }

        // 2. 重新索引所有未删除的非文件夹文件
        FileExample example = new FileExample();
        example.createCriteria().andDeleteTimeIsNull().andIsFolderEqualTo((byte) 0);
        var files = fileMapper.selectByExampleWithBLOBs(example);
        int count = 0;
        for (File f : files) {
            try {
                index(f);
                count++;
            } catch (Exception e) {
                LOG.warn("重建索引失败: fileId={}", f.getId(), e);
            }
        }
        LOG.info("ES 索引重建完成: {} 个文件", count);
        return count;
    }

    /**
     * 每 30 分钟自动全量对账，清理 ES 中可能残留的孤儿文档。
     * 首次延迟 10 分钟（给启动清理留时间），之后每 30 分钟。
     */
    @Scheduled(fixedDelay = 30 * 60 * 1000, initialDelay = 10 * 60 * 1000)
    public void scheduledReconciliation() {
        try {
            long count = rebuildAll();
            if (count > 0) {
                LOG.info("ES 定时对账完成: {} 个文件", count);
            }
        } catch (Exception e) {
            LOG.warn("ES 定时对账失败: {}", e.getMessage());
        }
    }

    /**
     * 每 5 分钟重试失败的 ES 操作（增量补偿，不走全量重建）。
     * 全量对账（30 分钟）仍为最终兜底。
     */
    @Scheduled(fixedDelay = 5 * 60 * 1000, initialDelay = 2 * 60 * 1000)
    public void retryFailedOps() {
        if (pendingOps.isEmpty()) return;
        Map<Long, String> snapshot = new HashMap<>(pendingOps);
        pendingOps.clear();
        int success = 0;
        for (var entry : snapshot.entrySet()) {
            try {
                if ("index".equals(entry.getValue())) {
                    File f = fileMapper.selectByPrimaryKey(entry.getKey());
                    if (f != null && f.getDeleteTime() == null) {
                        doIndex(f);
                    }
                } else {
                    restTemplate.delete(SEARCH_SERVICE_URL + "/" + entry.getKey());
                }
                success++;
            } catch (Exception e) {
                // 重试失败则重新入队，等待下次调度
                pendingOps.put(entry.getKey(), entry.getValue());
            }
        }
        if (success > 0) {
            LOG.info("ES 补偿重试: 成功={}, 仍失败={}", success, snapshot.size() - success);
        }
    }
}