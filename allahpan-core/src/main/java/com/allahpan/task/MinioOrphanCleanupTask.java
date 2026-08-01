package com.allahpan.task;

import com.allahpan.component.MinioUtil;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.FileExample;
import com.github.pagehelper.PageHelper;
import com.allahpan.common.log.LogContext;
import com.allahpan.common.log.StructuredLog;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.time.Duration;
import java.time.Instant;

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
    private static final Duration ORPHAN_GRACE_PERIOD = Duration.ofHours(24);

    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private FileMapper fileMapper;

    @Scheduled(cron = "0 0 4 * * ?")  // 每天凌晨 4:00
    public void scanOrphans() {
        long started = System.nanoTime();
        LogContext.bindScheduled(LogContext.newJobId("minio-orphan-cleanup"));
        log.info(StructuredLog.event("job.started", "jobName", "minio-orphan-cleanup"));
        boolean failed = false;
        try {
            scanOrphansInBucket(minioUtil.getBucketName(), "files");
            scanOrphansInBucket(minioUtil.getThumbnailBucket(), "thumbnails");
            scanOrphansInBucket(minioUtil.getTrashBucket(), "trash");
        } catch (Exception e) {
            failed = true;
            log.error(StructuredLog.event("job.failed", "jobName", "minio-orphan-cleanup",
                    "errorType", e.getClass().getSimpleName()), e);
        } finally {
            if (!failed) {
                log.info(StructuredLog.event("job.completed", "jobName", "minio-orphan-cleanup",
                        "durationMs", elapsedMs(started)));
            }
            LogContext.clearAll();
        }
    }

    private void scanOrphansInBucket(String bucket, String bucketLabel) {
        log.info(StructuredLog.event("job.bucket.started", "jobName", "minio-orphan-cleanup",
                "bucket", bucketLabel));
        try {
            List<String> minioKeys = minioUtil.listObjectNames(bucket);
            log.info(StructuredLog.event("job.bucket.scanned", "bucket", bucketLabel,
                    "objectCount", minioKeys.size()));
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
                    if (isTooNewToDelete(bucket, key)) {
                        log.debug(StructuredLog.event("job.object.skipped", "bucket", bucketLabel,
                                "reason", "grace_period"));
                        continue;
                    }
                    orphanCount++;
                    log.warn(StructuredLog.event("storage.orphan.detected", "bucket", bucketLabel));
                    // 安全清理：只删除确认无引用的对象
                    try {
                        if ("thumbnails".equals(bucketLabel)) {
                            minioUtil.removeThumbnail(key);
                        } else if ("trash".equals(bucketLabel)) {
                            minioUtil.removeFromTrash(key);
                        } else {
                            minioUtil.removeObject(key);
                        }
                        log.info(StructuredLog.event("storage.orphan.deleted", "bucket", bucketLabel));
                    } catch (Exception e) {
                        log.error(StructuredLog.event("storage.orphan.delete_failed", "bucket", bucketLabel,
                                "errorType", e.getClass().getSimpleName()), e);
                    }
                }
            }
            log.info(StructuredLog.event("job.bucket.completed", "bucket", bucketLabel,
                    "orphanCount", orphanCount));
        } catch (Exception e) {
            log.error(StructuredLog.event("job.bucket.failed", "bucket", bucketLabel,
                    "errorType", e.getClass().getSimpleName()), e);
        }
    }

    private boolean isTooNewToDelete(String bucket, String key) {
        try {
            Instant lastModified = minioUtil.objectLastModified(bucket, key);
            return lastModified != null && lastModified.plus(ORPHAN_GRACE_PERIOD).isAfter(Instant.now());
        } catch (Exception e) {
            log.warn(StructuredLog.event("storage.object_metadata.failed", "bucket", bucket,
                    "errorType", e.getClass().getSimpleName()), e);
            return true;
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
                if (f.getPreviewKey() != null) {
                    keys.add(f.getPreviewKey());
                }
            }
            if (files.size() < PAGE_SIZE) break;
            pageNum++;
        }
        // 补查仅有 previewKey 的记录
        pageNum = 1;
        while (true) {
            FileExample previewExample = new FileExample();
            previewExample.createCriteria().andPreviewKeyIsNotNull();
            PageHelper.startPage(pageNum, PAGE_SIZE);
            var previewFiles = fileMapper.selectByExample(previewExample);
            if (previewFiles.isEmpty()) break;
            for (var f : previewFiles) {
                if (f.getPreviewKey() != null) {
                    keys.add(f.getPreviewKey());
                }
            }
            if (previewFiles.size() < PAGE_SIZE) break;
            pageNum++;
        }
        return keys;
    }

    private long elapsedMs(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }
}
