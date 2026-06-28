# 02 — 认证流程架构图

## 验证码登录完整链路

```mermaid
sequenceDiagram
    actor 用户
    participant AuthController as AuthController<br/>/api/auth
    participant AuthCodeService as AuthCodeServiceImpl
    participant MailService as MailService<br/>(QQ邮箱 SMTP)
    participant Redis as Redis
    participant UserService as UserServiceImpl
    participant UserMapper as UserMapper
    participant MySQL as MySQL (users)
    participant JwtUtil as JwtTokenUtil
    participant UserCache as UserCacheService

    Note over 用户,UserCache: ═══ Step 1: 发送验证码 ═══
    用户->>AuthController: POST /api/auth/send-code {email}
    AuthController->>AuthCodeService: sendCode(email)

    AuthCodeService->>Redis: EXISTS allahpan:sendLimit:{email}
    alt 30秒内已发送
        Redis-->>AuthCodeService: key 存在 → 拒绝
        AuthCodeService-->>AuthController: TOO_MANY_REQUESTS
        AuthController-->>用户: 429 "请30s后再试"
    else 未超频
        AuthCodeService->>Redis: INCR allahpan:attempts:{email}
        alt 小时超过50次
            AuthCodeService-->>AuthController: TOO_MANY_REQUESTS
            AuthController-->>用户: 429 "超过每小时上限"
        else 正常
            AuthCodeService->>AuthCodeService: 生成6位随机码
            AuthCodeService->>Redis: SET allahpan:authCode:{email} = code (TTL 5min)
            AuthCodeService->>Redis: SET allahpan:sendLimit:{email} = 1 (TTL 30s)
            AuthCodeService->>MailService: send(email, code)
            MailService-->>AuthCodeService: QQ邮箱SMTP发送
            AuthCodeService-->>AuthController: success
            AuthController-->>用户: 200 "验证码已发送"
        end
    end

    Note over 用户,UserCache: ═══ Step 2: 验证码登录 ═══
    用户->>AuthController: POST /api/auth/login-by-code {email, code}
    AuthController->>AuthCodeService: verifyCode(email, code)

    AuthCodeService->>Redis: GET allahpan:authCode:{email}
    Redis-->>AuthCodeService: storedCode

    alt 验证码错误或过期
        AuthCodeService-->>AuthController: CODE_ERROR / CODE_EXPIRED
        AuthController-->>用户: 400
    else 验证通过
        AuthCodeService->>Redis: DEL allahpan:authCode:{email}
        AuthController->>UserService: loginByCode(email)

        UserService->>UserCache: getUser(email)
        alt 缓存命中
            UserCache-->>UserService: User
        else 缓存未命中
            UserService->>UserMapper: selectByExample(email=?)
            MySQL-->>UserMapper: User / null
        end

        alt 用户不存在
            UserService->>UserMapper: insert(新用户)
            MySQL-->>UserMapper: userId
        end

        UserService->>UserCache: setUser(user) (TTL 24h)
        UserService-->>AuthController: User

        AuthController->>JwtUtil: generateToken(userId, email, hasPassword)
        JwtUtil-->>AuthController: JWT token (HS512, 7天有效期)
        AuthController-->>用户: {token, tokenHead, userId, email, hasPassword, firstLogin}
    end
```

## JWT 请求认证流程（后续请求）

```mermaid
sequenceDiagram
    actor 客户端
    participant Filter as JwtAuthentication<br/>TokenFilter
    participant JwtUtil as JwtTokenUtil
    participant SecurityConfig as MallSecurityConfig<br/>(UserDetailsService)
    participant UserCache as UserCacheService
    participant UserMapper as UserMapper
    participant MySQL as MySQL
    participant SecurityCtx as SecurityContext

    客户端->>Filter: HTTP Request<br/>Authorization: Bearer <token>
    Filter->>Filter: 提取 token (去 "Bearer " 前缀)

    Filter->>JwtUtil: getSubjectFromToken(token)
    JwtUtil-->>Filter: email

    Filter->>Filter: 检查 SecurityContext 是否已认证

    alt 未认证
        Filter->>SecurityConfig: loadUserByUsername(email)
        SecurityConfig->>UserCache: getUser(email)

        alt 缓存命中
            UserCache-->>SecurityConfig: User
        else 缓存未命中
            SecurityConfig->>UserMapper: selectByExample(email=?, status=1)
            MySQL-->>UserMapper: User
            SecurityConfig->>UserCache: setUser(user)
        end

        SecurityConfig-->>Filter: AdminUserDetails (userId, email, authorities=[])
        Filter->>JwtUtil: validateToken(token, email)
        JwtUtil-->>Filter: true

        Filter->>SecurityCtx: setAuthentication(UsernamePasswordAuthenticationToken)
    end

    Filter->>Filter: chain.doFilter()
    Note over Filter,MySQL: 请求进入 Controller → Service → Mapper 链路
```

