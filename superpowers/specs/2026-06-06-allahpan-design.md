# AllahPan 云盘系统设计文档

> 基于 mall 项目技术栈的全面应用与升级——从 JWT 认证到 MinIO 直传、从 RabbitMQ 延迟队列到文件处理状态机、从 ES 商品搜索到文件内容检索。每个技术决策都回答"为什么这么选"。

---

## 一、项目概述

AllahPan 是一个**共享云盘系统**（多用户访问同一文件池），部署在 Mac 上，域名 Allah.cn。核心定位是**实际可用 + 简历亮点**——每个技术选型都能在面试中讲出决策理由。

### 核心功能

| 功能 | 描述 |
|------|------|
| 多用户注册登录 | 手机验证码 + 密码双通道，首次登录强制设密码 |
| 文件管理 | 树形文件夹、拖拽/按钮上传、自定义根目录（默认 Mac 桌面） |
| 缩略图预览 | 图片/PDF 首页/视频封面，状态机异步生成 |
| 内容搜索 | 文件名 + PDF 正文 + 图片 OCR 文字，ES 高亮返回 |
| 智能 OCR | Ollama 本地部署千问3-VL，图片→文字，MLX GPU 加速 |
| 文件收藏 | 每人独立收藏夹 |
| Docker 部署 | 一键编排 7 个容器 + 数据卷持久化 |

### 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Spring Boot | 3.5 |
| JDK | Java | 17 |
| ORM | MyBatis + MyBatis Generator | 3.5 |
| 数据库 | MySQL | 8.0 |
| 缓存 | Redis | 7.0 |
| 消息队列 | RabbitMQ | 3.12 |
| 搜索引擎 | Elasticsearch | 7.17 |
| 对象存储 | MinIO | latest |
| AI 推理 | Ollama + 千问3-VL (MLX) | 0.19+ |
| 前端 | Vue 3 + Vite + Element Plus | — |
| 部署 | Docker Compose + nginx | — |

---

## 二、模块架构

```
AllahPan (Maven Aggregator, JDK 17, Spring Boot 3.5)
│
├── allahpan-common      通用层：CommonResult、RedisService、MinIO工具、全局异常
├── allahpan-security    安全层：JWT工具、Spring Security过滤器、@CacheException
├── allahpan-mbg         数据层：MBG 生成模型 + Mapper
├── allahpan-core        核心业务（可部署，端口 8080）
│   ├── controller       用户/文件/收藏/搜索 API
│   ├── service          业务逻辑 + CacheService
│   ├── dao              手写复杂 SQL
│   ├── component        RabbitMQ 收发、文件处理状态机
│   └── config           MinIO、RabbitMQ、线程池
│
└── allahpan-search      ES 搜索模块（独立应用，端口 8081）
    ├── domain           EsFile 文档定义
    ├── repository       Spring Data ES Repository
    └── service          搜索、索引、高亮
```

### 依赖关系

```
common → security → mbg → core
                       → search
```

### 与 mall 模块对照

| AllahPan | mall | 复用 | 创新 |
|----------|------|------|------|
| allahpan-common | mall-common | CommonResult、RedisService、GlobalExceptionHandler | MinIO 工具类封装 |
| allahpan-security | mall-security | JWT 过滤器链、@CacheException | 双通道登录、首次设密码 |
| allahpan-mbg | mall-mbg | MBG 生成模式、CommentGenerator | 表规模更小（5-8 张） |
| allahpan-core | mall-admin + mall-portal 融合 | CacheService 模式、RabbitMQ 配置 | 文件状态机、MinIO 适配、Ollama 集成 |
| allahpan-search | mall-search | function_score、ik_max_word、高亮查询 | 文件内容检索（originText 字段） |

---

## 三、数据库设计

### 3.1 用户认证（users）

