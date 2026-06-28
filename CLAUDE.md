# CLAUDE.md

## 项目概述

AllahPan — 家庭共享云盘系统。Spring Boot 3.5 多模块后端 + Vue 3 前端。

## 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | Spring Boot 3.5.14, Java 17 |
| ORM | MyBatis 3.5 + MyBatis Generator |
| 数据库 | MySQL 8.0 (Druid 连接池) |
| 缓存 | Redis 7.0 (Jedis) |
| 消息队列 | RabbitMQ 3.12 (Spring AMQP) |
| 搜索引擎 | Elasticsearch 8.11 (Spring Data ES) |
| 安全 | Spring Security + JWT (Hutool) |
| 文档处理 | PDFBox 3.0, Apache POI 5.5 |
| AI/OCR | Ollama (qwen3.5:2b) |
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Axios |

## 模块结构

```
allahpan/
├── allahpan-common/      工具层（API 响应、异常、Redis、AOP 日志）
├── allahpan-security/    安全层（JWT + Spring Security）
├── allahpan-mbg/         数据层（MBG 生成的实体/Mapper）
├── allahpan-core/        主应用 :8088（入口 AllahPanApplication）
├── allahpan-search/      搜索服务 :8081（入口 SearchApplication）
├── allahpan-web/         前端 Vue 3（独立项目，非 Maven 模块）
├── docker/               Dockerfile（core / search / frontend+nginx）
├── docs/                 架构 & API 文档
├── docker-compose.yml    全部 8 个服务容器编排
├── start-all.ps1         一键启动脚本
└── init.sql              数据库 DDL
```

**依赖链**: `common ← security ← mbg ← core(:8088)`，`search(:8081)` 仅依赖 `common`

- **可运行入口**: `allahpan-core` (`AllahPanApplication`, 8088) 和 `allahpan-search` (`SearchApplication`, 8081)
- **库模块**: `allahpan-common`, `allahpan-mbg`, `allahpan-security`（不可单独运行）

## 构建与运行

### 容器化部署（推荐）

```powershell
# 一键启动全部 8 个服务（首次/代码修改后加 -Build）
.\start-all.ps1 -Build

# 日常重启
.\start-all.ps1

# 停止
docker-compose down
```

`-Build` 会自动执行 `mvn package -DskipTests` 编译后端 JAR，然后 `docker-compose up -d --build` 构建镜像并启动所有容器。

### 开发模式

仅启动基础设施，后端和前端手动运行（方便热重载）：

```bash
# 1. 启动基础设施
docker-compose up -d mysql redis rabbitmq elasticsearch minio

# 2. 编译后端
mvn package -DskipTests

# 3. 启动主应用 (8088)
cd allahpan-core
mvn spring-boot:run

# 4. 启动搜索服务 (8081)
cd allahpan-search
mvn spring-boot:run

# 5. 启动前端 dev server (5173，热重载)
cd allahpan-web
npm run dev
```

## 基础设施 (docker-compose)

全部 8 个服务由 `docker-compose.yml` 编排，其中 3 个应用服务由 `docker/` 下的 Dockerfile 构建。

| 服务 | 端口 | 备注 |
|------|------|------|
| MySQL 8.0 | 3307 | 数据库 `allahpan`，密码 `123456` |
| Redis 7.0 | 6379 | 无密码 |
| RabbitMQ 3.12 | 5672 / 15672 | 管理界面，guest/guest |
| Elasticsearch 8.11 | 9200 | 单节点，安全已禁用，IK 分词器 |
| MinIO | 9000 / 9001 | 对象存储，minioadmin/minioadmin |
| allahpan-core | 8088 | 主后端 API（Spring Boot JAR） |
| allahpan-search | 8081 | 搜索服务（Spring Boot JAR） |
| allahpan-nginx | 88 | 前端静态文件 + `/api/` 反代到 core |

基础设施容器启动后无需重建；应用容器通过 `docker-compose up -d --build` 增量更新。

Docker 环境变量覆盖（`docker-compose.yml` 中 `environment`）：
- 服务间通过 Docker 服务名通信（`mysql`/`redis`/`rabbitmq`/`minio`/`elasticsearch`）
- 本地开发用 `localhost`，Docker 用服务名，环境变量自动适配

## 公网部署 (Nginx + Cloudflare Tunnel)

生产环境通过 Nginx 反向代理 + Cloudflare Tunnel 对外提供 HTTPS：

```
Cloudflare Edge (SSL 终止) → cloudflared (Windows 服务) → Nginx :88 → Core :8088
```

| 组件 | 位置 | 说明 |
|------|------|------|
| cloudflared | Windows 服务 | 出站 WebSocket 隧道，无需开放入站端口 |
| Nginx | 容器 `allahpan-nginx:88` | 前端 SPA + `/api/` 反代 |
| 公网地址 | https://allahpan.cn | Cloudflare 自动 SSL/DDoS 防护 |

容器化部署后，外部 Nginx（`C:\nginx-1.26.3`）不再需要，所有流量走容器内 nginx。

## 架构要点

### 端口分配
- `88` — 生产 Nginx 反代（前端 SPA + `/api/` → `:8088`）
- `8088` — 主后端 API（allahpan-core）
- `8081` — 搜索服务 API（allahpan-search）
- `5173` — 前端开发服务器（Vite，仅 dev 模式）
- `9000/9001` — MinIO API / 控制台

### 文件处理流水线 (RabbitMQ)

```
UPLOADED → 缩略图生成 → THUMBNAILED → 文本提取(含Ollama OCR) → TEXT_EXTRACTED → ES索引 → COMPLETED
```

死信队列 + 指数退避重试 (30s/60s/120s)。

### 认证模型
邮箱验证码登录 → JWT 令牌（Hutool JWT，7 天过期）→ Spring Security 过滤器链

### 存储模型
MinIO 对象存储（容器 `minio:9000`），3 个 bucket：`allahpan-files`（文件）、`allahpan-thumbnails`（缩略图）、`allahpan-trash`（回收站）。storageKey 基于文件路径+文件名拼接（如 `folderA/vacation/photo.jpg`），MD5 去重实现秒传。

### 关键组件 (allahpan-core)
- `FileProcessSender` / `FileProcessReceiver` — RabbitMQ 流水线消息收发
- `ThumbnailGenerator` — 图片缩略图生成
- `TextExtractor` — PDF/DOCX/XLSX/PPTX/TXT 文本提取
- `OllamaService` — AI OCR（可选）
- `LocalStorageService` — 本地文件存储
- `EsIndexService` — Elasticsearch 索引同步
- `TrashCleanupTask` — 定时清理 30 天回收站

## 测试

- 测试仅在 `allahpan-core` 模块运行（其他模块 `<skipTests>true</skipTests>`）
- 测试框架: JUnit 5 + Mockito
- 测试文件位于 `allahpan-core/src/test/`

## 包命名约定

`com.allahpan.<layer>` — controller / service / service.impl / component / config / domain / task
