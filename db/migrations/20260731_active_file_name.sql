-- 修复 (parent_id, file_name, delete_time) 无法约束 delete_time IS NULL 的问题。
-- 执行前确认不存在同目录活跃重名：
-- SELECT parent_id, file_name, COUNT(*)
-- FROM files WHERE delete_time IS NULL
-- GROUP BY parent_id, file_name HAVING COUNT(*) > 1;

ALTER TABLE files
    DROP INDEX uk_parent_name_delete,
    ADD COLUMN active_file_name VARCHAR(255)
        GENERATED ALWAYS AS (CASE WHEN delete_time IS NULL THEN file_name ELSE NULL END) STORED
        COMMENT '仅活跃记录参与同目录重名约束',
    ADD UNIQUE INDEX uk_parent_active_name (parent_id, active_file_name);