```sql
users
├── id              BIGINT PK AUTO_INCREMENT
├── phone           VARCHAR(20) UNIQUE NOT NULL    -- 手机号（登录凭证）
├── password        VARCHAR(255)                   -- BCrypt 密文，首次登录前为 NULL
├── nickname        VARCHAR(50)
├── avatar_url      VARCHAR(255)                   -- 头像 MinIO key
├── status          TINYINT DEFAULT 1              -- 0=禁用 1=正常
├── first_login     TINYINT DEFAULT 1              -- 0=已设密码 1=首次登录待设密码
├── last_login_time DATETIME
├── create_time     DATETIME
└── update_time     DATETIME
```

**设计要点**：
- `password` 可为 NULL——验证码登录时自动注册，首次登录后强制设置密码
- `first_login` 标记驱动前端跳转"设置密码"页面
- BCrypt 加密和 mall-admin 的 `UmsAdmin` 完全一致

### 3.2 文件系统（files）

```sql
files
├── id              BIGINT PK AUTO_INCREMENT
├── uploader_id     BIGINT FK → users.id              -- 上传者（展示用，非权限隔离用）
├── parent_id       BIGINT FK → files.id              -- 树形结构，根目录 = 0
├── file_name       VARCHAR(255) NOT NULL
├── file_path       VARCHAR(500)                       -- 虚拟路径：/工作/项目/文档.pdf
├── storage_key     VARCHAR(500)                       -- MinIO key：{userId}/2026/06/file.pdf
├── file_type       VARCHAR(20)                        -- FOLDER / IMAGE / VIDEO / DOCUMENT / OTHER
├── file_size       BIGINT DEFAULT 0
├── content_type    VARCHAR(100)                       -- MIME：image/png, application/pdf
├── thumbnail_key   VARCHAR(500)                       -- 缩略图 MinIO key
├── is_folder       TINYINT DEFAULT 0                  -- 0=文件 1=文件夹
├── origin_text     LONGTEXT                           -- PDF 解析/OCR 提取的原始文本（ES 索引用）
├── process_status  TINYINT DEFAULT 0                  -- 0=待处理 1=缩略图完成 2=文本提取完成 3=索引完成 -1=失败
├── md5             VARCHAR(32)                        -- 文件 MD5，秒传去重用
├── create_time     DATETIME
├── update_time     DATETIME
└── delete_time     DATETIME                           -- 软删除（回收站功能）
```

**设计要点**：
- 文件和文件夹用同一张表，`is_folder` 区分——单表树形结构比父子两张表更简洁
- `origin_text` 存 PDF/图片 OCR 后的全量文字，作为 ES 索引的数据源
- `process_status` 跟踪异步处理进度，前端可查询展示
- `md5` 实现秒传——相同文件不重复存储

### 3.3 收藏（file_favorites）

```sql
file_favorites
├── id              BIGINT PK AUTO_INCREMENT
├── user_id         BIGINT FK → users.id
├── file_id         BIGINT FK → files.id
├── create_time     DATETIME
└── UNIQUE(user_id, file_id)
```

**设计要点**：收藏是唯一需要 `user_id` 的表——共享文件池中每人独立收藏。唯一约束防止重复收藏。

---

## 四、认证与安全

### 4.1 验证码安全（三层 Redis 防护）

```
allahpan:authCode:{phone}          值: "483921"     TTL: 300s（5 分钟有效期）
allahpan:authCode:sendLimit:{phone}  值: "1"         TTL: 30s（发送间隔）
allahpan:authCode:attempts:{phone}   值: "3"         TTL: 3600s（一小时错误计数，50 次上限）
```

