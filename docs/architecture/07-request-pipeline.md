# 07 — 请求处理全链路图

## HTTP 请求 → 响应 完整路径

```mermaid
flowchart TD
    HTTP["HTTP Request"] --> Filter["JwtAuthenticationTokenFilter<br/>OncePerRequestFilter"]
    Filter -->|"公开URL"| Skip["跳过认证"]
    Filter -->|"需认证"| JWT["解析 JWT → 查 DB/Cache<br/>→ 注入 SecurityContext"]
    Skip --> Security["Spring Security Filter Chain"]
    JWT --> Security
    Security --> Log["WebLogAspect<br/>@Around controller"]
    Log --> Controller["Controller"]
    Controller --> Service["Service"]
    Service --> Mapper["Mapper (MyBatis)"]
    Mapper --> DB[("MySQL")]
    DB --> Mapper
    Mapper --> Service
    Service --> Controller
    Controller --> Log
    Log --> Result["CommonResult<T> JSON"]
    Result --> Exception{"异常?"}
    Exception -->|"ApiException"| Handler["GlobalExceptionHandler<br/>handleApiException()"]
    Exception -->|"MethodArgumentNotValid"| Handler2["GlobalExceptionHandler<br/>handleValidException()"]
    Exception -->|"无异常"| Response["HTTP Response<br/>Content-Type: application/json"]
    Handler --> Response
    Handler2 --> Response
```

## Filter Chain 详细流程

```mermaid
sequenceDiagram
    actor Client as 客户端
    participant Container as Servlet Container
    participant JwtFilter as JwtAuthentication<br/>TokenFilter
    participant JwtUtil as JwtTokenUtil
    participant UserDetailsSvc as UserDetailsService<br/>(MallSecurityConfig)
    participant SecurityCtx as SecurityContextHolder
    participant Dispatcher as DispatcherServlet
    participant Controller as Controller

    Client->>Container: HTTP Request
    Container->>JwtFilter: doFilterInternal()

    Note over JwtFilter: 1. 提取 Token
    JwtFilter->>JwtFilter: request.getHeader(tokenHeader)<br/>e.g. "Authorization: Bearer eyJ..."
    JwtFilter->>JwtFilter: 去 "Bearer " 前缀

    alt Token 存在
        Note over JwtFilter: 2. 解析 subject (email)
        JwtFilter->>JwtUtil: getSubjectFromToken(token)
        JwtUtil-->>JwtFilter: email

        Note over JwtFilter: 3. 检查是否已认证
        JwtFilter->>SecurityCtx: getContext().getAuthentication()
        alt 未认证
            Note over JwtFilter: 4. 加载用户详情
            JwtFilter->>UserDetailsSvc: loadUserByUsername(email)
            UserDetailsSvc-->>JwtFilter: AdminUserDetails

            Note over JwtFilter: 5. 验证 Token
            JwtFilter->>JwtUtil: validateToken(token, email)
            JwtUtil-->>JwtFilter: true

            Note over JwtFilter: 6. 注入 SecurityContext
            JwtFilter->>SecurityCtx: setAuthentication(<br/>  new UsernamePasswordAuthenticationToken(<br/>    userDetails, null, authorities)<br/>)
        end
    end

    JwtFilter->>Container: chain.doFilter()
    Container->>Dispatcher: 路由到 Controller

    Note over Dispatcher: WebLogAspect @Around
    Dispatcher->>Controller: 执行方法
    Controller-->>Dispatcher: CommonResult
    Dispatcher-->>Client: JSON Response
```

## 控制器一览

| 控制器 | 路径前缀 | 端点数 | 关键端点 |
|--------|---------|--------|---------|
| `AuthController` | `/api/auth` | 3 | `send-code`, `login-by-code`, `login-by-password` |
| `UserController` | `/api/user` | 2 | `set-password`, `/me` |
| `FileController` | `/api/file` | 16 | `upload`, `create-folder`, `list`, `tree/{id}`, `getFile`, `download`, `stream`, `thumbnail`, `watch`(SSE), `rename`, `move`, `batch`, `trash`, `restore`, `permanent-delete` |
| `SearchController` | `/api/search` | 2 | GET search（代理转发）, POST rebuild-index |
| `FavoriteController` | `/api/favorite` | 4 | `POST /{fileId}`, `DELETE /{fileId}`, `GET /check/{fileId}`, `GET /list` |
| `ShareController` | `/api/share` | 3 | POST create（需认证）, GET access（公开）, DELETE revoke（需认证） |
| `ChunkController` | `/api/file/chunk` | 4 | `init`, `upload`, `complete`, `status/{uploadId}` — 大文件分片上传 |

> **端点总数**: core 模块共有 ~34 个端点（含 chunk 4 个），search 模块 5 个，合计约 39 个。

## 安全配置

