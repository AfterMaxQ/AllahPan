# 005 — 后端审计与安全修复（12 项）

**日期:** 2026-06-08
**范围:** JWT 认证 / 文件操作 / 消息队列 / 数据库 / 验证码

---

## 背景

对后端全部代码进行审计，发现 12 个需修复的问题（不含跳过的 C3 文件所有权校验——家庭项目无需权限架构）。

---

## C1: JWT 签名从未验证

**文件:** `allahpan-security/.../util/JwtTokenUtil.java`
**严重级别:** 🔴 Critical

**问题:** 所有 token 解析方法都用 hutool 的 `JWTUtil.parseToken()`（仅 Base64 解码），从未调用 `JWTUtil.verify(token, signer)` 验证 HMAC-SHA512 签名。攻击者可构造任意 JWT 冒充任何用户。

**修复:**

1. 新增私有辅助方法：
```java
private JWT parseVerifiedToken(String token) {
    if (!JWTUtil.verify(token, JWTSignerUtil.hs512(secret.getBytes()))) {
        return null;
    }
    return JWTUtil.parseToken(token);
}
```

2. 替换全部 6 处 `JWTUtil.parseToken(token)` 调用：
   - `isTokenExpired()` — 签名无效返回 `true`（视为过期）
   - `getSubjectFromToken()` — 签名无效返回 `null`
   - `refreshToken()` — 一次解析提取全部 claims，避免多次验证
   - `getHasPasswordFromToken()` — 签名无效返回 `false`
   - `getUserIdFromToken()` — 签名无效返回 `null`
   - `validateToken()` — 直接使用已验证的 JWT 对象

3. Hutool `JWTUtil.verify()` 验证 HS512 签名后再 `parseToken()` 读取载荷，从源头杜绝伪造 token。

---

## C2: JWT 密钥弱密码

**文件:** `allahpan-core/.../application-dev.yml`
**严重级别:** 🔴 Critical

**问题:** `secret: allahpan-jwt-secret` —— 字典短语，可被 JWT 破解工具暴力破解。

**修复:**

```yaml
# 旧
secret: allahpan-jwt-secret
# 新
secret: ${JWT_SECRET:e7b2a3c94d1f5680fe912a7b4c3d8e5f6a1b7c2d3e4f5a6b7c8d9e0f1a2b3c4d5}
```

- Spring `${ENV_VAR:default}` 语法：开发环境用 64 字符随机 hex 默认值，生产环境通过 `JWT_SECRET` 环境变量覆盖
- 64 字符 hex = 256 bit，满足 HS512 强度要求

---

## C4: permanentDelete 无软删除前置校验

**文件:** `allahpan-core/.../service/impl/FileServiceImpl.java`
**严重级别:** 🔴 Critical

**问题:** `permanentDelete()` 只检查文件是否存在，不检查是否已进入垃圾站（`deleteTime != null`）。攻击者可以跳过软删除直接永久删除正常文件及其所有子节点。

**修复:**

```java
Asserts.isTrue(file != null, "文件不存在");
Asserts.isTrue(file.getDeleteTime() != null, "只能永久删除垃圾站中的文件");  // 新增
```

与已有的 `restoreFile()` 检查一致（`"文件不在垃圾站中"`），确保删除两阶段：软删除 → 永久删除。

---

## C5: 搜索服务零认证

**文件:** `allahpan-search/.../application.yml`
**严重级别:** 🔴 Critical

**问题:** `allahpan-search` 模块未依赖 `allahpan-security`，`:8081` 端口的所有 ES 管理端点完全无认证保护。

**修复:**

```yaml
server:
  port: 8081
  address: 127.0.0.1   # 新增：仅监听本地回环
```

- core 模块通过 `RestTemplate` 走 `localhost` 代理搜索请求，不受影响
- 外部网络无法直接访问 `:8081`，需通过 `:8088` 的认证网关

---

## C7: CommonPage.restPage() 从未填充 list 字段