```
发送验证码流程：
  ① 检查 sendLimit key → 存在则拒绝（"请 30 秒后再试"）
  ② 生成 6 位随机码
  ③ SET authCode:{phone} = code, TTL 300s
  ④ SET sendLimit:{phone} = 1, TTL 30s

验证验证码流程：
  ① GET authCode:{phone}
     → Redis 挂了？@CacheException 直接抛异常（验证码不可降级，安全底线）
  ② GET attempts:{phone} ≥ 50？→ 拒绝（"操作过于频繁"）
  ③ 比对失败 → INCR attempts → 返回通用错误（不暴露剩余次数）
  ④ 比对成功 → DEL authCode → 不删 attempts（保留小时计数）
```

### 4.2 与 mall 验证码的对比

| 安全维度 | mall-portal | AllahPan |
|---------|-----------|----------|
| 验证码有效期 | 90s TTL | 300s TTL |
| 发送频率限制 | ❌ 无 | 30s 间隔 |
| 小时重试上限 | ❌ 无 | 50 次/小时 |
| 超限策略 | ❌ 无 | 超限验证码作废 |
| 失败提示 | 单一错误消息 | 不暴露剩余次数 |
| Redis 异常处理 | @CacheException 抛异常 | 一致 |

> **简历要点**：从 mall 的 1 层防护（仅过期）升级到 3 层（过期 + 发送间隔 + 小时上限），讲清楚每层防什么攻击。

### 4.3 登录状态机

```
用户输入手机号
    │
    ├─ 有密码 → 密码登录通道 → BCrypt 验证 → 返回 JWT
    │
    └─ 无密码/忘记密码 → 验证码登录通道
                              │
                        验证码校验通过
                              │
                        用户不存在？→ 自动注册（INSERT users）
                        用户存在但 first_login=1？→ 同样允许登录
                              │
                        返回 JWT（含 firstLoginFlag）
                              │
                        前端判断 firstLoginFlag
                              │
                        强制跳转"设置密码"页面
                              │
                        POST /api/user/set-password
                        BCrypt 加密 → first_login=0
                              │
                        返回新 JWT（hasPassword=true）
                        后续走密码登录
```

### 4.4 JWT 设计

```java
JWT Payload:
  sub: phone                    // 手机号
  userId: 1001                  // 用户 ID
  hasPassword: true             // 是否已设置密码
  created: 1699123456789        // 签发时间戳
  exp: 1699187056789            // 过期时间（7 天）

Token 前缀: Bearer
签名算法: HS512
Secret: allahpan-jwt-secret
刷新策略: 距过期 < 30 分钟时自动刷新（和 mall 一致）
```

### 4.5 权限模型

**共享网盘，不走 mall 的 RBAC**——所有用户看到同一个文件池。权限模型简化：

```
JWT 验证 → 你是注册用户？→ 可访问所有文件 API
                              → 收藏按 user_id 隔离（每个人收藏自己的）
```

| | mall-admin | AllahPan |
|---|---|---|
| 权限模型 | 用户→角色→资源 URL，4 表关联 | 注册用户即可访问 |
| 数据隔离 | URL 级鉴权（DynamicAuthorizationManager） | 无（共享文件池） |
| 白名单 | 登录接口 + Swagger | 登录接口 + Swagger |

> **简历要点**：讲清楚为什么简化——mall 是后台管理系统（运营/客服/管理员各有权限），AllahPan 是共享空间，权限模型跟着业务场景走，不套模板。这是架构判断力。

---

## 五、文件上传与处理流水线

### 5.1 上传流程（MinIO 预签名 URL 直传）

```
前端                                   后端                            MinIO
 │                                      │                                │
 │  ① 计算文件 MD5（Web Crypto API）     │                                │
 │                                      │                                │
 │  POST /api/file/pre-upload           │                                │
 │  {md5, fileName, parentId}           │                                │
 │  ──────────────────────────────────→ │                                │
 │                                      │  查 files WHERE md5 = ?       │
 │                                      │  → 存在？秒传成功，返回 OK     │
 │                                      │  → 不存在？生成 storageKey     │
 │                                      │                                │
 │                      返回 {storageKey, preSignedUrl}                  │
 │  ←────────────────────────────────── │                                │
 │                                      │                                │
 │  ② PUT 文件流到 preSignedUrl         │                                │
 │  ─────────────────────────────────────────────────────────────────→ │
 │                                      │                 文件直接存入 MinIO
 │  ←───────────────────────────────────────────────────────────────── │
 │                                      │                                │
 │  POST /api/file/confirm-upload       │                                │
 │  {storageKey, fileName, ...}         │                                │
 │  ──────────────────────────────────→ │                                │
 │                                      │  INSERT files (process_status=0)
 │                                      │  发送 RabbitMQ 消息             │
 │                      返回 fileId     │                                │
```

