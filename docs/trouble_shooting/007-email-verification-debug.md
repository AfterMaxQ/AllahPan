# 007 — 邮箱验证码联调排错记录

**日期:** 2026-06-08
**范围:** QQ SMTP 认证 / MySQL 公钥 / IPv6 / Redis 多实例

---

## 背景

将 AllahPan 登录系统从手机短信迁移至邮箱验证码后，进行端到端联调时遇到 4 个问题。

---

## 问题 1: QQ SMTP 认证失败（535 Login fail）

**现象:**
```java
jakarta.mail.AuthenticationFailedException: 535 Login fail. Account is abnormal...
```

**原因:** 配置文件中 QQ 邮箱地址拼写错误：`1455716631@qq.com` → 应为 `1455726631@qq.com`。

**修复:** 更正 `application-dev.yml` 中 `mail.username` 和 `mail.from` 的邮箱地址。

**教训:** SMTP 535 错误优先检查用户名/授权码拼写，而非网络或端口。

---

## 问题 2: MySQL Public Key Retrieval 被拒

**现象:**
```
java.sql.SQLNonTransientConnectionException: Public Key Retrieval is not allowed
```
发生在 `login-by-code` 调用时（需查询 `users` 表），但不影响 `send-code`（仅用 Redis）。

**原因:** MySQL 8.0 默认不允许客户端获取服务器公钥用于密码认证。Docker 中的 MySQL 8.0 容器与本地 MySQL 8.0 行为一致但 JDBC 驱动版本不同，需要显式声明。

**修复:** JDBC URL 增加参数：
```
allowPublicKeyRetrieval=true
```

**最终 URL:**
```yaml
url: jdbc:mysql://localhost:3307/allahpan?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai&characterEncoding=utf-8
```

---

## 问题 3: IPv6 导致 Security 白名单行为不一致

**现象:** `curl localhost` 有时返回 200（正常），有时返回 401 body（被 Security 拦截）。浏览器访问正常。

**原因:** `localhost` 在 Windows 上同时解析为 `::1`（IPv6）和 `127.0.0.1`（IPv4）。Spring Security 的 `requestMatchers` 的 ant 匹配机制在不同 IP 协议栈下行为不一致。IPv6 请求先尝试，失败后 fallback 到 IPv4，但部分请求在 IPv6 下被 `RestAuthenticationEntryPoint` 拦截。

**修复:** curl 测试时使用 `-4` 参数强制 IPv4：
```bash
curl -4 -X POST http://127.0.0.1:8088/api/auth/send-code ...
```

浏览器不会受此问题影响（浏览器使用操作系统解析的 IP），生产环境部署时 nginx 统一处理也无需担心。

---

## 问题 4: 本地 Redis 与 Docker Redis 双实例

**现象:** `docker exec redis-allahpan redis-cli KEYS "*"` 返回空，但后端显然在使用 Redis。

**原因:** 本地 Windows 已安装 Redis 并监听 127.0.0.1:6379（PID 6328），Docker 容器 Redis 监听 0.0.0.0:6379（PID 20784）。Java 后端连接 `localhost:6379` 时优先匹配到 127.0.0.1（本地 Redis），验证码存储在那个里。

**修复:** 通过 Docker Redis 的 `host.docker.internal` 访问宿主机 Redis：
```bash
docker exec redis-allahpan redis-cli -h host.docker.internal GET "allahpan:authCode:xxx@qq.com"
```

**长期方案:** 二选一——关闭本地 Redis，或修改 docker-compose 中 Redis 端口映射避免冲突。开发阶段用 `host.docker.internal` 桥接即可。

---

## 最终验证结果

```
✅ 前端输入邮箱 → 点击获取验证码
✅ 后端 AuthCodeService 生成 6 位码 → Redis 存储 → MailService 发送
✅ QQ 邮箱收到 HTML 暖木风格验证码邮件
✅ 前端输入验证码 → 点击登录 → JWT 签发
✅ 新用户自动注册（昵称取 @ 前部分）→ firstLogin=true → 跳转 /set-password
```

全栈 6 层 22 文件改动无遗漏，编译和运行均正常。
