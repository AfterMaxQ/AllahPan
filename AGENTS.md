# AGENTS.md

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
├── docs/                 架构 & API 文档
├── docker-compose.yml    基础设施编排
└── init.sql              数据库 DDL
```

**依赖链**: `common ← security ← mbg ← core(:8088)`，`search(:8081)` 仅依赖 `common`

- **可运行入口**: `allahpan-core` (`AllahPanApplication`, 8088) 和 `allahpan-search` (`SearchApplication`, 8081)
- **库模块**: `allahpan-common`, `allahpan-mbg`, `allahpan-security`（不可单独运行）

## 构建与运行

```bash
# 1. 启动基础设施
docker-compose up -d

# 2. 构建全部模块（core 模块运行测试，其他跳过）
mvn clean package -DskipTests

# 3. 启动主应用 (8088)
cd allahpan-core
mvn spring-boot:run

# 4. 启动搜索服务 (8081)
cd allahpan-search
mvn spring-boot:run

# 5. 启动前端 (5173)
cd allahpan-web
npm install
npm run dev
```

## 基础设施 (docker-compose)

| 服务 | 端口 | 备注 |
|------|------|------|
| MySQL 8.0 | 3307 | 数据库 `allahpan`，密码 `123456` |
| Redis 7.0 | 6379 | 无密码 |
| RabbitMQ 3.12 | 5672 / 15672 | 管理界面，guest/guest |
| Elasticsearch 8.11 | 9200 | 单节点，安全已禁用 |

## 架构要点

### 端口分配
- `8088` — 主后端 API（allahpan-core）
- `8081` — 搜索服务 API（allahpan-search，绑定 127.0.0.1）
- `5173` — 前端开发服务器（Vite，API 代理到 8088）

### 文件处理流水线 (RabbitMQ)

```
UPLOADED → 缩略图生成 → THUMBNAILED → 文本提取(含Ollama OCR) → TEXT_EXTRACTED → ES索引 → COMPLETED
```

死信队列 + 指数退避重试 (30s/60s/120s)。

### 认证模型
邮箱验证码登录 → JWT 令牌（Hutool JWT，7 天过期）→ Spring Security 过滤器链

### 存储模型
本地磁盘 `ALLAHPAN_ROOT`（默认 `C:/Users/ray/AllahPan`），每用户独立目录。`FileSystemWatcher` 双向同步文件系统变更。MD5 去重实现秒传。

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