**为什么用预签名 URL 而不是后端中转？**

| | 后端中转 | MinIO 预签名 URL |
|---|---|---|
| 大文件上传 | 文件流经 Spring Boot → 内存/网络 → MinIO，Tomcat 线程阻塞 | 前端直传 MinIO，后端只处理元数据 |
| 并发能力 | 受 Tomcat 线程池（默认 200）限制 | MinIO 原生 S3 协议，无应用层瓶颈 |
| 架构价值 | 无亮点 | S3 协议、签名算法、客户端直传——三个面试点 |

### 5.2 文件处理状态机（RabbitMQ 单队列 + 阶段枚举）

```
file.process.queue ──→ Consumer.handle(message)
                           │
                           switch(message.stage):
                             case UPLOADED:
                               → 生成缩略图（ImageIO / PDFBox / FFmpeg）
                               → 上传缩略图到 MinIO
                               → UPDATE files.process_status = 1
                               → re-send({stage: THUMBNAILED})
                             
                             case THUMBNAILED:
                               → 提取文本（PDF: PDFBox / 图片: Ollama OCR）
                               → UPDATE files.origin_text
                               → UPDATE files.process_status = 2
                               → re-send({stage: TEXT_EXTRACTED})
                             
                             case TEXT_EXTRACTED:
                               → 写入 ES 索引
                               → UPDATE files.process_status = 3 (INDEXED)
                               → 完成 ✓
                             
                             default: FAILED → 重试逻辑

消息体：
{
  "fileId": 1001,
  "currentStage": "THUMBNAILED",
  "retryCount": 0,
  "lastError": null
}
```

### 5.3 各阶段处理

| 阶段 | 适用文件类型 | 处理方式 | 工具 |
|------|------------|---------|------|
| UPLOADED → 缩略图 | IMAGE | 直接缩放 | Java ImageIO |
| | PDF | 提取首页渲染 | Apache PDFBox |
| | VIDEO | 截取第 5 秒帧 | FFmpeg 命令行 |
| THUMBNAILED → 文本 | PDF | 提取全文 | Apache PDFBox |
| | IMAGE | OCR 识别 | Ollama 千问3-VL |
| TEXT_EXTRACTED → ES | 所有类型 | 写入索引 | Spring Data ES |

### 5.4 失败重试（复用 mall 的 TTL 延迟重试）

```
处理失败 → retryCount < 3？
  ├─ Yes → 发送到延迟队列（TTL 递增: 30s / 60s / 120s）
  │         过期后重新进入 file.process.queue
  └─ No  → process_status = -1 (FAILED)，停止重试
```

### 5.5 前端进度查询

```
GET /api/file/{id}/status

{
  "fileId": 1001,
  "fileName": "发票.pdf",
  "processStatus": "TEXT_EXTRACTED",
  "statusLabel": "文本提取中...",
  "thumbnailReady": true,
  "textReady": false
}
```

### 5.6 与 mall RabbitMQ 的对比

| | mall 订单取消 | AllahPan 文件处理 |
|---|---|---|
| 模式 | TTL + DLX 延迟队列 | 单队列 + 状态机 |
| 阶段数 | 1 个（等 30 分钟 → 取消） | 3 个（缩略图 → 文本 → 索引） |
| 依赖关系 | 无（只等时间） | 有（OCR 依赖缩略图，ES 依赖 OCR） |
| 适用场景 | "一段时间后做一件事" | "多阶段处理，后继依赖前驱" |

