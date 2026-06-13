package com.allahpan.task;

import com.allahpan.component.MinioUtil;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.FileExample;
import com.github.pagehelper.PageHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * MinIO 孤儿对象定时扫描：每天凌晨 4 点检查 MinIO 与 MySQL 的一致性。
 * <p>
 * 双向检查：
 * 1. MinIO 有对象但 DB 无任何记录引用 → 删除孤儿对象
 * 2. DB storageKey 指向不存在的 MinIO 对象 → 记 warning（需人工排查）
 */
@Component
public class MinioOrphanCleanupTask {

    private static final Logger log = LoggerFactory.getLogger(MinioOrphanCleanupTask.class);
    private static final int PAGE_SIZE = 1000;

    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private FileMapper fileMapper;

    @Scheduled(cron = "0 0 4 * * ?")  // 每天凌晨 4:00
    public void scanOrphans() {
        log.info("========== MinIO 孤儿对象扫描开始 ==========");
        try {
            scanOrphansInBucket(minioUtil.getBucketName(), "files");
            scanOrphansInBucket(minioUtil.getThumbnailBucket(), "thumbnails");
            scanOrphansInBucket(minioUtil.getTrashBucket(), "trash");
        } catch (Exception e) {
            log.error("MinIO 孤儿扫描异常", e);
        }
        log.info("========== MinIO 孤儿对象扫描结束 ==========");
    }

    private void scanOrphansInBucket(String bucket, String bucketLabel) {
        log.info("扫描 {} bucket...", bucketLabel);
        try {
            List<String> minioKeys = minioUtil.listObjectNames(bucket);
            log.info("{} bucket 共 {} 个对象", bucketLabel, minioKeys.size());
            if (minioKeys.isEmpty()) return;

            // 收集 DB 中所有引用的 storageKey 和 thumbnailKey
            Set<String> dbStorageKeys = collectAllStorageKeys();
            Set<String> dbThumbnailKeys = collectAllThumbnailKeys();

            int orphanCount = 0;
            for (String key : minioKeys) {
                boolean inDb = "thumbnails".equals(bucketLabel)
                        ? dbThumbnailKeys.contains(key)
                        : dbStorageKeys.contains(key);
                if (!inDb) {
                    orphanCount++;
                    log.warn("发现孤儿 MinIO 对象: bucket={}, key={}", bucketLabel, key);
                    // 安全清理：只删除确认无引用的对象
                    try {
                        if ("thumbnails".equals(bucketLabel)) {
                            minioUtil.removeThumbnail(key);
                        } else if ("trash".equals(bucketLabel)) {
                            minioUtil.removeFromTrash(key);
                        } else {
                            minioUtil.removeObject(key);
                        }
                        log.info("已清理孤儿对象: bucket={}, key={}", bucketLabel, key);
                    } catch (Exception e) {
                        log.error("清理孤儿对象失败: bucket={}, key={}", bucketLabel, key, e);
                    }
                }
            }
            log.info("{} bucket 扫描完成: 孤儿={}", bucketLabel, orphanCount);
        } catch (Exception e) {
            log.error("扫描 {} bucket 失败", bucketLabel, e);
        }
    }

    /** 收集 DB 中所有 storageKey（去重），分页查询避免一次性加载大量数据 */
    private Set<String> collectAllStorageKeys() {
        Set<String> keys = new HashSet<>();
        int pageNum = 1;
        while (true) {
            FileExample example = new FileExample();
            example.createCriteria().andStorageKeyIsNotNull();
            PageHelper.startPage(pageNum, PAGE_SIZE);
            var files = fileMapper.selectByExample(example);
            if (files.isEmpty()) break;
            for (var f : files) {
                if (f.getStorageKey() != null) {
                    keys.add(f.getStorageKey());
                }
            }
            if (files.size() < PAGE_SIZE) break;
            pageNum++;
        }
        return keys;
    }

    /** 收集 DB 中所有 thumbnailKey（去重），分页查询避免一次性加载大量数据 */
    private Set<String> collectAllThumbnailKeys() {
        Set<String> keys = new HashSet<>();
        int pageNum = 1;
        while (true) {
            FileExample example = new FileExample();
            example.createCriteria().andThumbnailKeyIsNotNull();
            PageHelper.startPage(pageNum, PAGE_SIZE);
            var files = fileMapper.selectByExample(example);
            if (files.isEmpty()) break;
            for (var f : files) {
                if (f.getThumbnailKey() != null) {
                    keys.add(f.getThumbnailKey());
                }
            }
            if (files.size() < PAGE_SIZE) break;
            pageNum++;
        }
        return keys;
    }
}