**文件:** `allahpan-common/.../api/CommonPage.java`
**严重级别:** 🔴 Critical

**问题:** `restPage()` 设置了 `pageNum/pageSize/totalPage/total` 但遗漏了 `result.setList(...)`。所有使用 `CommonPage.restPage()` 的分页接口返回的 `data.list` 为 `null`。

**修复:**

```java
// PageHelper 分支
result.setList(page.getResult());  // 新增

// 非 PageHelper 分支（兜底）
result.setList(list);  // 新增
```

- `Page.getResult()` 返回当前页的实际数据行
- `else` 分支将普通列表当作单页结果，避免 NPE

---

## H1: 无重名防护

**文件:** `FileServiceImpl.java` + `init.sql`
**严重级别:** 🟠 High

**问题:** 数据库无唯一约束，代码也不检查同名。同一目录可出现两个同名文件/文件夹。

**修复（双保险）:**

**A. 应用层** — 新增 `assertNameUnique()` 方法：
```java
private void assertNameUnique(Long parentId, String fileName) {
    FileExample example = new FileExample();
    example.createCriteria()
            .andParentIdEqualTo(parentId)
            .andFileNameEqualTo(fileName)
            .andDeleteTimeIsNull();
    Asserts.isTrue(fileMapper.selectByExample(example).isEmpty(),
            "同名文件或文件夹已存在");
}
```

在 4 个入口调用：`confirmUpload()`、`createFolder()`、`renameFile()`、`moveFile()`。

`renameFile()` 做了优化：名称未变更时跳过重名检查。

**B. 数据库层** — 新增唯一索引：
```sql
CREATE UNIQUE INDEX uk_parent_name_delete ON files (parent_id, file_name, delete_time);
```

- MySQL InnoDB UNIQUE 将 NULL 视为不同值
- 活跃文件（`delete_time IS NULL`）强制唯一
- 已删除文件可重名（`delete_time` 不同，键值不冲突）

> H4（并发秒传竞态）由数据库唯一索引顺带解决：并发插入相同 `(parent_id, file_name, NULL)` 时，第二个请求触发 `DuplicateKeyException`。

---

## H3: 秒传不复制 thumbnailKey

**文件:** `FileServiceImpl.java` preUpload()
**严重级别:** 🟠 High

**问题:** 秒传创建新记录时复制了 `storageKey/fileSize/contentType/fileType/md5`，但遗漏了 `thumbnailKey`。新记录无缩略图，需等处理流水线重新生成。

**修复:**

```java
dup.setFileType(existing.getFileType());
dup.setThumbnailKey(existing.getThumbnailKey());  // 新增
dup.setIsFolder((byte) 0);
```

两个记录指向同一 `storageKey`，缩略图内容相同，复用 `thumbnailKey` 正确且高效。

---

## H6: RabbitMQ 管线状态不一致

**文件:** `allahpan-core/.../component/FileProcessReceiver.java`
**严重级别:** 🟠 High

**问题:** UPLOADED 和 THUMBNAILED 两个 case 先更新 DB 状态再发下一阶段消息。如果 `sender.sendProcess()` 失败抛异常，DB 已更新但消息未发出，文件卡在中间状态。

**修复（重排序）:**

```java
// UPLOADED case — 新顺序：
thumbnailGenerator.generate(file);
sender.sendProcess(...);               // ← 先发消息（失败则抛异常）
file.setProcessStatus((byte) 1);
fileMapper.updateByPrimaryKeySelective(file);  // ← 后更新 DB

// THUMBNAILED case — 同样调整
```

- 发送失败 → 异常 → 外层 catch 触发重试 → DB 未修改 → 从同一 stage 干净重来
- 发送成功 + DB 更新失败 → 重复消息到达下一 stage → 下一 stage 幂等（同文件重复缩略图/OCR/索引结果一致）

---

## H7b: 缩略图重试泄漏

**文件:** `FileProcessReceiver.java` UPLOADED case
**严重级别:** 🟠 High