> **简历要点**：同一套 RabbitMQ，两种架构模式。讲清楚什么场景用哪种——这是一个工程师的判断力，不是生搬硬套。

---

## 六、智能搜索

### 6.1 ES 文档设计

```java
@Document(indexName = "allahpan_files")
@Setting(shards = 1, replicas = 0)
public class EsFile {
    @Id
    private Long fileId;

    @Field(type = FieldType.Text, analyzer = "ik_max_word")
    private String fileName;              // 索引权重 10

    @Field(type = FieldType.Keyword)
    private String fileType;              // IMAGE / VIDEO / DOCUMENT / FOLDER / OTHER

    @Field(type = FieldType.Text, analyzer = "ik_max_word")
    private String originText;            // 索引权重 5（PDF 解析 + OCR 文本）

    @Field(type = FieldType.Keyword)
    private String filePath;              // 精确匹配

    private Long uploaderId;
    @Field(type = FieldType.Keyword)
    private String uploaderName;

    private Long fileSize;
    private Boolean isFolder;
    private Date createTime;
}
```

### 6.2 搜索查询（function_score + 高亮）

```java
SearchRequest request = SearchRequest.of(s -> s
    .index("allahpan_files")
    .query(q -> q
        .functionScore(fs -> fs
            .query(q2 -> q2
                .bool(b -> b
                    .must(m -> m
                        .multiMatch(mm -> mm
                            .fields("fileName^10", "originText^5")
                            .query(keyword)
                            .type(TextQueryType.BestFields)
                        )
                    )
                    .filter(filterByType(fileType))  // 按类型过滤
                )
            )
        )
    )
    .highlight(h -> h
        .fields("fileName", hf -> hf.numberOfFragments(0))     // 完整字段
        .fields("originText", hf -> hf                         // 内容片段
            .numberOfFragments(3)
            .fragmentSize(100)
        )
        .preTags("<mark>")
        .postTags("</mark>")
    )
    .aggregations("fileTypes", a -> a
        .terms(t -> t.field("fileType").size(10))
    )
    .from((pageNum - 1) * pageSize)
    .size(pageSize)
);
```

### 6.3 搜索结果响应

```json
{
  "list": [
    {
      "fileId": 1001,
      "fileName": "2024年报销<b>发票</b>汇总.pdf",
      "fileNameHighlight": "2024年报销<mark>发票</mark>汇总.pdf",
      "contentSnippets": [
        "这是一张办公用品<mark>发票</mark>，总金额为 3980 元...",
        "请于 30 日内完成<mark>发票</mark>报销流程"
      ],
      "fileType": "DOCUMENT",
      "filePath": "/工作/报销",
      "uploaderName": "张三",
      "fileSize": 2456789,
      "createTime": "2024-03-15",
      "score": 15.8
    }
  ],
  "totalCount": 47,
  "aggregations": {
    "fileTypes": [
      {"type": "DOCUMENT", "count": 30},
      {"type": "IMAGE", "count": 12},
      {"type": "OTHER", "count": 5}
    ]
  }
}
```

### 6.4 与 mall-search 对比

| | mall-search（商品） | AllahPan（文件） |
|---|---|---|
| 全文检索字段 | name(10) + subTitle(5) + keywords(2) | fileName(10) + originText(5) |
| 高亮字段 | name | fileName + originText（片段） |
| 聚合维度 | 品牌 + 分类 + 属性（Nested） | fileType（简单 terms） |
| 排序 | function_score + 销量 | function_score + 创建时间 |
| 数据来源 | MySQL 多表 JOIN（复杂 resultMap） | MySQL 单表 files（更简单） |

### 6.5 渐进式搜索可用性

