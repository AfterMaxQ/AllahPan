package com.allahpan.component;

import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.github.pagehelper.PageHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 启动时将 DB 中 MinIO 格式的 storageKey 迁移为本地相对路径。
 * 迁移完成后自动成为 no-op（所有 key 已是本地路径）。
 */
@Component
public class StorageKeyMigration {

    private static final Logger log = LoggerFactory.getLogger(StorageKeyMigration.class);
    private static final int BATCH_SIZE = 500;

    @Autowired
    private FileMapper fileMapper;

    @jakarta.annotation.PostConstruct
    public void migrate() {
        int totalMigrated = 0;
        int pageNum = 1;

        while (true) {
            FileExample example = new FileExample();
            example.createCriteria();
            PageHelper.startPage(pageNum, BATCH_SIZE, false);
            List<File> batch = fileMapper.selectByExample(example);
            if (batch.isEmpty()) break;

            int batchMigrated = 0;
            for (File f : batch) {
                if (f.getStorageKey() == null) continue;
                if (!looksLikeMinioKey(f.getStorageKey())) continue;

                String newPath = buildLocalPath(f);
                if (newPath == null || newPath.isEmpty()) continue;

                log.info("迁移 storageKey: {} -> {}", f.getStorageKey(), newPath);
                File update = new File();
                update.setId(f.getId());
                update.setStorageKey(newPath);
                fileMapper.updateByPrimaryKeySelective(update);
                batchMigrated++;
            }

            totalMigrated += batchMigrated;
            if (batch.size() < BATCH_SIZE) break;
            pageNum++;
        }

        if (totalMigrated > 0) {
            log.info("StorageKey 迁移完成: {} 条记录已更新", totalMigrated);
        } else {
            log.info("StorageKey 迁移: 无需迁移（所有 key 已是本地路径）");
        }
    }

    /**
     * MinIO key 格式: "1/yyyy/MM/uuid.ext" — 以数字开头，含 UUID-like 段
     */
    private boolean looksLikeMinioKey(String key) {
        return key.matches("^\\d+/\\d{4}/\\d{2}/[0-9a-f-]{36}.*");
    }

    /**
     * 根据 parentId 链重建本地相对路径。
     */
    private String buildLocalPath(File file) {
        ArrayList<String> parts = new ArrayList<>();
        parts.add(file.getFileName());
        Long pid = file.getParentId();
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            parts.add(0, parent.getFileName());
            pid = parent.getParentId();
        }
        return String.join("/", parts);
    }
}
