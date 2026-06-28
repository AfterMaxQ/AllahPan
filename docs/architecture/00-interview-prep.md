# AllahPan 面试复习指南

> 跟着本文档过一遍代码，面试时能清晰讲清楚架构设计。

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构图](#2-整体架构图)
3. [技术栈速览](#3-技术栈速览)
4. [认证流程](#4-认证流程)
5. [文件上传体系](#5-文件上传体系)
6. [文件处理流水线](#6-文件处理流水线)
7. [存储模型](#7-存储模型)
8. [搜索架构](#8-搜索架构)
9. [缓存策略](#9-缓存策略)
10. [前端架构](#10-前端架构)
11. [部署架构](#11-部署架构)
12. [关键设计决策](#12-关键设计决策)
13. [代码走读清单](#13-代码走读清单)

---

## 1. 项目概述

**AllahPan** — 家庭共享云盘系统。支持大文件分片上传、秒传、在线预览、全文搜索、分享链接。

**核心价值：**
- 家庭场景的文件存储与共享
- 大文件（GB 级）稳定上传：分片 + 断点续传
- 智能文件处理：缩略图 → OCR/文本提取 → 全文搜索
- 一键容器化部署：`docker-compose up -d`

**规模：** 后端 ~50 个 Java 文件，前端 ~45 个 Vue/JS 文件，8 个 Docker 容器。

---

## 2. 整体架构图

### 2.1 部署拓扑

```
                    Internet
                       │
              Cloudflare Tunnel (HTTPS)
                       │
              cloudflared (Windows 服务)
                       │
              nginx :88 (容器)
              ├─ 静态文件 (Vue SPA)
              └─ /api/* → core:8088
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   core :8088     search :8081   基础设施
   (主应用)       (搜索微服务)    ├─ MySQL :3307
        │              │         ├─ Redis :6379
        │              │         ├─ RabbitMQ :5672
        │              │         ├─ Elasticsearch :9200
        │              │         └─ MinIO :9000
        └──── REST ────┘
```

### 2.2 Maven 模块依赖

```
allahpan-common       ← 基础工具（Redis、异常、响应封装）
    ↑
allahpan-mbg          ← 数据层（MyBatis Generator 实体/Mapper）
    ↑
allahpan-security     ← 安全层（JWT + Spring Security）
    ↑
allahpan-core (:8088) ← 主应用入口
    (独立)
allahpan-search (:8081) ← 搜索微服务入口（仅依赖 common）
```

**设计意图：** common 被所有模块依赖而无循环依赖；mbg 隔离使代码生成可重复执行不影响业务；security 隔离可独立测试过滤器链；search 独立部署可单独扩缩容。

> 关键文件：根 `pom.xml` → `modules` 声明 → 各子模块 `pom.xml` → `dependencies`

---

## 3. 技术栈速览

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 框架 | Spring Boot | 3.5.14 | 生态成熟，自动配置 |
| JDK | Java | 17 | LTS，虚拟线程支持 |
| ORM | MyBatis + MBG | 3.5 | SQL 可控，代码生成减少重复 |
| 连接池 | Druid | 1.2 | 监控 + 防火墙 |
| 分页 | PageHelper | 6.1 | MyBatis 插件式分页 |
| 安全 | Spring Security + JWT | Hutool JWT | 无状态认证，适合分布式 |
| 缓存 | Redis (Jedis) | 7.0 | 高性能，支持 Bitmap (Bloom Filter) |
| 消息队列 | RabbitMQ | 3.12 | 可靠投递，TTL+DLX 延迟重试 |
| 搜索引擎 | Elasticsearch | 8.11 | IK 中文分词，全文搜索 |
| 对象存储 | MinIO | latest | S3 兼容，自建无成本 |
| 文档处理 | PDFBox + POI | 3.0 / 5.5 | Apache 生态，覆盖常见格式 |
| AI/OCR | Ollama (qwen3.5:2b) | - | 本地运行，零成本 |
| 前端框架 | Vue 3 | 3.5 | Composition API，生态丰富 |
| 构建工具 | Vite | 8.0 | 极速 HMR |
| UI 库 | Element Plus | 2.14 | 中文生态好，组件齐全 |
| 状态管理 | Pinia | 3.0 | Vue 3 官方推荐 |
| HTTP | Axios | 1.17 | 拦截器链，进度回调 |

---

## 4. 认证流程

### 4.1 登录方式

两种登录 + 一种自注册：

| 方式 | 端点 | 说明 |
|------|------|------|
| 验证码登录 | `POST /api/auth/send-code` → `POST /api/auth/login-by-code` | 新用户自动注册 |
| 密码登录 | `POST /api/auth/login-by-password` | 已有密码的用户 |

**验证码流程：**
```
send-code → 生成6位数字 → Redis存5分钟 → QQ邮箱发送HTML邮件
login-by-code → 从Redis取码比对 → 失败计数(50次/小时锁) → 成功删码
用户不存在 → 自动注册(nickname=邮箱前缀, firstLogin=1) → BloomFilter添加 → 发Token
```

> 关键文件：`AuthCodeServiceImpl.java`, `UserServiceImpl.java`, `MailService.java`

### 4.2 JWT 令牌

| 属性 | 值 |
|------|-----|
| 算法 | HS512 (Hutool JWT) |
| Payload | `sub`(email), `user_id`, `hasPassword`, `created`, `exp` |
| 过期 | 7天 (604800s) |
| 刷新窗口 | 过期前 30 分钟 |

> 关键文件：`JwtTokenUtil.java`

### 4.3 Spring Security 过滤器链（**面试重点**）

```
请求到达
  │
  ├─ SecurityFilterChain
  │   ├─ CSRF 禁用
  │   ├─ SessionCreationPolicy.STATELESS （无HTTP Session）
  │   └─ authorizeHttpRequests:
  │       ├─ 白名单放行（auth、share、swagger、thumbnail/stream/download/watch）
  │       └─ 其余需要认证
  │
  ├─ JwtAuthenticationTokenFilter (OncePerRequestFilter)
  │   │  在每个请求上执行一次
  │   │  位置：在 UsernamePasswordAuthenticationFilter 之前
  │   │
  │   ├─ 1. 从 Header 取 "Authorization: Bearer <token>"
  │   ├─ 2. JwtTokenUtil.parseVerifiedToken() 验证签名
  │   ├─ 3. 提取 subject (email)
  │   ├─ 4. UserDetailsService.loadUserByUsername(email)
  │   │      └─ UserCacheService.getUser(email)
  │   │           ├─ BloomFilter.mightContain() → 不存在直接返回null
  │   │           ├─ Redis 查缓存 → 命中返回
  │   │           └─ MySQL 查询 → 回填 Redis
  │   ├─ 5. 校验 token 未过期
  │   └─ 6. 构建 UsernamePasswordAuthenticationToken 放入 SecurityContextHolder
  │
  ├─ 认证失败 → RestAuthenticationEntryPoint → JSON {code:401}
  └─ 权限不足 → RestfulAccessDeniedHandler → JSON {code:403}
```

**设计亮点：**
- 白名单 URL 配置化（`application.yml` 中 `secure.ignored.urls`）
- 无 RBAC——家庭场景所有认证用户权限相同，简单实用
- 错误响应全部 JSON（不是 302 重定向），适合 SPA

> 关键文件：`SecurityConfig.java`, `JwtAuthenticationTokenFilter.java`, `MallSecurityConfig.java`, `RestAuthenticationEntryPoint.java`, `RestfulAccessDeniedHandler.java`

### 4.4 首次登录密码设置

```
login-by-code 返回 { token, firstLogin: true }
  → 前端检测 firstLogin → 路由守卫强制跳转 /set-password
  → POST /api/user/set-password → BCrypt加密 → firstLogin=0
  → 返回新 token (hasPassword=true) → 前端更新 token
```

> 关键文件：`SetPassword.vue`, `router/index.js` 的 `beforeEach` 守卫

---

## 5. 文件上传体系

### 5.1 三种上传模式

| 模式 | 阈值 | 端点 | 特点 |
|------|------|------|------|
| 单文件上传 | < 10MB | `POST /api/file/upload` | 一个 multipart 请求完成 |
| 分片上传 | ≥ 10MB | `POST /api/file/chunk/*` | 10MB/片，6并发，断点续传 |
| 秒传 | 任意 | 自动检测 | MD5 匹配已有文件，跳过上传 |

### 5.2 分片上传完整流程

```
前端                                   后端
 │                                      │
 ├─ 1. SparkMD5 计算文件指纹 ──────────┤
 │   (2MB/片读取，进度 0~5%)             │
 │                                      │
 ├─ 2. initUpload() ──────────────────→│ 创建 Redis 会话
 │   {fileName, fileSize, fileMd5,     │  uploadId = UUID(md5+size+name)
 │    parentId, chunkSize, totalChunks}│  返回 {uploadId, uploadedChunks:[]}
 │                                      │
 ├─ 3. 并发上传分片 (6 workers)          │
 │   ┌─ worker1: chunk 0 ─────────────→│ 写入临时目录
 │   ├─ worker2: chunk 1 ─────────────→│ /tmp/allahpan-chunks/{uploadId}/
 │   ├─ worker3: chunk 2 ─────────────→│ Redis set 记录已完成分片索引
 │   ├─ worker4: chunk 3 ─────────────→│
 │   ├─ worker5: chunk 4 ─────────────→│
 │   └─ worker6: chunk 5 ─────────────→│
 │   (完成的分片通知其他 worker 抢新任务)  │
 │                                      │
 ├─ 4. completeUpload() ──────────────→│ 按序合并分片 → 单文件
 │                                      │ 上传到 MinIO (multipart 10MB/片)
 │                                      │ 计算 MD5 → 秒传检测
 │                                      │ 创建 DB 记录
 │                                      │ 发送 RabbitMQ 处理消息
 │                                      │ 广播 SSE 事件
 │                                      │ 清理临时分片
```

### 5.3 断点续传

```
用户中断上传 → 刷新页面 → 选择同一文件
  → initUpload 返回 {status:"resumed", uploadedChunks:[0,1,2,3]}
  → 前端跳过已上传的 4 个分片
  → 从第 5 个分片继续
```

**uploadId 确定性生成：** `UUID.nameUUIDFromBytes(md5 + fileSize + fileName)`，同一文件每次 init 得到相同 uploadId。

### 5.4 秒传（MD5 去重）

```
completeUpload 合并分片 → 计算 MD5
  → 查询 files 表: WHERE md5 = ? AND delete_time IS NULL
  → 找到 → 不重复上传 MinIO，直接创建新 DB 记录
  → 复制已有文件的 thumbnail_key 和 origin_text
```

### 5.5 MinIO 存储细节

| 参数 | 值 | 说明 |
|------|-----|------|
| partSize | 10 MB | MinIO 分片大小，启用 multipart 上传 |
| connectTimeout | 10s | OkHttp 连接超时 |
| readTimeout | 60s | 读取超时 |
| writeTimeout | 60s | 写入超时 |

> 关键文件：`ChunkUploadServiceImpl.java`, `MinioUtil.java`, `FileServiceImpl.java`
> 前端：`useChunkUpload.js`, `chunkUpload.js` (api), `transfer.js` (SpeedTracker)

---

## 6. 文件处理流水线

### 6.1 RabbitMQ 拓扑

```
                    allahpan.file.process (Direct Exchange)
                         │
                         │ rk: allahpan.file.process
                         ↓
              allahpan.file.process (Queue, Durable)
                         │
                         │ @RabbitListener
                         ↓
                 FileProcessReceiver
                    │        │
                    │        │ 失败 + retryCount < 3
                    │        ↓
                    │   allahpan.file.retry.direct (Exchange)
                    │        │
                    │        │ rk: allahpan.file.retry.ttl
                    │        ↓
                    │   allahpan.file.retry.ttl (Queue)
                    │   x-dead-letter-exchange: allahpan.file.process
                    │   x-message-ttl: 30s / 60s / 120s (指数退避)
                    │        │
                    │        │ TTL 过期 → DLX
                    │        ↓
                    │   (回到主队列)
                    │
                    │ 重试耗尽 → process_status = -1 (FAILED)
                    │           → 或降级保留部分结果
```

**重试策略：** 最多 3 次，间隔 30s → 60s → 120s（指数退避）。基础设施错误（网络/超时/Ollama）最终降级保留部分结果；致命错误（数据库写入失败）标记 FAILED。

> 关键文件：`RabbitMqConfig.java`, `FileProcessSender.java`, `FileProcessReceiver.java`

### 6.2 三阶段状态机

```
UPLOADED (0) ────→ THUMBNAILED (1) ────→ TEXT_EXTRACTED (2) ────→ COMPLETED (3)
      │                    │                      │
      │ 生成缩略图          │ 文本提取              │ ES 索引
      │                    │                      │
      ├─ IMAGE: ImageIO    ├─ IMAGE: Ollama OCR   └─ EsIndexService.index()
      │   300px 宽缩放      │   qwen3.5:2b 视觉模型
      │                     │
      ├─ PDF: PDFBox       ├─ PDF: PDFTextStripper
      │   首页渲染→缩放      │
      │                     ├─ DOCX/DOC: POI WordExtractor
      └─ 其他: 跳过          ├─ XLSX/XLS: POI ExcelExtractor
                            ├─ PPTX/PPT: POI SlideShow
                            └─ 纯文本: 直接读取
```

**每个阶段完成后：** 更新 DB `process_status` → 发送下阶段消息 → 广播 SSE 事件给在线前端。

> 关键文件：`ThumbnailGenerator.java`, `TextExtractor.java`, `OllamaService.java`, `EsIndexServiceImpl.java`

### 6.3 SSE 实时推送

```
GET /api/file/watch?token=JWT
  │
  └─ SseBroadcaster (CopyOnWriteArrayList<SseEmitter>)
       ├─ file-created: 新文件上传完成
       └─ file-updated: 文件处理状态变更 (processStatus)

前端 EventSource → onmessage → 解析事件 → triggerRefresh() → 重新加载文件列表
```

> 关键文件：`SseBroadcaster.java`, `useFileWatcher.js`

---

## 7. 存储模型

### 7.1 MinIO 三桶策略

| Bucket | 用途 | 生命周期 |
|--------|------|----------|
| `allahpan-files` | 原始文件 | 永久（软删除时移到 trash）|
| `allahpan-thumbnails` | JPEG 缩略图 | 文件永久删除时清理 |
| `allahpan-trash` | 软删除文件 | 定时清理（60天） |

**storageKey 命名规则：** `父目录链/文件名`

```
例：folderA/vacation/photo.jpg
    root/工作文档/2024/report.pdf
```

bucket 由 `@PostConstruct` 自动创建。

> 关键文件：`MinioUtil.java`, `MinioConfig.java`

### 7.2 MySQL 文件树结构

```sql
-- 核心表
files (
  id BIGINT PK,
  uploader_id BIGINT → users.id,
  parent_id BIGINT DEFAULT 0,     -- 0 = 根目录
  file_name VARCHAR(255),
  file_path VARCHAR(500),         -- 虚拟路径 /folderA/sub/file.txt
  storage_key VARCHAR(500),       -- MinIO 对象 key
  file_type ENUM,                 -- FOLDER | IMAGE | VIDEO | DOCUMENT | OTHER
  file_size BIGINT,
  content_type VARCHAR(100),      -- MIME
  thumbnail_key VARCHAR(500),
  is_folder TINYINT,
  process_status TINYINT,         -- 0→1→2→3 / -1
  md5 VARCHAR(32),
  origin_text LONGTEXT,           -- 提取的文本
  delete_time DATETIME,           -- NULL=活跃，非NULL=回收站
  create_time, update_time DATETIME
)

-- 唯一约束
UNIQUE (parent_id, file_name, delete_time)
  -- 同一目录下不允许同名文件，但回收站中可以

-- 索引
idx_parent_delete (parent_id, delete_time)  -- 列出目录内容
idx_md5_delete (md5, delete_time)           -- 秒传检测
idx_delete_time                              -- 回收站清理
```

### 7.3 文件操作的一致性模型

**DB 优先，MinIO 后置：** 先写 MySQL，再操作 MinIO。MySQL 失败则全部回滚，MinIO 失败则回滚 MySQL。保证 MySQL 始终是权威数据源。

```
renameFile:
  1. UPDATE files SET file_name=新名, file_path=新路径 WHERE id=?
  2. MinIO copyObject(旧key → 新key)
  3. MinIO removeObject(旧key)
  4. POST es-admin/files/index (更新ES)
  5. 如果是文件夹 → 递归更新所有子文件的 file_path
  任何步骤失败 → 回滚 MySQL
```

```
moveFile:
  1. 循环检测 (isDescendant) ─ 不能移动到自己的子文件夹
  2. 同名检测 ─ 目标目录不能有同名文件
  3. UPDATE files SET parent_id=新父ID, file_path=新路径
  4. MinIO 复制+删除(非文件夹) / 递归(文件夹)
```

> 关键文件：`FileServiceImpl.java`（~730行，最大Service）

---

## 8. 搜索架构

### 8.1 双服务通信

```
Core (:8088) ──── RestTemplate ────→ Search (:8081)
  │                                      │
  │ POST /es-admin/files/index           │ ElasticsearchRepository
  │ DELETE /es-admin/files/{id}          │ (Spring Data ES)
  │ GET /es-admin/files/search            │
  │ DELETE /es-admin/files/_all          ↓
  │ POST /es-admin/rebuild          Elasticsearch (:9200)
  │                                   │
  │                                   └─ index: allahpan_files
  ↓                                       (1 shard, 0 replicas)

前端 /api/search?keyword=xxx
  → Core SearchController
  → SearchServiceImpl (RestTemplate 调用 search 服务)
  → 返回高亮 + 聚合结果
```

**为何独立微服务？** ES 的 Spring Data Elasticsearch 依赖可能与主应用冲突（ES 客户端版本），独立部署隔离依赖。同时可独立扩缩容。

> 关键文件：`EsIndexServiceImpl.java`, `SearchServiceImpl.java`, `EsFileServiceImpl.java` (search模块)

### 8.2 搜索查询结构

```json
{
  "query": {
    "bool": {
      "must": [{
        "multi_match": {
          "query": "用户输入",
          "fields": ["fileName^10", "originText^5", "originText.char^2"],
          "type": "best_fields"
        }
      }],
      "should": [{
        "match": { "fileName": { "query": "用户输入", "boost": 50 } }
      }],
      "filter": [{ "term": { "fileType": "DOCUMENT" } }]  // 可选
    }
  },
  "highlight": {
    "fields": {
      "fileName": { "number_of_fragments": 0 },
      "originText": { "fragment_size": 100, "number_of_fragments": 3 }
    },
    "pre_tags": ["<mark>"], "post_tags": ["</mark>"]
  },
  "aggs": {
    "fileTypes": { "terms": { "field": "fileType" } }
  }
}
```

**设计要点：**
- `fileName^10` 确保文件名匹配权重最高
- `should` 子句中额外 +50 boost 让精确命中排名第一
- IK 分词器支持中文分词（"励志演讲" → "励志"/"演讲"）
- 聚合返回各类型文件计数（筛选器）

### 8.3 索引一致性保障

| 机制 | 频率 | 说明 |
|------|------|------|
| 实时索引 | 每个文件处理完成 | TEXT_EXTRACTED 阶段调用 `index()` |
| 启动全量重建 | 启动后 5 分钟内 | 等待 search 服务健康后 rebuildAll() |
| 定时全量重建 | 每 30 分钟 | 清理孤儿文档 |
| 失败重试 | 每 5 分钟 | pendingOps 补偿队列 |

> 关键文件：`EsIndexServiceImpl.java` → `scheduleStartupCleanup()`, `scheduledReconciliation()`, `retryFailedOps()`

---

## 9. 缓存策略

### 9.1 三级读取防御

```
getUserByEmail(email)
  │
  ├─ 1. BloomFilter.mightContain(email)
  │      ├─ false → 确定不存在，直接返回 null（防止缓存穿透）
  │      └─ true → 继续
  │
  ├─ 2. Redis GET allahpan:member:{email}
  │      └─ 命中 → 返回
  │
  └─ 3. MySQL SELECT * FROM users WHERE email=?
         └─ 查到 → SET allahpan:member:{email} (TTL 86400+随机0~300s)
                   → 回填缓存
```

### 9.2 缓存设计要点

| 场景 | 策略 | 说明 |
|------|------|------|
| 缓存穿透 | Bloom Filter (Redis Bitmap) | 布隆过滤器说"不存在"则一定不存在 |
| 缓存击穿 | 无特殊处理 | 用户缓存并发量不大，可接受 |
| 缓存雪崩 | TTL 随机偏移 (+0~300s) | 避免同时过期 |
| Redis 故障 | 注解驱动降级 | `@CacheException` 标注的方法抛异常；未标注的返回 null 降级 |

### 9.3 Bloom Filter 实现

```
参数: n=10000 预期元素, p=1% 误报率
位数组: m=95850 bits ≈ 12KB
哈希函数: k=7 (SHA-256 派生的 7 个索引)
键: {database}:bloom:user:email

启动时: BloomFilterInitializer (ApplicationRunner)
  → RESET bitmap → 加载所有用户email → 逐个ADD
注册时: UserServiceImpl.loginByCode()
  → BloomFilterService.add(email)
```

**误报率意味着什么？** 1% 的查询会穿透 Bloom Filter 到 Redis/MySQL，但这些查询可能是合法用户（缓存未命中），不会有性能问题。

### 9.4 Redis 键全景

| 键模式 | TTL | 用途 |
|--------|-----|------|
| `allahpan:member:{email}` | 24h+随机 | 用户对象缓存 |
| `allahpan:authCode:{email}` | 5min | 邮箱验证码 |
| `allahpan:sendLimit:{email}` | 30s | 发送频率限制 |
| `allahpan:attempts:{email}` | 1h | 验证失败计数（锁50次） |
| `allahpan:share:{code}` | expire+1h | 分享链接元数据 |
| `chunk:upload:{uploadId}` | 24h | 分片上传会话(Hash) |
| `chunk:upload:{uploadId}:chunks` | 24h | 已完成分片索引(Set) |
| `allahpan:bloom:user:email` | 永久 | 布隆过滤器位图 |

> 关键文件：`BaseRedisConfig.java`, `UserCacheServiceImpl.java`, `BloomFilterService.java`, `BloomFilterInitializer.java`, `RedisCacheAspect.java`

---

## 10. 前端架构

### 10.1 技术分层

```
视图层 (Vue 3 SFC <script setup>)
  ├─ 路由 (Vue Router 4, HTML5 History)
  ├─ 状态 (Pinia: userStore + fileStore, 其余 local ref)
  ├─ 业务逻辑 (Composables: useChunkUpload, useFileWatcher)
  └─ HTTP 层 (Axios 实例 → 拦截器链 → CommonResult 解包)
```

### 10.2 路由设计

| 路径 | 组件 | 认证 | 说明 |
|------|------|------|------|
| `/login` | Login.vue | 公开 | 验证码/密码登录 |
| `/set-password` | SetPassword.vue | 需认证 | 首次登录强制设置密码 |
| `/` | AppLayout → FileBrowser.vue | 需认证 | 主文件浏览器 |
| `/favorites` | AppLayout → Favorites.vue | 需认证 | 收藏列表 |
| `/search` | AppLayout → Search.vue | 需认证 | 搜索结果 |
| `/trash` | AppLayout → Trash.vue | 需认证 | 回收站 |
| `/share/:code` | SharedView.vue | 公开 | 分享页面 |

**路由守卫（`router.beforeEach`）核心逻辑：**
1. 非公开页面 + 无 token → `/login`
2. 有 token + firstLogin=true + 非 `/set-password` → `/set-password`
3. 已在 `/login` + 有 token → `/`（防止重复登录）

### 10.3 Pinia Store 设计

```
useUserStore:
  token (localStorage 持久化)
  isFirstLogin (localStorage 持久化)
  userInfo (内存)
  ├─ setAuth()        登录后设置
  ├─ updateTokenAfterSetPassword()  密码设置后换 token
  └─ logout()         清空所有状态 + localStorage

useFileStore:
  currentFolderId (内存, 0=根目录)
  viewMode (localStorage 持久化)
  refreshTrigger (整数计数器)
  ├─ setCurrentFolder()  导航到文件夹
  ├─ toggleViewMode()    网格/列表切换
  └─ triggerRefresh()    触发文件列表重载
```

**设计原则：** 跨路由持久化的状态放 Pinia；局部 UI 状态（loading/dialog/show/selected）放组件的 `ref`。

### 10.4 Axios 拦截器链

```
请求拦截器:
  取出 useUserStore().token
  → config.headers.Authorization = `Bearer ${token}`

响应拦截器(成功):
  检查 res.data.code:
  ├─ code === 200 → return res.data (剥除外层 CommonResult)
  ├─ code === 401 → 登出 + 跳转 /login + 提示
  └─ 其他 → Toast 错误 + reject

响应拦截器(错误):
  HTTP 401 → 登出 + 跳转
  其他 → Toast 通用错误
```

### 10.5 分片上传前端实现

```
useChunkUpload.js:
  uploadFiles(files, parentId, onTaskUpdate)
  │
  ├─ 小文件 (<10MB):
  │   └─ uploadSingleStep() → uploadFile() API → 进度回调
  │
  └─ 大文件 (≥10MB):
      └─ uploadWithChunks()
          ├─ calculateMD5() (SparkMD5, 2MB/片, 进度0~5%)
          ├─ initUpload() → {uploadId, uploadedChunks}
          ├─ 构建 pendingChunks 队列 (跳过已上传)
          ├─ 6 并发 worker 循环:
          │   ├─ 从队列取 chunk
          │   ├─ uploadChunk() → FormData → axios(onUploadProgress)
          │   ├─ SpeedTracker.addSample() → 计算 speed/ETA
          │   └─ onTaskUpdate({percent, loaded, speed, eta})
          └─ completeUpload(uploadId)

SpeedTracker (transfer.js):
  滑动窗口(5 samples) → getSpeed() → getETA(remainingBytes)
  formatSpeed/formatETA 人性化显示
```

**取消机制：** `cancelFlag` + `AbortController`，worker 检测取消后停止取队列，正在上传的请求 abort。

### 10.6 组件树（面试可画）

```
App.vue
└─ <router-view>
    ├─ Login.vue (独立页)
    ├─ SharedView.vue (独立页)
    └─ AppLayout.vue (主布局)
        ├─ AppSidebar.vue (导航 + 用户信息)
        ├─ AppHeader.vue (面包屑 + 搜索框)
        └─ <router-view> (带 fade-transform 过渡)
            ├─ FileBrowser.vue ★ 最复杂组件
            │   ├─ FileToolbar.vue
            │   ├─ FileGridView.vue → FileCard.vue
            │   ├─ FileListView.vue
            │   ├─ FileContextMenu.vue
            │   ├─ FileUploadDialog.vue (拖拽 + 文件夹选择 + 任务列表)
            │   ├─ FilePreviewDialog.vue (图片/视频/文档/文本)
            │   │   └─ FileDownloadDialog.vue
            │   ├─ FolderCreateDialog.vue
            │   └─ MoveFileDialog.vue
            ├─ Favorites.vue
            ├─ Search.vue → SearchResultItem.vue
            └─ Trash.vue
```

> 关键文件入口：`main.js`, `App.vue`, `router/index.js`, `stores/user.js`, `stores/file.js`, `api/index.js`

---

## 11. 部署架构

### 11.1 Docker Compose — 8 个容器

```
docker-compose up -d --build
├── mysql:8.0                   3307 → 3306
├── redis:7.0-alpine            6379
├── rabbitmq:3.12-management    5672, 15672
├── allahpan-elasticsearch:8.11 9200   (自构建，含 IK 分词器)
├── minio/minio                 9000, 9001
├── allahpan-core               8088   (Spring Boot JAR)
├── allahpan-search             8081   (Spring Boot JAR)
└── allahpan-nginx              88→80  (Vue SPA + /api/ 反代)
```

### 11.2 Docker 环境适配

本地开发用 `localhost`，Docker 内用服务名通信，通过环境变量覆盖：

```yaml
# docker-compose.yml 中 core 的环境变量
SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/...
SPRING_DATA_REDIS_HOST: redis
SPRING_RABBITMQ_HOST: rabbitmq
MINIO_ENDPOINT: http://minio:9000
```

### 11.3 Nginx 容器配置

```
server {
    listen 80;
    client_max_body_size 2048m;    ← 支持大文件上传

    location /api/ {
        proxy_pass http://core:8088;
        proxy_read_timeout 3600s;  ← SSE 长连接
        proxy_buffering off;       ← SSE 禁用缓冲
    }

    location / {
        try_files $uri /index.html; ← Vue SPA fallback
    }
}
```

### 11.4 公网访问链

```
Cloudflare Edge (SSL 终止, https://allahpan.cn)
  → cloudflared (Windows 服务, WebSocket 隧道)
  → localhost:88
  → allahpan-nginx 容器
  → allahpan-core 容器
```

**优势：** 无需开放入站端口，无需购买 SSL 证书，Cloudflare 自带 DDoS 防护。

### 11.5 一键启动

```powershell
# 首次/代码修改后
.\start-all.ps1 -Build   # mvn package → docker-compose up -d --build

# 日常重启
.\start-all.ps1           # docker-compose up -d
```

> 关键文件：`docker-compose.yml`, `start-all.ps1`, `docker/core/Dockerfile`, `docker/search/Dockerfile`, `docker/frontend/Dockerfile`, `docker/frontend/nginx.conf`

---

## 12. 关键设计决策

### 12.1 为什么不用 Spring Session？

**选择 JWT 无状态认证。** 家庭场景用户量小（几十人），不需要分布式 Session。JWT 直接校验，不依赖 Redis，降低 Redis 故障影响面。缺点是无法主动踢人——家庭场景不需要。

### 12.2 为什么 DB 优先而非 MinIO 优先？

```
写操作: MySQL 先写 → MinIO 后操作
失败时: MinIO 失败 → 回滚 MySQL

原因：
- MySQL 事务支持，回滚可靠
- MinIO 不支持事务
- MySQL 是业务数据的权威源
```

### 12.3 为什么搜索独立微服务？

- 依赖隔离：Spring Data ES 与主应用的 Spring 版本可能冲突
- 独立扩缩容：搜索压力大时可单独扩容
- 故障隔离：ES 挂了不影响文件上传和浏览
- 通信方式：REST（简单）而非 RabbitMQ（异步），因为索引是同步需求

### 12.4 为什么用 RabbitMQ 而非直接异步线程？

- 持久化：服务重启后消息不丢失
- 重试：TTL + DLX 实现指数退避，不需要自己写定时器
- 解耦：处理逻辑与上传逻辑分离，易于测试和排错
- 有序性：单队列保证处理顺序

### 12.5 为什么用 Redis 做分片上传状态？

- 分片会话是临时的（24h TTL），不需要持久化到 MySQL
- Redis 的 Set 数据结构天然适合存储已上传分片索引
- 断点续传的 uploadId 基于文件内容确定性生成，同文件重启后自动恢复

### 12.6 为什么软删除用 MinIO copy 而非 move？

```
误删恢复: 原始文件保持在 allahpan-files，复制到 allahpan-trash
引用计数: 同一 MD5 的文件可能被多条 DB 记录引用
永久删除: 只有当 trash 中的对象不再被任何 DB 记录引用时才物理删除
```

---

## 13. 代码走读清单

按以下顺序阅读，从底层到上层，从简单到复杂：

### 第一遍：基础设施层（理解项目骨架）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 1 | `pom.xml` | 模块声明 `<modules>`，版本号 `<properties>` |
| 2 | `allahpan-common/pom.xml` | 被谁依赖 |
| 3 | `allahpan-common/.../CommonResult.java` | API 响应格式 `{code, message, data}` |
| 4 | `allahpan-common/.../BaseRedisConfig.java` | RedisTemplate 配置，CacheManager |
| 5 | `allahpan-common/.../BloomFilterService.java` | Bitmap + SHA-256 哈希 |
| 6 | `init.sql` | 三张表的结构 |

### 第二遍：安全层（理解认证）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 7 | `allahpan-security/.../SecurityConfig.java` | 过滤器链、白名单、STATELESS |
| 8 | `allahpan-security/.../JwtTokenUtil.java` | HS512 生成/验证 |
| 9 | `allahpan-security/.../JwtAuthenticationTokenFilter.java` | doFilterInternal 全流程 |
| 10 | `allahpan-core/.../MallSecurityConfig.java` | UserDetailsService bean |
| 11 | `allahpan-core/.../UserCacheServiceImpl.java` | 三级读取 |
| 12 | `allahpan-core/.../AuthCodeServiceImpl.java` | 验证码发送与校验 |

### 第三遍：存储层（理解文件系统）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 13 | `allahpan-core/.../MinioUtil.java` | 三桶管理、putObject、copy/remove |
| 14 | `allahpan-core/.../MinioConfig.java` | MinioClient bean 创建 |
| 15 | `allahpan-core/.../FileServiceImpl.java` | upload/delete/rename/move/restore |

### 第四遍：上传体系（理解文件入口）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 16 | `allahpan-core/.../FileController.java` | 所有 REST 端点 |
| 17 | `allahpan-core/.../ChunkUploadServiceImpl.java` | init → upload → complete 三阶段 |
| 18 | 前端 `useChunkUpload.js` | 并发控制、进度聚合、断点续传 |
| 19 | 前端 `chunkUpload.js` | API 请求封装 |
| 20 | 前端 `transfer.js` | SpeedTracker 速率计算 |

### 第五遍：处理流水线（理解异步处理）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 21 | `allahpan-core/.../RabbitMqConfig.java` | 交换机、队列、绑定、TTL+DLX |
| 22 | `allahpan-core/.../FileProcessReceiver.java` | 三阶段状态机、重试逻辑、降级策略 |
| 23 | `allahpan-core/.../ThumbnailGenerator.java` | 图片/PDF 缩略图 |
| 24 | `allahpan-core/.../TextExtractor.java` | 多格式文本提取 |
| 25 | `allahpan-core/.../OllamaService.java` | Vision LLM OCR |

### 第六遍：搜索体系（理解全文搜索）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 26 | `allahpan-search/.../EsFileServiceImpl.java` | 索引 CRUD + 搜索查询构造 |
| 27 | `allahpan-search/.../EsFileController.java` | 搜索服务 REST 端点 |
| 28 | `allahpan-core/.../EsIndexServiceImpl.java` | Core→Search REST 通信、启动重建、定时对账 |

### 第七遍：前端（理解用户体验）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 29 | `allahpan-web/src/main.js` | 应用入口、插件注册 |
| 30 | `allahpan-web/src/router/index.js` | 路由守卫逻辑 |
| 31 | `allahpan-web/src/api/index.js` | Axios 拦截器链、CommonResult 解包 |
| 32 | `allahpan-web/src/stores/user.js` | 认证状态管理 |
| 33 | `allahpan-web/src/views/FileBrowser.vue` | 主界面，组合所有功能 |
| 34 | `allahpan-web/src/composables/useFileWatcher.js` | SSE 连接 |
| 35 | `allahpan-web/src/components/file/FileUploadDialog.vue` | 上传对话框 |
| 36 | `allahpan-web/src/styles/global.css` | 暖木色设计系统 |

### 第八遍：部署（理解运维）

| 顺序 | 文件 | 重点看什么 |
|------|------|------------|
| 37 | `docker-compose.yml` | 8 个服务定义、环境变量覆盖 |
| 38 | `docker/core/Dockerfile` | JRE 镜像 + JAR 复制 |
| 39 | `docker/frontend/Dockerfile` | 多阶段：npm build → nginx |
| 40 | `docker/frontend/nginx.conf` | SPA fallback、大文件 proxy、SSE |
| 41 | `start-all.ps1` | 一键启动脚本 |

---

## 附：面试常见问题自测

1. **Q: 如何处理大文件上传的稳定性？**
   A: 分片上传（10MB/片）+ 断点续传（Redis 状态）+ MinIO multipart（10MB/片）+ 6 并发前端 worker + AbortController 取消。

2. **Q: JWT 过期了怎么办？**
   A: 前端 Axios 拦截器检测 401 → 清空 token → 跳转登录页。JWT 过期前 30 分钟可以刷新（refresh 接口预留但未实现前端自动化，因为用户活跃期间会持续请求，401 后重新登录即可）。

3. **Q: 缓存穿透怎么解决？**
   A: Bloom Filter (Redis Bitmap) + 空值不缓存 + 启动时全量加载用户 email。三层：Bloom → Redis → MySQL。

4. **Q: RabbitMQ 消息丢了怎么办？**
   A: Exchange/Queue 声明为 durable；消息持久化；消费者手动确认（默认 auto-ack）；失败消息通过 TTL+DLX 重试 3 次；重试耗尽后标记 process_status=-1。

5. **Q: 如何保证数据库和 MinIO 的一致性？**
   A: DB 优先写 → MinIO 后操作 → 失败回滚 DB。MinIO 操作失败不会产生脏数据。定时孤儿扫描任务清理残留对象。

6. **Q: Elasticsearch 索引不一致了怎么修复？**
   A: 启动时全量重建（等 search 服务健康后）；每 30 分钟定时全量重建；每 5 分钟重试失败操作（pendingOps）；管理员手动 POST /api/search/rebuild-index。

7. **Q: 为什么选择 MinIO 而不是阿里云 OSS？**
   A: 家庭场景数据量小，自建零成本；S3 兼容 API，未来可无缝迁移到云存储。

8. **Q: 前端的核心性能优化有哪些？**
   A: 路由懒加载（dynamic import）；文件列表虚拟滚动（通过分页而非全量）；缩略图 URL 直接渲染（不经过 JS 处理）；静态资源长期缓存（/assets/ 30d）；Element Plus 按需引入（全量注册，但 tree-shaking 优化）。

9. **Q: 这个项目有哪些可以改进的地方？**
   A: (1) 无 RBAC——未来可加角色权限；(2) 文件版本管理——同名覆盖可改为版本链；(3) WebSocket 替代 SSE——双向通信更灵活；(4) 搜索服务的熔断降级——目前无 Hystrix/Sentinel；(5) 监控告警——目前无 Prometheus/Grafana；(6) 日志聚合——容器日志未集中收集。

10. **Q: 项目最大的技术挑战是什么？**
    A: 大文件分片上传的端到端可靠性——需要协调前端并发控制、Redis 会话状态、临时文件管理、MinIO multipart、MD5 秒传检测、断点续传恢复。涉及前端 composable → API 层 → Controller → Service → Redis → MinIO → DB 共 7 层的协同。修复过两个关键 Bug：MinIO 单次 PUT 超时（改为 multipart 10MB/片）和 resolveConflict 未分离目录路径。

---

> 最后更新：2026-06-28