文件上传后搜索立即可用（按文件名），OCR 完成后可搜文件内容。ES 索引和数据库之间采用应用层同步（和 mall 一致），全量重建索引通过管理接口触发。

---

## 七、部署架构

### 7.1 Docker Compose 编排（Cloudflare Tunnel 一键部署）

> 通过 Cloudflare Tunnel 暴露服务到公网，无需开放宿主机端口（80/443），Cloudflare 自动处理 SSL/TLS 终止、证书续签和 DDoS 防护。`cloudflared` 守护进程通过出站 WebSocket 连接将流量从 Cloudflare 边缘节点转发到本地 nginx。

```yaml
# docker-compose.yml
services:

  # ========== Cloudflare Tunnel ==========
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel run
    volumes:
      - ./cloudflared/config.yml:/etc/cloudflared/config.yml
      - ./cloudflared/credentials.json:/etc/cloudflared/credentials.json
    depends_on:
      - nginx
    restart: unless-stopped

  # ========== 网关层 ==========
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"       # 仅本地测试；公网流量走 Cloudflare Tunnel
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./allahpan-web/dist:/usr/share/nginx/html   # Vue 前端
    depends_on:
      - allahpan-core
      - allahpan-search

  # ========== 应用层 ==========
  allahpan-core:
    build: ./allahpan-core
    # 不映射宿主机端口（cloudflared → nginx → core 走 Docker 内网）
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    depends_on:
      - mysql
      - redis
      - minio
      - rabbitmq

  allahpan-search:
    build: ./allahpan-search
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    depends_on:
      - elasticsearch

  # ========== 数据层 ==========
  mysql:
    image: mysql:8.0
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: allahpan
    volumes:
      - ./docker-data/mysql:/var/lib/mysql

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
    volumes:
      - ./docker-data/redis:/data

  minio:
    image: minio/minio
    ports:
      - "9000:9000"     # API
      - "9001:9001"     # Web Console
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ./docker-data/minio:/data
    command: server /data --console-address ":9001"

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"     # AMQP
      - "15672:15672"   # Management UI
    volumes:
      - ./docker-data/rabbitmq:/var/lib/rabbitmq

  elasticsearch:
    image: elasticsearch:7.17.0
    ports:
      - "9200:9200"
    environment:
      - "discovery.type=single-node"
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - ./docker-data/es:/usr/share/elasticsearch/data

# ========== 宿主机原生 ==========
# Ollama — 不在 Compose 里，需要单独启动
# 原因：Docker Desktop on Mac/Windows 无 GPU 直通，MLX/CUDA 加速无法使用
```

**nginx 职责**：

| 路由 | 目标 | 说明 |
|------|------|------|
| `/` | Vue 静态文件 | 前端 SPA |
| `/api/*` | allahpan-core:8080 | 所有业务 API（含用户搜索） |
| `/es-admin/*` | allahpan-search:8081 | ES 管理接口（仅内网，重建索引等） |

> SSL/TLS 由 Cloudflare 在边缘节点自动处理，nginx 只监听 80 端口接收来自 cloudflared 的 HTTP 流量。

**一键命令**：

```bash
# 生产环境部署
docker compose up -d                    # 拉镜像 + 启动所有容器
docker compose ps                       # 查看运行状态
docker compose logs -f cloudflared      # 确认隧道已连接
docker compose logs -f allahpan-core    # 查看应用日志

# Cloudflare Tunnel 首次设置（仅一次）:
# 1. 在 Cloudflare Zero Trust (one.dash.cloudflare.com) 创建 Tunnel
# 2. 下载 credentials.json 到 cloudflared/ 目录
# 3. 编辑 cloudflared/config.yml 填入你的域名和 tunnel ID
# 4. docker compose up -d 即可
```

### 7.2 Ollama 为什么不在 Docker 里

