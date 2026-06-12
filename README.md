# AllahPan — 家庭共享云盘

Spring Boot 3.5 + Java 17 + MyBatis + Redis + RabbitMQ + Elasticsearch + Ollama + MinIO + Vue 3

## 项目结构

```
allahpan/
├── allahpan-common/      工具层（API 响应、异常处理、Redis、AOP）
├── allahpan-security/    安全层（JWT + Spring Security）
├── allahpan-mbg/         数据层（MyBatis Generator 实体/Mapper）
├── allahpan-core/        主应用 :8088（文件管理、用户认证、流水线）
├── allahpan-search/      搜索应用 :8081（Elasticsearch 全文检索）
├── allahpan-web/         前端 Vue 3（独立项目）
├── docs/                 架构 & API 文档
├── docker-compose.yml    基础设施编排
├── init.sql              数据库建表 DDL
└── README.md
```

**模块依赖**: `common → security → mbg → core(:8088)`，`search(:8081)` 仅依赖 common

## 环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| JDK | 17+ | 编译和运行后端 |
| Maven | 3.6+ | 项目构建 |
| Docker | 20.10+ | 运行基础设施容器 |
| Node.js | 18+ | 前端开发 |
| npm | 9+ | 前端包管理 |
| Ollama | (可选) | AI OCR 文字识别 |

## 快速启动

### 1. 克隆并初始化

```bash
git clone <repo-url>
cd allahpan
```

### 2. 启动基础设施

```bash
docker compose up -d
```

启动后会自动创建 `allahpan` 数据库并执行 `init.sql` 建表。

| 服务 | 端口 | 账号/密码 |
|------|------|-----------|
| MySQL 8.0 | `3307` | `root / 123456` |
| Redis 7.0 | `6379` | 无密码 |
| RabbitMQ 3.12 | `5672` (管理界面 `15672`) | `guest / guest` |
| Elasticsearch 8.11 | `9200` | 无安全认证（内置 IK 分词器） |
| MinIO | `9000` (Console `9001`) | `minioadmin / minioadmin` |

### 3. 构建后端

```bash
# 按依赖顺序构建（必须）
mvn clean install -pl allahpan-common,allahpan-mbg,allahpan-security,allahpan-core,allahpan-search -DskipTests
```

### 4. 启动后端服务

需要打开两个终端：

```bash
# 终端 1：主应用（端口 8088）
mvn spring-boot:run -pl allahpan-core

# 终端 2：搜索服务（端口 8081）
mvn spring-boot:run -pl allahpan-search
```

### 5. 启动前端

```bash
cd allahpan-web
npm install        # 首次运行需要
npm run dev        # 默认 http://localhost:5173
```

### 6. (可选) 启动 Ollama OCR

```bash
ollama pull qwen3.5:2b
ollama serve
```

