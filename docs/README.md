# AllahPan 文档中心

## 架构文档 (`architecture/`)

系统架构说明，含 Mermaid 图表。

- [00 — 项目总览](architecture/00-project-overview.md)
- [01 — 模块依赖全景图](architecture/01-module-dependency.md)
- [02 — 认证流程架构图](architecture/02-authentication-flow.md)
- [03 — 文件上传流程架构图](architecture/03-file-upload-flow.md)
- [04 — 文件管理操作架构图](architecture/04-file-operations.md)
- [05 — 缓存与 AOP 架构图](architecture/05-cache-architecture.md)
- [06 — 文件上传与处理流水线](architecture/06-file-upload-pipeline.md)
- [07 — 请求处理全链路图](architecture/07-request-pipeline.md)
- [08 — 搜索系统架构](architecture/08-search-architecture.md)
- [09 — 数据模型 ER 图](architecture/09-data-model.md)
- [10 — 收藏模块](architecture/10-favorites-module.md)
- [11 — MinIO 存储架构](architecture/11-minio-storage-architecture.md)

## API 文档 (`api/`)

面向前端开发和服务对接的完整 API 文档，含 curl 示例和 JSON 响应。

- [README — 总览、认证、错误码](api/README.md)
- [01 — 认证 API](api/01-auth.md)（3 端点）
- [02 — 用户 API](api/02-user.md)（2 端点）
- [03 — 文件 API](api/03-file.md)（16 端点）
- [04 — 收藏 API](api/04-favorite.md)（4 端点）
- [05 — 搜索 API（core 代理）](api/05-search-core.md)（2 端点）
- [06 — 搜索服务 API（:8081）](api/06-search-service.md)（5 端点）
- [07 — 分享 API](api/07-share.md)（3 端点）

## 故障排查 (`trouble_shooting/`)

开发过程中遇到的问题和解决方案。

- [001 — MBG Generator 表名冲突](trouble_shooting/001-mbg-generator-table-conflict.md)
- [002 — 应用启动基础设施配置](trouble_shooting/002-application-startup-infrastructure.md)
- [003 — JWT 过滤器认证失败](trouble_shooting/003-jwt-filter-authentication-failure.md)
- [004 — Phase 3 文件模块编译错误修复](trouble_shooting/004-phase3-file-module-compilation.md)
- [005 — 后端审计与安全修复（12 项）](trouble_shooting/005-backend-audit-fixes.md)
- [006 — 手机验证码 → 邮箱验证码 全栈迁移](trouble_shooting/006-phone-to-email-migration.md)
- [007 — 邮箱验证码联调排错记录](trouble_shooting/007-email-verification-debug.md)
- [008 — 端到端功能测试发现的 Bug 修复](trouble_shooting/008-e2e-test-fixes.md)
- [009 — 文件上传卡在排队中或失败](trouble_shooting/009-file-upload-stuck-queuing-failed.md)
- [010 — OllamaService HTTP 超时与提示词优化](trouble_shooting/010-ollama-timeout-and-prompt.md)
- [011 — MinIO docker-compose 持久化配置](trouble_shooting/011-minio-docker-compose-persistence.md)
- [012 — Ollama OCR 管线完整排查与修复](trouble_shooting/012-ollama-ocr-pipeline-complete.md)
- [013 — 搜索页"暂未登录或token过期"和"未找到相关内容"](trouble_shooting/013-search-auth-error-and-empty-results.md)
- [014 — 本地目录为空（死代码误导）](trouble_shooting/014-local-dir-empty-dead-code.md)
- [015 — 本地文件系统主存储架构迁移](trouble_shooting/015-local-storage-architecture-migration.md)
- [016 — ES 搜索返回已删除文件](trouble_shooting/016-es-search-returns-deleted-files.md)
- [017 — Ollama 管线停止, Redis/RabbitMQ 配置排查](trouble_shooting/017-ollama-pipeline-stopped-redis-rabbitmq.md)

> 注: trouble_shooting 目录存在两对重复编号（014 和 015），分别对应两个不同的问题，已知暂未重新编号。

## 设计规范 (`superpowers/specs/`)

- [前端设计语言](superpowers/specs/2026-06-08-allahpan-frontend-design.md) — 暖白木色系，温馨简洁
- [Gemini 前端实现提示词](superpowers/specs/2026-06-08-allahpan-frontend-gemini-prompt.md) — 发给 Gemini 的完整上下文

## Q&A (`qa/`)

项目开发与技术问答，深入解释技术决策和架构设计。

- [001 — 什么是无状态 JWT，在我的项目里有什么用](qa/001-stateless-jwt.md)
- [002 — 为什么 WebLogAspect 只给 Controller 切面打日志](qa/002-weblog-aspect-scope.md)