| 部署方式 | GPU 加速 | 原因 |
|---------|---------|------|
| Mac 原生 `brew install ollama` | ✅ 全速 MLX | 直接访问 Apple Silicon 统一内存 + Neural Accelerator |
| Docker 容器内 | ❌ 不行 | Docker Desktop on Mac 跑在 Linux VM 内，无 GPU 直通 |

Ollama 0.19+ 默认使用 Apple MLX 框架，推理速度比旧版 llama.cpp Metal 方案快约 2 倍。

### 7.3 开发环境（跨平台：Windows / Mac / Linux）

```
本地开发机（Windows / Mac / Linux）
├── Docker Desktop / OrbStack / Podman
│   ├── MySQL
│   ├── Redis
│   ├── MinIO
│   ├── RabbitMQ
│   └── Elasticsearch
│
├── IDE 直接运行
│   ├── allahpan-core（Spring Boot DevTools 热部署）
│   └── allahpan-search
│
├── 终端
│   └── npm run dev（Vue + Vite HMR）
│
└── Ollama Windows 原生安装
    └── 千问3-VL 模型
```

多环境配置：`application-dev.yml` ↔ `application-prod.yml`，和 mall 项目一致。

---

## 八、简历 5 个深度问题

### 1. "为什么文件上传走 MinIO 预签名而不走后端中转？"

大文件不经过 Spring Boot——Tomcat 线程不阻塞，MinIO 原生 S3 协议直传。后端只处理元数据（几十字节），不在上传数据路径上。预签名 URL 有时效性（默认 5 分钟），安全性由签名算法保证。

### 2. "RabbitMQ 为什么不用 DLX 延迟队列？"

DLX 适合"等一段时间后做一件事"（如订单 30 分钟未付取消）。文件处理是"做多件事，每件事依赖前一步的结果"（缩略图 → OCR → ES 索引）。用状态机 + 同一队列复投更自然——每个 stage 枚举值对应一种 handler，阶段流转清晰，前端可查询进度。

### 3. "验证码安全比 mall 多了什么？"

mall 只做了 TTL 过期（1 层）。AllahPan 加了发送间隔（防短信轰炸）和小时重试上限（防暴力破解），共 3 层。全部用 Redis TTL 自然过期，不落 MySQL 减少攻击面。

### 4. "ES 怎么搜到图片里的文字？"

图片上传后，状态机触发 OCR 阶段——Ollama 本地千问3-VL 模型提取图片中文字，写入 `files.origin_text`，然后索引到 ES 的 `originText` 字段（ik_max_word 分词）。用户搜"发票"时，命中的是 OCR 后的文字索引，不是原始图片。

### 5. "为什么 ES 单独拆一个模块？"

搜索和核心业务解耦——搜索挂了不影响文件浏览/上传（参考 mall 的模块拆分）。ES 对内存要求高，独立部署可单独扩容或降配。模块间通过 Maven 依赖 + 应用层调用来通信，不走 HTTP 微服务——保持简单。

---

## 九、关键文件索引（目标结构）