## 三层验证码保护

```mermaid
graph TD
    subgraph "Redis Key 结构"
        A["allahpan:authCode:{email}<br/>值: 6位验证码<br/>TTL: 5分钟"]
        B["allahpan:sendLimit:{email}<br/>值: 1<br/>TTL: 30秒<br/><b>第1层: 发送间隔</b>"]
        C["allahpan:attempts:{email}<br/>值: 计数器<br/>TTL: 1小时<br/><b>第3层: 每小时上限50次</b>"]
    end

    Send["sendCode(email)"] --> B
    B -->|"key 不存在"| C
    B -->|"key 存在"| Reject1["拒绝: 30s内已发送"]
    C -->|"count ≤ 50"| Gen["生成6位码 → 存A"]
    C -->|"count > 50"| Reject2["拒绝: 超每小时上限"]

    Verify["verifyCode(email, code)"] --> A
    A -->|"匹配"| OK["删除key A → 放行"]
    A -->|"不匹配/过期"| Fail["CODE_ERROR / CODE_EXPIRED"]
```

## 关键文件索引

| 步骤 | 文件 | 方法 |
|------|------|------|
| 发送验证码 | `AuthController.java` | `sendCode()` |
| 生成/存储验证码 | `AuthCodeServiceImpl.java` | `sendCode()` |
| 邮件发送 | `MailService.java` | `send()` (QQ邮箱SMTP) |
| 验证码校验 | `AuthCodeServiceImpl.java` | `verifyCode()` |
| 验证码登录 | `UserServiceImpl.java` | `loginByCode()` |
| 密码登录 | `UserServiceImpl.java` | `loginByPassword()` |
| JWT 生成 | `AuthController.java` | `buildLoginResponse()` |
| JWT 工具 | `JwtTokenUtil.java` | `generateToken()` / `validateToken()` |
| 请求过滤器 | `JwtAuthenticationTokenFilter.java` | `doFilterInternal()` |
| 用户加载 | `MallSecurityConfig.java` | `loadUserByUsername()` |
| 用户详情 | `AdminUserDetails.java` | `getUserId()` / `getUsername()` |
| 缓存读取 | `UserCacheServiceImpl.java` | `getUser()` |
| 缓存写入 | `UserCacheServiceImpl.java` | `setUser()` |
| 缓存删除 | `UserCacheServiceImpl.java` | `delUser()` |
| 布隆过滤器 | `BloomFilterInitializer.java` | 启动时加载所有邮箱到 Redis bitmap |
| 布隆预检 | `UserCacheServiceImpl.java` | `getUser()` 先调 `bloomFilterService.mightContain(email)` |

## 布隆过滤器预检

`UserCacheServiceImpl.getUser()` 在查 Redis/MySQL 之前，先调用 `bloomFilterService.mightContain(email)`：

- **返回 false**：该邮箱绝对不存在，直接返回 null，跳过 Redis + MySQL 查询
- **返回 true**：该邮箱可能存在，继续正常的 Redis → MySQL 查询流程

`BloomFilterInitializer` (`ApplicationRunner`) 在应用启动时重建布隆过滤器，加载所有已有用户邮箱。

## 随机 TTL 防雪崩

`UserCacheServiceImpl` 在写入用户缓存时添加 0-300s 的随机抖动 (`ThreadLocalRandom`)：

```
实际 TTL = 86400 (24h) + random(0, 300)
```

这避免了大量用户缓存在同一时刻过期导致的缓存雪崩。

## 密码登录流程

`POST /api/auth/login-by-password` 支持已设密码的用户直接登录：

1. 根据 email 查询用户（缓存 → DB）
2. `BCryptPasswordEncoder.matches(rawPassword, storedHash)` 验证密码
3. 成功 → 生成 JWT Token 返回
4. 失败 → `CommonResult.failed("密码错误")`

密码首次设置通过 `POST /api/user/set-password`，设置后 `first_login` 标记从 1 变为 0。`hasPassword` 字段反映在 JWT claims 中。