Ollama 仅用于 IMAGE 类型文件的 OCR 文字提取。不启动时图片无 OCR 文字，但不影响其他功能。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_SECRET` | (内置 dev secret) | JWT 签名密钥，生产环境必须修改 |
| `MAIL_PASSWORD` | (内置 QQ 邮箱授权码) | SMTP 验证码发送密码 |

**Windows 设置示例（PowerShell）**:
```powershell
$env:JWT_SECRET = "your-256-bit-secret"
```

## 使用指南

### 登录

1. 打开 http://localhost:5173
2. 输入邮箱地址 → 点击「获取验证码」（验证码发送到 QQ 邮箱）
3. 输入 6 位验证码 → 点击「登录」
4. 首次登录建议设置密码，后续可用密码登录

### 上传文件

- 点击上传按钮或拖拽文件到页面
- 支持所有文件类型（图片、视频、文档、压缩包等）
- MD5 秒传：相同文件自动跳过上传
- 上传后自动进入处理流水线：缩略图 → 文字提取 → ES 索引

### 文件预览

- **图片/视频**：直接在线预览
- **文档（PDF/DOCX/DOC/XLSX/XLS/PPTX/PPT/TXT）**：提取的文字直接在预览窗口展示
- 图片类文件还支持 AI OCR 文字识别（需 Ollama）
- 处理状态实时显示（排队中 → 已缩略 → 识别中 → 可用）

### 全文搜索

- 按文件名和文件内容（提取的文字）搜索
- 支持中文分词（IK Analysis）
- 搜索结果高亮显示匹配内容

### 文件管理

- 文件夹树形结构，支持嵌套
- 右键菜单：重命名、移动、删除
- 垃圾站：30 天保留，支持恢复
- 每天凌晨 3 点自动清理过期垃圾

## 存储架构

文件存储在 MinIO 对象存储，3 个 bucket：

```
MinIO (:9000)
├── allahpan-files/          # 原文件
├── allahpan-thumbnails/     # 缩略图
└── allahpan-trash/          # 垃圾站（软删除文件）
```

文件通过 `MinioUtil` 组件读写，存储 key 格式为 `{userId}/{yyyy/MM}/{UUID}{ext}`。`SseBroadcaster` 负责实时推送文件变更事件到前端。

## 处理流水线

文件上传后经过 RabbitMQ 3 阶段串行处理：

```
UPLOADED (0) → THUMBNAILED (1) → TEXT_EXTRACTED (2) → COMPLETED (3)
```

| 阶段 | 处理内容 | 失败处理 |
|------|----------|----------|
| 缩略图 | IMAGE 缩放 300px / PDF 渲染首帧 | 重试 3 次（30s/60s/120s） |
| 文字提取 | PDF/DOCX/DOC/XLSX/XLS/PPTX/PPT/TXT 文本提取；IMAGE OCR | 同上 |
| ES 索引 | 写入 Elasticsearch 全文索引 | 降级，不标记失败 |

基础设施错误（ES/Ollama 不可达）重试耗尽后自动降级，不影响文件使用。

## API 文档

详见 `docs/api/` 目录：

- [认证 API](docs/api/01-auth.md) — 发送验证码、登录
- [用户 API](docs/api/02-user.md) — 设置密码、获取个人信息
- [文件 API](docs/api/03-file.md) — 上传、下载、预览、搜索、重命名、移动、删除
- [收藏 API](docs/api/04-favorite.md) — 收藏/取消/列表
- [搜索 API](docs/api/05-search-core.md) — 全文搜索
- [分享 API](docs/api/07-share.md) — 创建/访问/删除分享

## 架构文档

详见 `docs/architecture/` 目录：

| 文档 | 内容 |
|------|------|
| [01-模块依赖](docs/architecture/01-module-dependency.md) | Maven 模块结构与依赖关系 |
| [02-认证流程](docs/architecture/02-authentication-flow.md) | JWT 认证与 Security 配置 |
| [03-上传流程](docs/architecture/03-file-upload-flow.md) | multipart 上传与秒传 |
| [04-文件操作](docs/architecture/04-file-operations.md) | 软删除、恢复、重命名、移动 |
| [07-数据模型](docs/architecture/07-data-model.md) | ER 图与表结构 |
| [08-流水线](docs/architecture/08-rabbitmq-pipeline.md) | RabbitMQ 处理流水线 |
| [09-搜索模块](docs/architecture/09-search-module.md) | ES 搜索架构 |
| [11-存储架构](docs/architecture/11-minio-storage-architecture.md) | MinIO 对象存储 |

## 常用命令

```bash
# 重新构建全部模块
mvn clean install -pl allahpan-common,allahpan-mbg,allahpan-security,allahpan-core,allahpan-search -DskipTests

# 只构建 core（改动后快速验证编译）
mvn compile -pl allahpan-core -DskipTests

# 运行测试
mvn test -pl allahpan-core

# 停止基础设施（保留数据）
docker compose down

# 停止并清除数据
docker compose down -v

# 查看 RabbitMQ 管理界面
# 浏览器打开 http://localhost:15672  (guest/guest)
```

## 技术栈

**后端**: Spring Boot 3.5 · Spring Security · MyBatis · PageHelper · Druid · RabbitMQ · Redis · PDFBox · Apache POI · Elasticsearch · Ollama · Hutool JWT · Lombok · Swagger

**前端**: Vue 3 · Vite · Element Plus · Pinia · Axios · Vue Router

**基础设施**: MySQL 8.0 · Redis 7.0 · RabbitMQ 3.12 · Elasticsearch 8.11 (IK) · MinIO