```
allahpan/
├── pom.xml                          # Maven 聚合 POM
├── docker-compose.yml               # 一键编排
├── docker-compose-dev.yml           # 开发环境精简版
│
├── allahpan-common/
│   └── src/main/java/com/allahpan/common/
│       ├── api/CommonResult.java
│       ├── api/CommonPage.java
│       ├── exception/ApiException.java
│       ├── exception/GlobalExceptionHandler.java
│       ├── service/RedisService.java
│       ├── service/impl/RedisServiceImpl.java
│       ├── config/BaseRedisConfig.java       # 复用 mall 的 Jackson JSON 序列化
│       └── util/MinioUtil.java               # 新增：预签名 URL 生成、bucket 操作
│
├── allahpan-security/
│   └── src/main/java/com/allahpan/security/
│       ├── util/JwtTokenUtil.java            # 复用 mall 的 Hutool JWT
│       ├── component/JwtAuthenticationTokenFilter.java
│       ├── component/RestAuthenticationEntryPoint.java
│       ├── component/RestfulAccessDeniedHandler.java
│       ├── config/SecurityConfig.java
│       ├── aspect/RedisCacheAspect.java      # 复用 mall 的缓存降级切面
│       └── annotation/CacheException.java
│
├── allahpan-mbg/
│   ├── generatorConfig.xml
│   └── src/main/java/com/allahpan/mbg/
│       ├── Generator.java
│       ├── model/                             # 生成实体类
│       └── mapper/                            # 生成 Mapper
│
├── allahpan-core/
│   └── src/main/java/com/allahpan/
│       ├── controller/
│       │   ├── AuthController.java           # 验证码发送、双通道登录
│       │   ├── UserController.java           # 设置密码、个人信息
│       │   ├── FileController.java           # 文件 CRUD、上传预签名、目录树
│       │   ├── FavoriteController.java       # 收藏管理
│       │   └── SearchController.java         # 搜索代理（调 allahpan-search）
│       │
│       ├── service/
│       │   ├── UserService.java / impl/
│       │   ├── FileService.java / impl/
│       │   ├── FavoriteService.java / impl/
│       │   ├── UserCacheService.java
│       │   └── impl/UserCacheServiceImpl.java  # 复用 mall 的 CacheService 模式
│       │
│       ├── dao/                               # 手写复杂 SQL
│       │
│       ├── component/
│       │   ├── FileProcessSender.java         # 发送文件处理消息
│       │   ├── FileProcessReceiver.java       # 状态机消费者
│       │   ├── SmsService.java                # 短信发送（开发期 mock）
│       │   └── OllamaService.java             # 千问3-VL OCR 调用
│       │
│       └── config/
│           ├── MinioConfig.java
│           ├── RabbitMqConfig.java            # 复用 mall 的 DLX 模式（重试用）
│           └── ThreadPoolConfig.java
│
├── allahpan-search/
│   └── src/main/java/com/allahpan/search/
│       ├── domain/
│       │   └── EsFile.java                    # ES 文档定义
│       ├── repository/
│       │   └── EsFileRepository.java
│       ├── service/
│       │   └── impl/EsFileServiceImpl.java   # 搜索、高亮、聚合
│       └── controller/
│           └── EsFileController.java
│
└── allahpan-web/                              # Vue 3 前端
    └── src/
        ├── views/
        │   ├── Login.vue                      # 双通道登录页
        │   ├── SetPassword.vue                # 首次设置密码
        │   ├── FileBrowser.vue                # 文件浏览器（树形 + 网格）
        │   ├── Favorites.vue                  # 收藏夹
        │   └── Search.vue                     # 搜索结果（高亮）
        ├── components/
        │   ├── FileUpload.vue                 # 拖拽上传 + 按钮上传
        │   ├── FileCard.vue                   # 文件卡片（缩略图 + 进度）
        │   └── FolderTree.vue                 # 目录树
        └── api/                               # Axios 封装
```

---

## 十、开发顺序

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 1 | 项目骨架：Maven 聚合 + common + mbg 生成 | 无 |
| 2 | 认证模块：security + 验证码 + 双通道登录 | 阶段 1 |
| 3 | 文件模块：MinIO 直传 + 目录树 + 缩略图上传 | 阶段 2 |
| 4 | 处理流水线：RabbitMQ 状态机 + PDF 解析 + Ollama OCR | 阶段 3 |
| 5 | 搜索模块：ES 索引 + 高亮搜索 + 聚合 | 阶段 4 |
| 6 | 收藏模块：收藏夹 CRUD | 阶段 3 |
| 7 | 前端：Vue 页面 + 组件 | 阶段 2-6 |
| 8 | 部署：Docker Compose + Cloudflare Tunnel | 阶段 7 |

---

> 设计完成。下一步：`writing-plans` 技能将本设计转化为可执行的实现计划。