**问题:** 重试时重新生成缩略图并上传 MinIO，上一次已上传的缩略图对象成为孤儿。

**修复:**

```java
if (file.getThumbnailKey() == null) {   // 新增：已有就跳过
    String thumbnailKey = thumbnailGenerator.generate(file);
    if (thumbnailKey != null) {
        file.setThumbnailKey(thumbnailKey);
    }
}
```

如果上一次尝试已生成缩略图并持久化到 DB（但后续 sendProcess 失败），重试时直接复用已有 `thumbnailKey`。

---

## H7c: MinIO 删除异常静默吞

**文件:** `allahpan-common/.../util/MinioUtil.java`
**严重级别:** 🟡 Medium

**问题:** `removeObject()` 的空 catch 块静默丢弃所有异常，MinIO 连接故障时运维无感知。

**修复:**

```java
// 新增 Logger
private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(MinioUtil.class);

// catch 块
} catch (Exception e) {
    log.warn("删除 MinIO 对象失败: {}", storageKey, e);
}
```

---

## H8: file_path VARCHAR(500) 溢出无校验

**文件:** `FileServiceImpl.java`
**严重级别:** 🟠 High

**问题:** `buildPath()` 无长度检查。深层嵌套 + 长文件夹名时可超过 500 字符，触发 `DataTruncation` SQL 错误但无用户友好提示。

**修复:**

**A.** `buildPath()` 末尾加检查：
```java
String result = path.toString();
Asserts.isTrue(result.length() <= MAX_PATH_LENGTH,
        "文件路径过长（最大500字符），请缩短文件夹或文件名");
return result;
```

**B.** `createFolder()` 和 `renameFile()` 名单段长度检查：
```java
Asserts.isTrue(newName.length() <= MAX_FILE_NAME_LENGTH,
        "文件名过长（最大255字符）");
```

---

## H9: 缺少数据库索引

**文件:** `init.sql`
**严重级别:** 🟠 High

**问题:** `files` 表只有主键索引，所有业务查询都是全表扫描。

**修复:**

```sql
CREATE INDEX idx_parent_delete ON files (parent_id, delete_time);
CREATE INDEX idx_md5_delete ON files (md5, delete_time);
CREATE INDEX idx_delete_time ON files (delete_time);
CREATE UNIQUE INDEX uk_parent_name_delete ON files (parent_id, file_name, delete_time);
```

| 索引 | 加速的查询 |
|------|-----------|
| `idx_parent_delete` | `listFiles()` 按父目录列出未删除文件 |
| `idx_md5_delete` | `preUpload()` MD5 秒传检测 |
| `idx_delete_time` | `listTrash()` 垃圾站列表 |
| `uk_parent_name_delete` | 重名检查 + 并发防护（H1+H4） |

---

## H10: java.util.Random 生成验证码

**文件:** `allahpan-core/.../service/impl/AuthCodeServiceImpl.java`
**严重级别:** 🟠 High

**问题:** `new Random().nextInt(1000000)` — `java.util.Random` 是线性同余生成器，非密码学安全，观测足够多验证码后可预测后续。

**修复:**

```java
// 旧
import java.util.Random;
String code = String.format("%06d", new Random().nextInt(1000000));

// 新
import java.security.SecureRandom;
String code = String.format("%06d", new SecureRandom().nextInt(1000000));
```

- `new SecureRandom()` 从 OS 熵池取种子，不阻塞（不同于 `SecureRandom.getInstanceStrong()`）
- 配合已有的三层验证码保护（5min 过期 / 30s 发送间隔 / 50 次/小时），双重防护

---

## 未修复的审计发现

| 问题 | 原因 |
|------|------|
| C3 文件所有权校验 | 家庭项目，无多用户隔离需求 |
| H5 密码哈希存在 Redis | 低风险，Redis 仅本地访问 |
| H9 之外的 N+1 查询 | 当前数据量不构成性能问题 |
| 搜索服务返回 `Map` 而非 `CommonResult` | 内部服务，不对外暴露 |
