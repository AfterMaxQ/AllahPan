# 07 — 数据模型 ER 图

## 数据库 ER 图

```mermaid
erDiagram
    users {
        BIGINT id PK "自增主键"
        VARCHAR email UK "邮箱（登录凭证）"
        VARCHAR password "BCrypt 密码, NULL=首次登录"
        VARCHAR nickname "昵称"
        VARCHAR avatar_url "头像 key（可空）"
        TINYINT status "0=禁用, 1=正常"
        TINYINT first_login "1=首次(未设密码)"
        DATETIME last_login_time "最后登录"
        DATETIME create_time "创建时间"
        DATETIME update_time "更新时间"
    }

    files {
        BIGINT id PK "自增主键"
        BIGINT uploader_id FK "上传者 → users.id"
        BIGINT parent_id "父目录ID, 0=根目录"
        VARCHAR file_name "文件名"
        VARCHAR file_path "虚拟路径 /A/B/file.png"
        VARCHAR storage_key "本地存储路径 key"
        VARCHAR file_type "FOLDER/IMAGE/VIDEO/DOCUMENT/OTHER"
        BIGINT file_size "字节数"
        VARCHAR content_type "MIME type"
        VARCHAR thumbnail_key "缩略图本地路径 key"
        TINYINT is_folder "0=文件, 1=文件夹"
        LONGTEXT origin_text "文字提取内容 (BLOB)"
        TINYINT process_status "0=pending,1=thumb,2=text,3=done,-1=fail"
        VARCHAR md5 "MD5 哈希 (秒传用)"
        DATETIME create_time "创建时间"
        DATETIME update_time "更新时间"
        DATETIME delete_time "软删除时间, NULL=正常"
    }

    file_favorites {
        BIGINT id PK "自增主键"
        BIGINT user_id FK "用户 → users.id"
        BIGINT file_id FK "文件 → files.id"
        DATETIME create_time "收藏时间"
    }

    users ||--o{ files : "uploader_id"
    users ||--o{ file_favorites : "user_id"
    files ||--o{ file_favorites : "file_id"
    files ||--o{ files : "parent_id (自引用)"
```

## MyBatis Generator 代码生成关系

```mermaid
graph TD
    subgraph "generatorConfig.xml"
        GC["JDBC: mysql://localhost:3306/allahpan<br/>3 张表: users, files, file_favorites"]
    end

    subgraph "生成产物 (每张表 5 个文件)"
        Entity["Xxx.java 实体"]
        Example["XxxExample.java 条件构造器"]
        Mapper["XxxMapper.java 接口"]
        XML["XxxMapper.xml SQL映射"]
    end

    GC -->|"MyBatis Generator"| Entity
    GC -->|"MyBatis Generator"| Example
    GC -->|"MyBatis Generator"| Mapper
    GC -->|"MyBatis Generator"| XML
    GC -->|"CommentGenerator"| Comment["自定义注释:<br/>Lombok @Data<br/>+ 表名/字段注释"]

    Entity --> Mapper
    Example --> Mapper
    Mapper --> XML
```

## 表 → Java 类映射

| 表名 | 实体 | Mapper | Example | XML | 特殊处理 |
|------|------|--------|---------|-----|----------|
| `users` | `User.java` | `UserMapper.java` | `UserExample.java` | `UserMapper.xml` | — |
| `files` | `File.java` | `FileMapper.java` | `FileExample.java` | `FileMapper.xml` | ⚠️ BLOB 列 `origin_text` |
| `file_favorites` | `FileFavorite.java` | `FileFavoriteMapper.java` | `FileFavoriteExample.java` | `FileFavoriteMapper.xml` | — |

## BLOB 列特殊处理 (origin_text)

`files.origin_text` 是 `LONGTEXT`，MBG 视为 BLOB 类型：

```mermaid
flowchart LR
    subgraph "FileMapper 额外方法"
        A["selectByExampleWithBLOBs"]
        B["updateByExampleWithBLOBs"]
        C["updateByPrimaryKeyWithBLOBs"]
    end

    subgraph "FileMapper.xml"
        D["ResultMapWithBLOBs<br/>(extends BaseResultMap)"]
        E["Blob_Column_List<br/>= origin_text"]
    end

    A --> D
    A --> E
    B --> D
    C --> D
```

> **⚠️ 陷阱**: `selectByExample()` 和 `updateByPrimaryKey()` **不包含** `origin_text` 列。必须用 `selectByExampleWithBLOBs()` 等三个方法才能读写 `originText` 字段。

## 关键索引

```sql
-- users
PRIMARY KEY (id)
UNIQUE KEY (email)

-- files
PRIMARY KEY (id)
KEY (parent_id)
KEY (md5)              -- 秒传检测
KEY (uploader_id)

-- file_favorites
PRIMARY KEY (id)
UNIQUE KEY (user_id, file_id)  -- 防止重复收藏
```

## processStatus 枚举

| 值 | 含义 | 触发条件 |
|----|------|----------|
| `0` | 等待处理 | `confirmUpload` 后 |
| `1` | 缩略图完成 | RabbitMQ 消费者生成缩略图后 |
| `2` | 文字提取完成 | RabbitMQ OCR 完成后 |
| `3` | 全部完成(已索引) | ES 索引完成后；文件夹/秒传直接设此值 |
| `-1` | 处理失败 | 任何步骤异常 |

## isFolder 枚举

| 值 | 含义 |
|----|------|
| `0` | 文件 |
| `1` | 文件夹 |

## fileType 枚举

| 值 | 判断依据 |
|----|----------|
| `FOLDER` | 文件夹（手动设置） |
| `IMAGE` | contentType 以 `image/` 开头 |
| `VIDEO` | contentType 以 `video/` 开头 |
| `DOCUMENT` | `application/pdf` 或含 `document`/`spreadsheet`/`presentation` 及 `text/` |
| `OTHER` | 其他所有类型 |

## User 状态枚举

| 字段 | 值 | 含义 |
|------|-----|------|
| `status` | `0` | 禁用 |
| `status` | `1` | 正常 |
| `first_login` | `0` | 已设置密码 |
| `first_login` | `1` | 首次登录（未设密码） |

## 关键文件索引

| 文件 | 内容 |
|------|------|
| `init.sql` | 建表 DDL |
| `allahpan-mbg/src/main/resources/generatorConfig.xml` | MBG 生成配置 |
| `allahpan-mbg/src/main/java/.../mbg/Generator.java` | 生成器入口 |
| `allahpan-mbg/src/main/java/.../mbg/CommentGenerator.java` | 自定义注释生成 |
| `allahpan-mbg/src/main/java/.../mbg/model/User.java` | 用户实体 |
| `allahpan-mbg/src/main/java/.../mbg/model/File.java` | 文件实体（含 BLOB） |
| `allahpan-mbg/src/main/java/.../mbg/model/FileFavorite.java` | 收藏实体 |
| `allahpan-mbg/src/main/java/.../mbg/mapper/FileMapper.java` | 文件 Mapper（含 BLOBs 方法） |
