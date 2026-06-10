# 006 — 手机验证码 → 邮箱验证码完整迁移

**日期:** 2026-06-08
**范围:** 全栈 6 层 22 个文件

---

## 背景

原系统使用 `users.phone` 作为登录凭证，`SmsService` 是占位实现（控制台打印）。家庭云盘不需要真实短信——用一个 QQ 邮箱 SMTP 发送验证码即可，零成本、零审核、零第三方依赖。

**核心思路:** `spring-boot-starter-mail` + QQ 邮箱 SMTP（587 端口 STARTTLS），管理员配一次授权码，家庭成员用自己已有邮箱注册/登录。

---

## 影响范围

| 层 | 文件数 | 改动 |
|----|--------|------|
| DB | 1 | `init.sql` — `phone` → `email` 列 |
| MBG | 3 | `User.java` / `UserExample.java` / `UserMapper.xml` |
| Security | 2 | `JwtTokenUtil.java` / `JwtAuthenticationTokenFilter.java` |
| Core | 10 | Service / Controller / Config / BO / 新建 MailService + 删除 SmsService |
| Frontend | 3 | `Login.vue` / `api/auth.js` / `stores/user.js` |
| Config | 2 | `pom.xml` 加 mail starter + `application-dev.yml` 加 mail 配置 |
| Docs | 2 | `01-auth.md` / `02-authentication-flow.md` |

---

## 逐步实施

### Step 1: 数据库

```sql
-- init.sql CREATE TABLE 部分
email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱（登录凭证）',

-- 已有数据库的迁移语句
ALTER TABLE users CHANGE phone email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱（登录凭证）';
```

### Step 2: MBG 层

`User.java`:
- 字段 `private String phone` → `private String email`
- 注释 `手机号` → `邮箱（登录凭证）`
- `getPhone()` / `setPhone()` → `getEmail()` / `setEmail()`

`UserExample.java`:
- 18 个 `andPhone*` 方法 → `andEmail*`（`replace_all: andPhone → andEmail`）
- 方法内字符串 `"phone"` → `"email"`（`replace_all: "phone → "email`）

`UserMapper.xml`:
- SQL 列名 `phone` → `email`、`#{phone}` → `#{email}`、`row.phone` → `row.email`
- 使用 `replace_all: phone → email`

### Step 3: Security 层

`JwtTokenUtil.java`:
```java
// 旧
public String generateToken(Long userId, String phone, boolean hasPassword)
public boolean validateToken(String token, String phone)
String phone = (String) jwt.getPayload().getClaim("sub");
return generateToken(userId, phone, hasPassword);

// 新
public String generateToken(Long userId, String email, boolean hasPassword)
public boolean validateToken(String token, String email)
String email = (String) jwt.getPayload().getClaim("sub");
return generateToken(userId, email, hasPassword);
```

`JwtAuthenticationTokenFilter.java`:
- 局部变量 `String phone` → `String email`

### Step 4: Core 层

**新建 `MailService.java`** — 替换 `SmsService.java`:

```java
@Component
public class MailService {
    @Value("${mail.host}")     private String host;      // smtp.qq.com
    @Value("${mail.port}")     private int port;          // 587
    @Value("${mail.username}") private String username;   // QQ邮箱
    @Value("${mail.password}") private String password;   // 授权码
    @Value("${mail.from}")     private String from;       // 发件人

    public void send(String toEmail, String code) {
        // JavaMail: SMTP auth + STARTTLS + 纯文本邮件
        Properties props = new Properties();
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.starttls.enable", "true");
        // ... 发送逻辑
    }
}
```

**删除 `SmsService.java`** — 内容替换为注释说明

**`LoginRequest.java`:**
```java
@NotBlank(message = "邮箱不能为空")
private String email;
getEmail() / setEmail()
```

**`AuthCodeServiceImpl.java`:**
```java
// 注入 MailService
@Autowired
private MailService mailService;

// sendCode() 末尾
mailService.send(email, code);   // 替换 System.out.println

// 所有方法参数名 phone → email
```

**其余 core 文件:** 参数/变量名 `phone` → `email`，`getPhone()` → `getEmail()`，`andPhoneEqualTo` → `andEmailEqualTo`

**`UserServiceImpl.loginByCode()` 昵称生成:**
```java
// 旧: "用户" + phone.substring(phone.length() - 4)  → "用户3800"
// 新: email.substring(0, email.indexOf('@'))          → "family"
user.setNickname(email.substring(0, email.indexOf('@')));
```

**`AuthController.buildLoginResponse()` 返回字段:**
```java
// 响应 JSON 中 "phone" → "email"
Map.of("token", token, "userId", userId, "email", email, "hasPassword", hasPassword, ...)
```

### Step 5: 配置

**`allahpan-core/pom.xml`:** 新增 `spring-boot-starter-mail` 依赖

**`application-dev.yml`:**
```yaml
mail:
  host: smtp.qq.com
  port: 587
  username: 1455716631@qq.com
  password: ${MAIL_PASSWORD:xlryydmymdeljiff}
  from: AllahPan <1455716631@qq.com>
```

### Step 6: 前端

**`Login.vue`:**
- 图标: `Iphone` → `Message`
- 输入 placeholder: `请输入手机号` → `请输入邮箱地址`
- 验证提示: `请填写手机号` → `请填写邮箱地址`
- 变量: `codeForm.phone` → `codeForm.email`

**`api/auth.js`:** 参数名 `phone` → `email`

**`stores/user.js`:** 无需修改（API 返回的字段名自动变为 `email`）

---

## QQ 邮箱授权码获取步骤

1. 登录 QQ 邮箱网页版 → 设置 → 账户
2. 找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务」
3. 开启「SMTP 服务」→ 发送短信验证 → 生成 16 位授权码
4. 将授权码填入 `application-dev.yml` 的 `mail.password`

**注意:** 授权码只用于发件方（AllahPan 系统本身），家庭成员接收邮件不需要任何配置。

---

## 架构对比

```
旧（手机验证码）：
  AuthCodeService → SecureRandom → System.out.println → 开发者看控制台

新（邮箱验证码）：
  AuthCodeService → SecureRandom → MailService.send() → QQ邮箱SMTP → 用户收件箱
```

三层保护不变：5min 过期 / 30s 间隔 / 50 次/小时。底层 Redis key 结构不变，只是 key 值从手机号变为邮箱地址。

---

## 已知取舍

| 项目 | 原因 |
|------|------|
| 用户名从手机号改为邮箱 | 免费、免审核、家庭自用无需短信 |
| 587 端口（STARTTLS）而非 465 | QQ 邮箱推荐，更安全 |
| Redis key 仍用 `authCode` 前缀 | 只改 key 值，不改 structure |
| `SmsService.java` 未物理删除 | 保留为注释文件，后续清理时可删 |
