package com.allahpan.task;

import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.FileService;
import com.allahpan.common.log.LogContext;
import com.allahpan.common.log.StructuredLog;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;

/**
 * 垃圾站定时清理：每天凌晨 3 点扫描，物理删除超过 60 天的垃圾文件
 */
@Component
public class TrashCleanupTask {

    private static final Logger log = LoggerFactory.getLogger(TrashCleanupTask.class);

    /** 垃圾站保留天数 */
    private static final int TRASH_RETENTION_DAYS = 60;

    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileService fileService;

    @Scheduled(cron = "0 0 3 * * ?")  // 每天凌晨 3:00
    public void cleanExpiredTrash() {
        long started = System.nanoTime();
        LogContext.bindScheduled(LogContext.newJobId("trash-cleanup"));
        log.info(StructuredLog.event("job.started", "jobName", "trash-cleanup"));
        int scanned = 0;
        int success = 0;
        int fail = 0;
        try {
            LocalDateTime threshold = LocalDateTime.now().minusDays(TRASH_RETENTION_DAYS);
            Date thresholdDate = Date.from(threshold.atZone(ZoneId.systemDefault()).toInstant());

            FileExample example = new FileExample();
            example.createCriteria().andDeleteTimeLessThanOrEqualTo(thresholdDate);
            List<File> expiredFiles = fileMapper.selectByExample(example);
            scanned = expiredFiles.size();

            if (!expiredFiles.isEmpty()) {
                var result = fileService.batchPermanentDelete(
                        expiredFiles.stream().map(File::getId).toList());
                success = ((Number) result.getOrDefault("deletedCount", 0)).intValue();
                fail = ((List<?>) result.getOrDefault("failedIds", List.of())).size();
            }
            log.info(StructuredLog.event("job.completed", "jobName", "trash-cleanup",
                    "scanned", scanned, "success", success, "failed", fail,
                    "durationMs", elapsedMs(started)));
        } catch (Exception e) {
            log.error(StructuredLog.event("job.failed", "jobName", "trash-cleanup",
                    "scanned", scanned, "success", success, "failed", fail,
                    "errorType", e.getClass().getSimpleName()), e);
        } finally {
            LogContext.clearAll();
        }
    }

    private long elapsedMs(long started) {
        return (System.nanoTime() - started) / 1_000_000;
    }
}