```mermaid
graph TD
    SC["SecurityConfig<br/>@EnableWebSecurity"]

    SC --> Bean1["IgnoredUrlsConfig<br/>@ConfigurationProperties(secure.ignored)"]
    SC --> Bean2["PasswordEncoder<br/>BCryptPasswordEncoder"]
    SC --> Bean3["SecurityFilterChain"]

    Bean3 --> Rule1["禁用 CSRF"]
    Bean3 --> Rule2["SessionCreationPolicy.STATELESS"]
    Bean3 --> Rule3["白名单 URL: permitAll()"]
    Bean3 --> Rule4["OPTIONS 请求: permitAll()"]
    Bean3 --> Rule5["其余请求: authenticated()"]
    Bean3 --> Rule6["401 处理: RestAuthenticationEntryPoint"]
    Bean3 --> Rule7["403 处理: RestfulAccessDeniedHandler"]
    Bean3 --> Rule8["JwtAuthenticationTokenFilter<br/>加在 UsernamePasswordAuthenticationFilter 之前"]

    Rule3 --> Whitelist["白名单 URL:<br/>/api/auth/send-code<br/>/api/auth/login-by-code<br/>/api/auth/login-by-password<br/>/api/share/**<br/>/api/file/*/thumbnail<br/>/api/file/*/stream<br/>/api/file/*/download<br/>/api/file/watch<br/>/swagger-ui/**<br/>/v3/api-docs/**<br/>/error"]
```

## 异常处理链路

```mermaid
flowchart TD
    Error["Service 抛出异常"] --> Type{"异常类型?"}

    Type -->|"ApiException"| GE1["GlobalExceptionHandler<br/>handleApiException()"]
    GE1 --> R1["CommonResult.failed(resultCode)"]

    Type -->|"MethodArgumentNotValidException"| GE2["GlobalExceptionHandler<br/>handleValidException()"]
    GE2 --> R2["提取字段级错误<br/>→ CommonResult.validateFailed()"]

    Type -->|"BindException"| GE3["GlobalExceptionHandler<br/>handleBindException()"]
    GE3 --> R3["提取 binding errors<br/>→ CommonResult.validateFailed()"]

    Type -->|"其他 Exception"| Spring["Spring Boot 默认<br/>/error 处理"]
    Spring --> R4["Whitelabel Error Page<br/>或 JSON"]
```

## 响应格式

所有 Controller 返回统一包装为 `CommonResult<T>`:

```json
{
  "code": 200,
  "message": "操作成功",
  "data": { ... }
}
```

错误时：
```json
{
  "code": 401,
  "message": "暂未登录或token过期",
  "data": null
}
```

## WebLogAspect 日志格式

每个 Controller 方法自动输出：
```
URL: /api/file/list, Method: GET, IP: 127.0.0.1,
Class: com.allahpan.controller.FileController,
Method: listFiles, Args: [0],
Result: CommonResult(code=200, ...), Spend: 15ms
```

异常时：
```
URL: /api/file/999, Method: GET, IP: 127.0.0.1,
Class: com.allahpan.controller.FileController,
Method: getFile, Args: [999],
ErrorMessage: 文件不存在, Spend: 8ms
```

## 关键文件索引

| 阶段 | 文件 | 关键方法/配置 |
|------|------|--------------|
| JWT 过滤器 | `JwtAuthenticationTokenFilter.java` | `doFilterInternal()` |
| JWT 工具 | `JwtTokenUtil.java` | `generateToken()`, `validateToken()`, `getSubjectFromToken()` |
| 安全配置 | `SecurityConfig.java` | `filterChain()`, `ignoredUrlsConfig()` |
| 用户加载 | `MallSecurityConfig.java` | `userDetailsService()` |
| 401 处理 | `RestAuthenticationEntryPoint.java` | `commence()` |
| 403 处理 | `RestfulAccessDeniedHandler.java` | `handle()` |
| 日志切面 | `WebLogAspect.java` | `doAround()` |
| 异常处理 | `GlobalExceptionHandler.java` | `handleApiException()`, `handleValidException()` |
| 响应包装 | `CommonResult.java` | `success()`, `failed()`, `unauthorized()`, `forbidden()` |
| 结果码 | `ResultCode.java` | `SUCCESS`, `UNAUTHORIZED`, `FORBIDDEN`, `TOO_MANY_REQUESTS`, ... |
| 断言工具 | `Asserts.java` | `fail()`, `isTrue()` |
| 搜索代理 | `SearchController.java` | `search()` / `rebuildIndex()` — RestTemplate → `:8081` |
| 分享 | `ShareController.java` | `createShare()`, `getShare()`, `deleteShare()` |
| 分片上传 | `ChunkController.java` | `init()`, `uploadChunk()`, `complete()`, `status()` |
| 布隆过滤 | `BloomFilterService.java` | `mightContain(email)` — Redis bitmap 预检 |
| 布隆初始化 | `BloomFilterInitializer.java` | `ApplicationRunner` — 启动时加载用户邮箱 |
| 收藏 | `FavoriteController.java` | `addFavorite()`, `removeFavorite()`, `isFavorited()`, `listFavorites()` |
