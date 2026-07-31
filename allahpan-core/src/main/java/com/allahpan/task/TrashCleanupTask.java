package com.allahpan.task;

import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.FileService;
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
        log.info("========== 垃圾站定时清理开始 ==========");

        // 计算 60 天前的时间
        LocalDateTime threshold = LocalDateTime.now().minusDays(TRASH_RETENTION_DAYS);
        Date thresholdDate = Date.from(threshold.atZone(ZoneId.systemDefault()).toInstant());

        // 查询 delete_time <= 60天前 的所有文件
        FileExample example = new FileExample();
        example.createCriteria().andDeleteTimeLessThanOrEqualTo(thresholdDate);
        List<File> expiredFiles = fileMapper.selectByExample(example);

        if (expiredFiles.isEmpty()) {
            log.info("没有过期垃圾文件需要清理");
            return;
        }

        var result = fileService.batchPermanentDelete(
                expiredFiles.stream().map(File::getId).toList());
        int success = ((Number) result.getOrDefault("deletedCount", 0)).intValue();
        int fail = ((List<?>) result.getOrDefault("failedIds", List.of())).size();

        log.info("垃圾站清理完成: 总计={}, 成功={}, 失败={}", expiredFiles.size(), success, fail);
        log.info("========== 垃圾站定时清理结束 ==========");
    }
}
