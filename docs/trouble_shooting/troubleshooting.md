# AllahPan 故障排查指南

## 目录

- [快速诊断](#快速诊断)
- [基础设施](#基础设施)
- [认证](#认证)
- [文件上传](#文件上传)
- [文件操作](#文件操作)
- [处理管线](#处理管线)
- [搜索](#搜索)
- [分享与收藏](#分享与收藏)
- [SSE 实时推送](#sse-实时推送)
- [性能与稳定性](#性能与稳定性)

---

## 快速诊断

### 一分钟健康检查

```bash
# 基础设施
docker ps --format "table {{.Names}}\t{{.Status}}" | grep allahpan

# 核心服务
curl -s -X POST http://localhost:8088/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"email":"health@check.com"}' | jq .

# 搜索服务
curl -s "http://localhost:8081/es-admin/files/search?keyword=health&pageNum=1&pageSize=1" | jq .
```

### 如何读日志

| 日志关键字 | 含义 | 紧急程度 |
|-----------|------|----------|
| `FileSystemWatcher 启动失败` | WatchService 未启动，文件系统事件丢失 | 🔴 高 |
| `文件处理彻底失败` | process_status=-1，文件处理永久失败 | 🔴 高 |
| `ES 启动清理超时` | 搜索服务 5 分钟未就绪，搜索不可用 | 🟠 中 |
| `全量同步失败` | 文件系统与 DB 不一致 | 🟠 中 |
| `搜索服务不可用` | ES 连接失败，用户搜索降级 | 🟡 低 |
| `非关键组件不可用` | 缩略图/OCR/ES 降级，文件仍可用 | 🟡 低 |
| `SSE 状态推送失败` | 前端不实时更新，刷新页面即可 | 🟢 信息 |

---

## 基础设施

### MySQL 连接失败

**症状：** 启动报 `CommunicationsException` 或 `Unable to connect to localhost:3307`

```bash
# 检查容器状态
docker ps -a --filter "name=allahpan-mysql"

# 检查端口
netstat -ano | findstr 3307

# 测试连接
docker exec allahpan-mysql mysql -uroot -p123456 -e "SELECT 1" allahpan
```

**解决：**
```bash
# 容器未启动
docker compose up -d mysql

# 端口冲突（其他 MySQL 占用 3307）
netstat -ano | findstr 3307
# 找到 PID 后停止冲突进程，或修改 docker-compose.yml 端口映射

# 数据库不存在
docker exec allahpan-mysql mysql -uroot -p123456 -e "CREATE DATABASE IF NOT EXISTS allahpan DEFAULT CHARACTER SET utf8mb4"
```

### Redis 连接失败

**症状：** 验证码发送失败、登录状态丢失、分享链接不可用

```bash
docker exec allahpan-redis redis-cli ping
# 期望: PONG
```

**解决：**
```bash
# Redis 未启动
docker compose up -d redis

# Windows Redis 端口冲突（常见：本地已有 Redis 在 6379）
netstat -ano | findstr 6379
# 如果 PID 不是 docker 进程，停止冲突的 Redis 或修改 application-dev.yml 中 spring.data.redis.host
```

### RabbitMQ 连接失败

**症状：** 文件上传后 process_status 始终为 0（PENDING），日志报 `connection refused`

```bash
# 检查状态
curl -s -u guest:guest http://localhost:15672/api/aliveness-test/%2F

# 检查队列堆积
curl -s -u guest:guest http://localhost:15672/api/queues/%2F/allahpan.file.process | jq '.messages_ready'
```

**解决：**
```bash
docker compose up -d rabbitmq

# 队列堆积 > 100 → 消费者可能挂了，重启 core 服务
# 管理界面: http://localhost:15672 (guest/guest)
```

### Elasticsearch 不可用

**症状：** 搜索返回 "搜索服务暂不可用"，ES 日志持续报错

```bash
# 集群健康
curl -s http://localhost:9200/_cluster/health | jq .

# 索引状态
curl -s http://localhost:9200/_cat/indices/allahpan_files?v
```

**解决：**
```bash
docker compose up -d elasticsearch

# 状态 red → 检查磁盘空间
docker exec allahpan-elasticsearch df -h

# IK 分词器缺失 → 搜索不工作但不报错
docker exec allahpan-elasticsearch bin/elasticsearch-plugin list | grep ik
# 如果没有，需重新构建 ES 镜像安装 IK 插件
```

### MinIO 不可用

**症状：** 项目已迁移到纯本地存储，MinIO 不再使用。不影响当前功能。

**注意：** 如 `docker compose up -d` 报告 minio 容器为 orphaned——这是正常的。

---

## 认证

### 验证码收不到

**排查步骤：**

```bash
# 1. 检查 Redis 中验证码是否生成
docker exec allahpan-redis redis-cli GET "allahpan:authCode:用户邮箱"

# 2. 检查邮件发送日志（应用日志搜索 "验证码" 或 "MailService"）

# 3. 检查 QQ SMTP 配置
# application-dev.yml 中 mail.* 配置是否完整
# MAIL_PASSWORD 环境变量是否设置（QQ 邮箱需授权码，非登录密码）
```

**常见原因：**
- `MAIL_PASSWORD` 环境变量未设置或过期
- QQ 邮箱 SMTP 每日发送上限（通常 500 封）
- 邮件被归入垃圾箱

### "30 秒后才能再次发送"

**原因：** 这是正常的限流机制，不是 bug。`allahpan:sendLimit:{email}` 在 Redis 中有 30 秒 TTL。

```bash
# 手动清除限流（仅供调试）
docker exec allahpan-redis redis-cli DEL "allahpan:sendLimit:用户邮箱"
```

### "操作太频繁"（小时限制 50 次）

```bash
# 查看当前计数
docker exec allahpan-redis redis-cli GET "allahpan:attempts:用户邮箱"

# 重置计数（仅供调试）
docker exec allahpan-redis redis-cli DEL "allahpan:attempts:用户邮箱"
```

### Token 过期 / 401

**症状：** 所有请求返回 `{"code":401,"message":"暂未登录或token过期"}`

- JWT 有效期 7 天（`jwt.expiration: 604800`）
- Token 格式：`Authorization: Bearer <token>`（注意 `Bearer ` 后有空格）
- 前端 Axios 拦截器自动添加 token，上传文件须用原生 `fetch()`（避免 Axios 污染 Authorization 头）

### 密码登录失败

**症状：** 验证码登录正常但密码登录报 "密码错误"

```bash
# 检查用户密码是否已设置
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT email, first_login, password IS NOT NULL AS has_pwd FROM users WHERE email='用户邮箱'" allahpan
```

- `first_login=1` → 用户从未设置密码，只能用验证码登录
- `password IS NULL` → 同上
- 引导用户通过 `/api/user/set-password` 设置密码

---

## 文件上传

### 上传后文件不显示

**排查步骤：**

```bash
# 1. 检查是否真的写入了 DB
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, file_name, process_status, delete_time FROM files WHERE uploader_id=用户ID ORDER BY create_time DESC LIMIT 10" allahpan

# 2. 检查本地磁盘
ls "C:\Users\ray\AllahPan"  # 或 $env:ALLAHPAN_ROOT

# 3. 检查前端 parentId 参数
# GET /api/file/list?parentId=0 → 根目录
# GET /api/file/list?parentId=123 → 指定文件夹
```

### process_status 始终为 0（PENDING）

**原因：** RabbitMQ 管线未处理该文件。

**排查：**
1. **RabbitMQ 是否在线？** `curl -s -u guest:guest http://localhost:15672/api/aliveness-test/%2F`
2. **消费者是否活跃？** 检查 core 服务日志中的 `@RabbitListener`
3. **消息是否在队列中？** 查看 RabbitMQ 管理界面 Queues 标签页
4. **是否有异常导致静默失败？** 搜索日志中的 `fileId=你的文件ID`

**手动触发：** 重启 core 服务或在上传代码中确认 `fileProcessSender.sendProcess(...)` 被调用。

### MD5 秒传不生效

**条件：** 两个文件字节级完全一致才会触发。以下情况不触发：
- 文件名不同但内容相同 → **触发**（存储复用）
- 内容相同但上传到不同 parentId → **触发**
- 内容仅差 1 字节 → 不触发

**验证：**
```bash
# 检查文件 MD5
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, file_name, md5, storage_key FROM files WHERE md5='目标MD5值'" allahpan
```

### 文件名冲突处理

上传同名文件到同一目录时，系统自动追加序号：
```
test.txt → test (1).txt → test (2).txt → ...
```

如果无限循环 → 磁盘可能有同名但大小写不同的文件（Windows 不区分大小写），手动清理磁盘文件。

---

## 文件操作

### 删除失败（同名文件约束冲突）

**症状：** `DELETE /api/file/{id}` 返回 500，日志包含 `DuplicateKeyException: uk_parent_name_delete`

**原因：** 同一文件夹下有两个同名文件（如 `test.txt` 和 `test.txt` 分别上传后改名导致），软删除时 `delete_time` 时间戳相同，违反唯一约束 `uk_parent_name_delete(parent_id, file_name, delete_time)`。

**解决：**
1. 手动重命名其中一个文件后再删除
2. 已修复的版本会给 `delete_time` 加毫秒偏移

```bash
# 查找同名文件
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, file_name, parent_id, delete_time FROM files WHERE parent_id=父目录ID AND file_name='文件名' AND delete_time IS NULL" allahpan
```

### 移动文件报 "同名文件或文件夹已存在"

目标位置已有同名文件。先重命名或删除目标位置的文件。

### 移动文件报 "不能移动到子文件夹"

试图将文件夹移到自己的子文件夹中。选择其他目标目录。

### 文件夹重命名后子文件路径不对

**已知 Bug：** 文件夹重命名后 `storageKey` 未更新，子文件的物理路径仍指向旧名称。临时解决：
- 小规模：手动移动本地文件到新路径
- 等待修复：`FileServiceImpl.renameFile()` 需更新文件夹自身的 `storageKey`

### 回收站恢复报 "父文件夹在垃圾站中"

**原因：** 父文件夹也被删除了，需先恢复父文件夹再恢复子文件。

```bash
# 查找父文件夹
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, file_name, parent_id, delete_time FROM files WHERE id=文件的parent_id" allahpan

# 先恢复父文件夹
curl -X PUT "http://localhost:8088/api/file/trash/父文件夹ID/restore" \
  -H "Authorization: Bearer $TOKEN"

# 再恢复子文件
curl -X PUT "http://localhost:8088/api/file/trash/子文件ID/restore" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 处理管线

### 管线状态说明

| process_status | 含义 | 说明 |
|----------------|------|------|
| 0 | PENDING | 已上传，等待处理 |
| 1 | THUMBNAILED | 缩略图已生成 |
| 2 | TEXT_EXTRACTED | 文字已提取(OCR/文档解析) |
| 3 | COMPLETED | 已索引到 ES，处理完成 |
| -1 | FAILED | 处理失败（仅数据库错误会到这个状态） |

### 管线卡在某个状态

```bash
# 查看各阶段文件数量
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT process_status, COUNT(*) FROM files WHERE is_folder=0 AND delete_time IS NULL GROUP BY process_status" allahpan
```

**按状态排查：**

**卡在 0 (PENDING)：**
- RabbitMQ 连接是否正常？
- `FileProcessSender.sendProcess()` 是否在 upload 后被调用？
- 检查 core 服务日志中是否有 `sendProcess` 相关日志

**卡在 1 (THUMBNAILED)：**
- 缩略图生成是否失败？（限 IMAGE 类型）
- 检查日志中的 `生成缩略图失败` 或 `生成PDF缩略图失败`
- 非 IMAGE/DOCUMENT 类型跳过缩略图直接到 TEXT_EXTRACTED → 状态快速变为 2

**卡在 2 (TEXT_EXTRACTED)：**
- Ollama 是否在线？`curl http://localhost:11434/api/tags`
- 对于 DOCUMENT 类型，检查 MIME 类型是否在 `TextExtractor.extract()` 的处理范围内
- 未知 DOCUMENT 子类型会返回 null（日志: `未知的 DOCUMENT 子类型，无法提取文本`）

**状态为 -1 (FAILED)：**
- 仅数据库写入失败会标记 -1
- 检查日志中 `文件处理彻底失败` 的完整堆栈
- 基础设施错误（连接/超时/Ollama/ES）不会标记 -1，会自动降级

### 管线重试机制

每个阶段最多重试 3 次，间隔递增：
```
第 1 次失败 → 30 秒后重试
第 2 次失败 → 60 秒后重试
第 3 次失败 → 120 秒后重试
第 4 次失败 → 基础设施错误降级 / 数据库错误标记 -1
```

### Ollama OCR 不工作

```bash
# 1. 检查 Ollama 服务
curl http://localhost:11434/api/tags

# 2. 检查模型是否存在
curl http://localhost:11434/api/tags | jq '.models[].name'
# 期望包含: "qwen3.5:2b"

# 3. 模型未安装
ollama pull qwen3.5:2b

# 4. 测试 OCR 是否能正常调用
curl http://localhost:11434/api/chat -d '{
  "model": "qwen3.5:2b",
  "stream": false,
  "messages": [{"role": "user", "content": "Hello"}]
}'
```

**注意：** Ollama 超时在 `application-dev.yml` 中配置（`ollama.timeout: 60` 秒）。大图片 OCR 可能超时，增大此值或使用更快的模型。

### 缩略图不显示

```bash
# 检查文件是否为 IMAGE 或 PDF 类型
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, file_name, file_type, thumbnail_key, process_status FROM files WHERE id=文件ID" allahpan

# thumbnail_key 为 NULL → 缩略图未生成或生成失败
# 检查 .thumbnails/ 目录
ls "C:\Users\ray\AllahPan\.thumbnails"
```

**常见原因：**
- 非 IMAGE/PDF 类型不生成缩略图
- 图片格式不兼容（如 WebP、AVIF）
- PDF 渲染失败（加密 PDF 或损坏文件）

---

## 搜索

### 搜索不到文件内容（只能匹配文件名）

**🔴 高度怀疑 BUG #1：ES 重建丢失了全文索引。**

这是最常见的原因——`rebuildAll()` 或定时对账（每 30 分钟）已经清空了所有 `originText`。

**诊断：**
```bash
# 检查 ES 中的文件是否有 originText
curl -s "http://localhost:9200/allahpan_files/_doc/文件ID" | jq '._source.originText'

# 如果返回 "" 或 null → BUG #1 已触发
# 对比数据库
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT LEFT(origin_text, 200) FROM files WHERE id=文件ID" allahpan
```

**缓解方案（修复前）：**
1. 重新上传文件，管线会正确索引（单文件索引用的是正确的 `selectByPrimaryKey`）
2. 不要手动调用 `/api/search/rebuild-index`
3. 临时禁用定时对账（修改 `application-dev.yml` 或注释 `@Scheduled`）

**永久修复：** `EsIndexServiceImpl.java:130` 改为 `selectByExampleWithBLOBs`

### 搜索返回 "搜索服务暂不可用"

**原因：** core 服务无法连接 search 服务（localhost:8081）。

```bash
# 检查 search 服务
curl -s "http://localhost:8081/es-admin/files/search?keyword=test&pageNum=1&pageSize=1"

# 未启动则启动
mvn spring-boot:run -pl allahpan-search
```

### 搜索结果不相关或为空

1. 确认文件已完成处理（`process_status=3`）——只有完成处理的文件才会被索引
2. IK 分词器未安装 → 中文搜索无结果（不报错）
3. 搜索词与文件内容不匹配（ES 使用 `multi_match` 在 `fileName^10` 和 `originText^5` 上搜索）

---

## 分享与收藏

### 分享链接失效

**排查：**
```bash
# 检查 Redis 中是否存在
docker exec allahpan-redis redis-cli EXISTS "allahpan:share:分享码"
docker exec allahpan-redis redis-cli TTL "allahpan:share:分享码"
```

- `EXISTS=0` → 已过期或被删除。分享码有效期 = `expireHours` + 1 小时缓冲
- `TTL < 0` → key 无过期时间（异常）
- 分享的文件被删除后，分享链接返回 "文件不存在或已删除"

### 收藏的文件消失

收藏列表只显示**未被删除**的文件。如果文件被删除（包括软删除），收藏列表不再包含该文件。

---

## SSE 实时推送

### 前端收不到实时更新

**排查步骤：**

```bash
# 1. 测试 SSE 端点
curl -N "http://localhost:8088/api/file/watch?token=你的JWT"

# 正常应首先收到:
# event:connected
# data:ok
```

**常见原因：**
- **Token 在 URL 中传递**：SSE 使用 EventSource API，不支持自定义请求头，token 必须通过 `?token=` 查询参数传递
- **Token 过期**：SSE 连接最长 30 分钟，token 需在连接期间有效
- **代理/负载均衡器缓冲**：Nginx 等代理需关闭 SSE 响应的缓冲（`proxy_buffering off`）
- **前端 EventSource 不支持自定义事件名**：需手动解析 `event:` 行

### SSE 事件类型

| 事件名 | 触发时机 | data 内容 |
|--------|----------|-----------|
| `connected` | 客户端订阅成功 | `"ok"` |
| `file-created` | 新文件/文件夹被检测到 | `{fileId, parentId}` |
| `file-deleted` | 文件/文件夹被删除 | `{fileId, parentId}` |
| `file-updated` | 处理状态变更 | `{fileId, parentId, processStatus, thumbnailKey, originText}` |
| `sync-complete` | 全量同步完成 | `{}` |

---

## 性能与稳定性

### 内存使用过高

```bash
# 检查 Java 进程
Get-Process java | Select-Object Id, @{N='WS(MB)';E={[math]::Round($_.WorkingSet64/1MB,1)}}, @{N='PM(MB)';E={[math]::Round($_.PrivateMemorySize64/1MB,1)}}
```

**预期范围：** 500MB-2GB。如果超过 2GB：

1. **FileSystemWatcher 处理大文件**：`calculateMd5()` 用 `Files.readAllBytes()` 读整个文件到内存（已知问题）
2. **大量文件同时上传**：每个上传流占用内存
3. **ES 索引重建**：`rebuildAll()` 全量加载所有文件元数据

**缓解：** 重启 core 服务。长期修复：大文件 MD5 计算改用流式。

### 深层目录操作慢或报错

**症状：** 100+ 层目录的删除/重命名很慢，或抛出 StackOverflowError

**原因：** `deleteChildren`、`rebuildDescendantPaths` 使用递归，深度 > 1000 会栈溢出。

**缓解：** 限制目录深度或改用迭代实现。

### 上传大文件失败

- 单文件上限：512MB（`spring.servlet.multipart.max-file-size`）
- 请求上限：1GB（`spring.servlet.multipart.max-request-size`）
- 客户端超时：大文件上传需要足够长的超时时间
- 磁盘空间：检查 `C:\Users\ray\AllahPan` 所在分区剩余空间

```bash
# Windows 检查磁盘空间
Get-PSDrive C | Select-Object Used, Free
```

### 数据库连接池耗尽

**症状：** 日志出现 `CannotGetJdbcConnectionException` 或 `Too many connections`

```bash
# 检查 MySQL 连接数
docker exec allahpan-mysql mysql -uroot -p123456 -e "SHOW PROCESSLIST" allahpan

# 检查 Druid 连接池（应用日志搜索 "Druid" 或 "activeCount"）
```

**解决：**
- 增加 `spring.datasource.druid.max-active`（默认值通常够用）
- 检查是否有未关闭的数据库连接（长事务）
- 重启 core 服务

---

## 调试技巧

### 快速查看文件状态

```bash
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, file_name, file_type, is_folder, process_status, delete_time IS NOT NULL AS deleted FROM files WHERE id=文件ID" allahpan
```

### 快速查看用户状态

```bash
docker exec allahpan-mysql mysql -uroot -p123456 -e \
  "SELECT id, email, status, first_login, last_login_time FROM users WHERE email='用户邮箱'" allahpan
```

### 查看 Redis 中所有 AllahPan Key

```bash
docker exec allahpan-redis redis-cli KEYS "allahpan:*"
```

### 清空测试数据

```bash
# 清空所有文件（保留用户）
docker exec allahpan-mysql mysql -uroot -p123456 -e "DELETE FROM file_favorites; DELETE FROM files; DELETE FROM users WHERE email LIKE '%test%'" allahpan

# 清空 Redis 所有 AllahPan 缓存
docker exec allahpan-redis redis-cli KEYS "allahpan:*" | xargs docker exec allahpan-redis redis-cli DEL

# 清空本地文件（保留目录结构）
Remove-Item "C:\Users\ray\AllahPan\*" -Recurse -Force
Remove-Item "C:\Users\ray\AllahPan\.thumbnails\*" -Recurse -Force
Remove-Item "C:\Users\ray\AllahPan\.trash\*" -Recurse -Force

# 清空 ES 索引（下次启动自动重建）
curl -X DELETE "http://localhost:9200/allahpan_files"
```

### 重置 ES 索引

```bash
# 方法 1: 通过 API
curl -X POST "http://localhost:8088/api/search/rebuild-index" -H "Authorization: Bearer $TOKEN"

# 方法 2: 直接操作 ES（更彻底）
curl -X DELETE "http://localhost:9200/allahpan_files"
# 然后重启 core 服务 → 启动时自动重建索引
```

---

## 常见错误码速查

| HTTP Code | ResultCode | 含义 | 常见原因 |
|-----------|-----------|------|----------|
| 200 | 200 | 成功 | — |
| 200 | 401 | 未登录 | Token 缺失/过期/无效 |
| 200 | 403 | 无权限 | 越权访问他人资源 |
| 200 | 404 | 验证失败 | 参数校验不通过 |
| 200 | 429 | 限流-发送 | 30 秒内重复发送验证码 |
| 200 | 429 | 限流-尝试 | 验证码错误次数超限(50次/小时) |
| 200 | 400 | 验证码错误 | 输入的验证码不匹配 |
| 200 | 400 | 验证码过期 | 验证码已过期(5分钟) |
| 200 | 500 | 操作失败 | 服务端异常(查看日志) |
| 500 | — | Internal Server Error | 未捕获异常(已知问题, 待加 GlobalExceptionHandler) |
