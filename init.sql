-- AllahPan 数据库初始化脚本
-- 执行方式：docker exec -i mysql-allahpan mysql -uroot -p123456 allahpan < init.sql
-- 或登录 MySQL 客户端后 source init.sql

CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱（登录凭证）',
    password VARCHAR(255) COMMENT 'BCrypt 密文，首次登录前为 NULL',
    nickname VARCHAR(50) COMMENT '昵称',
    avatar_url VARCHAR(255) COMMENT '头像 MinIO key',
    status TINYINT DEFAULT 1 COMMENT '0=禁用 1=正常',
    first_login TINYINT DEFAULT 1 COMMENT '0=已设密码 1=首次登录',
    last_login_time DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '用户表';

CREATE TABLE IF NOT EXISTS files (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    uploader_id BIGINT COMMENT '上传者',
    parent_id BIGINT DEFAULT 0 COMMENT '父目录ID，0=根目录',
    file_name VARCHAR(255) NOT NULL COMMENT '文件名',
    file_path VARCHAR(500) COMMENT '虚拟路径',
    storage_key VARCHAR(500) COMMENT 'MinIO 存储 key',
    file_type VARCHAR(20) COMMENT 'FOLDER/IMAGE/VIDEO/DOCUMENT/OTHER',
    file_size BIGINT DEFAULT 0 COMMENT '文件大小（字节）',
    content_type VARCHAR(100) COMMENT 'MIME 类型',
    thumbnail_key VARCHAR(500) COMMENT '列表缩略图 MinIO key',
    preview_key VARCHAR(500) COMMENT '预览高清图 MinIO key',
    is_folder TINYINT DEFAULT 0 COMMENT '0=文件 1=文件夹',
    origin_text LONGTEXT COMMENT 'PDF 解析/OCR 提取的文本',
    process_status TINYINT DEFAULT 0 COMMENT '0=待处理 1=缩略图完成 2=文本提取完成 3=索引完成 -1=失败',
    md5 VARCHAR(32) COMMENT '文件 MD5',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    delete_time DATETIME COMMENT '软删除时间',
    active_file_name VARCHAR(255)
        GENERATED ALWAYS AS (CASE WHEN delete_time IS NULL THEN file_name ELSE NULL END) STORED
        COMMENT '仅活跃记录参与同目录重名约束',
    UNIQUE KEY uk_parent_active_name (parent_id, active_file_name)
) COMMENT '文件表';

-- 性能索引
CREATE INDEX idx_parent_delete ON files (parent_id, delete_time);
CREATE INDEX idx_md5_delete ON files (md5, delete_time);
CREATE INDEX idx_delete_time ON files (delete_time);
-- active_file_name 对已删除记录为 NULL，因此历史垃圾文件仍可同名。

CREATE TABLE IF NOT EXISTS file_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    file_id BIGINT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_file (user_id, file_id)
) COMMENT '文件收藏表';

-- ===== 迁移语句 =====
-- v2: phone → email（2026-06-08）
-- ALTER TABLE users CHANGE phone email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱（登录凭证）';
