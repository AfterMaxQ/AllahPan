# 014 — 搜索服务宕机时伪装为 401 "token 过期"

**日期:** 2026-06-09

## 症状

用户在搜索框中输入 "统计建模"（或任何关键词），同时看到两条提示：

1. `"暂未登录或 token 过期"` — 拦截器弹出，同时被重定向到登录页
2. `"搜索服务暂不可用，请稍后重试"` — Search.vue catch 块弹出

用户 token 是有效的（刚登录，7 天过期），其他页面（文件列表、用户信息）均正常访问。

## 根因

**两个独立 bug 叠加，一条误导性错误链：**

### 完整请求链路

```
浏览器 GET /api/search?keyword=统计建模
  Authorization: Bearer <valid_token>

  → Vite proxy → localhost:8088

  [第 1 次 dispatch：原始请求]
  → Spring Security: JWT 过滤器验证通过 ✓ → SecurityContext 设置
  → SearchController.search() 执行
  → RestTemplate.getForObject("http://localhost:8081/es-admin/files/search?...")
      → 搜索服务 (:8081) 未运行 → ResourceAccessException (连接拒绝)

  → 异常未被捕获，传播出 Controller
  → Spring Boot 触发 ERROR dispatch → forward 到 /error

  [第 2 次 dispatch：错误处理]
  → 过滤器链重新执行
  → JwtAuthenticationTokenFilter: OncePerRequestFilter 默认跳过 error dispatch
      → SecurityContext 无认证
  → AuthorizationFilter: /error 不在白名单 → 要求认证
  → RestAuthenticationEntryPoint → HTTP 200 + {"code":401,"message":"暂未登录或token过期"}
  → ❌ 真实的 500 错误被 401 覆盖！

  → 前端 axios 拦截器: res.code === 401
      → userStore.logout() → 清除 localStorage
      → router.push('/login') → 重定向到登录页
      → ElMessage.warning("暂未登录或 token 过期")
      → Promise.reject(new Error("暂未登录或 token 已过期"))

  → Search.vue catch 块:
      → e.message = "暂未登录或 token 已过期"
      → e.message !== '未授权' → TRUE（次生 bug）
      → ElMessage.error("搜索服务暂不可用，请稍后重试")
```

### 核心问题：Error Dispatch 身份验证失败

Spring Boot 的默认错误处理使用服务器内部 forward 到 `/error` 路径。这个 error dispatch：

1. **不携带原始请求的 Authorization header**
2. **被 `JwtAuthenticationTokenFilter`（`OncePerRequestFilter`）跳过** — 默认 `shouldNotFilterErrorDispatch() == true`
3. **`/error` 路径需要认证** — 不在 `secure.ignored.urls` 白名单中

结果：搜索服务宕机引发的异常永远无法被用户看到，被 Spring Security 的 401 响应覆盖。

### 次生问题：Search.vue 认证错误检测失效

`Search.vue` 的 catch 块原本想过滤掉认证错误（因为拦截器已经处理了），但检测条件错误：

```js
// ❌ 错误的检测方式
if (e.message !== '未授权') {  // 永远不匹配实际消息
  ElMessage.error('搜索服务暂不可用，请稍后重试')
}
```

拦截器 reject 时使用的是 `res.message`（服务端返回的实际消息），即 `"暂未登录或 token 已过期"`。固定字符串 `"未授权"` 只在 `res.message` 为 undefined/falsy 时才作为 fallback，所以几乎永远不匹配。

## 为什么其他端点正常

`/api/user/me`、`/api/file/list` 等端点不调用搜索服务，不会触发异常 → 不会进入 error dispatch → 一切正常。

## 修复

### 修复 1：`/error` 加入安全白名单

**文件:** `allahpan-core/src/main/resources/application-dev.yml`

```yaml
secure:
  ignored:
    urls:
      - /api/auth/send-code
      - /api/auth/login-by-code
      - /api/auth/login-by-password
      - /swagger-ui/**
      - /v3/api-docs/**
      - /doc.html
      - /webjars/**
      - /api/share/**
      - /error           # ← 新增：允许 error dispatch 无需认证
```

**作用：** Error dispatch 到达 `/error` 时不再被 `AuthorizationFilter` 拦截，Spring Boot 的 `BasicErrorController` 能正常返回错误的 JSON 响应。

### 修复 2：SearchController 捕获搜索服务调用异常

**文件:** `allahpan-core/src/main/java/com/allahpan/controller/SearchController.java`

```java
try {
    Map<String, Object> result = rt.getForObject(builder.toUriString(), Map.class);
    return CommonResult.success(result);
} catch (RestClientException e) {
    LOG.warn("搜索服务不可用: {}", e.getMessage());
    return CommonResult.failed("搜索服务暂不可用，请稍后重试");
}
```

**作用：** 搜索服务不可用时返回明确的错误消息，而不是让异常传播到 error dispatch。双保险——即使修复 1 未生效，也能防止 401 伪装。

### 修复 3：Search.vue 认证错误检测

**文件:** `allahpan-web/src/views/Search.vue`

```js
} catch (e) {
  console.error('搜索失败', e)
  const msg = e.message || ''
  if (msg !== '未授权' && !msg.includes('未登录') && !msg.includes('token')) {
    ElMessage.error('搜索服务暂不可用，请稍后重试')
  }
}
```

**作用：** 不再用单一固定字符串 `"未授权"` 检测认证错误，改用关键词匹配（`未登录`/`token`），覆盖拦截器可能返回的各种认证错误消息。

## 根因总结表

| 层 | 发生了什么 | 应该发生什么 |
|----|-----------|------------|
| 搜索服务 (:8081) | 未运行 | 正常运行 |
| SearchController | 抛 `ResourceAccessException` | 返回搜索结果或错误 |
| Error dispatch (/error) | 无 Authorization header，被 401 拦截 | 返回真正的错误（500 或自定义消息） |
| 前端拦截器 | 看到 401 → 登出 + 重定向 | 看到搜索服务错误 → 仅提示 |
| Search.vue catch | 未能识别认证错误 → 重复提示 | 识别并跳过认证错误 |

## 这个 bug 为什么难排查

1. **错误消息误导：** 真正的错误是"搜索服务连接拒绝"，但用户只看到"token 过期"
2. **不一致性：** 其他端点正常（因为它们不调用搜索服务），容易让人怀疑 token 本身或某个特定关键词
3. **双消息混淆：** 同时出现两条似乎矛盾的提示（"token 过期" vs "搜索服务不可用"）
4. **error dispatch 发生在服务器内部：** 不经过网络，日志中难以追踪

## 关联文档

- [012 — Ollama OCR 管线](./012-ollama-ocr-pipeline-complete.md) — 类似的跨服务调用问题
- [013 — 搜索页同时出现 token 过期和未找到相关内容](./013-search-auth-error-and-empty-results.md) — 前一次搜索 bug 修复（401 处理缺失）
- [06 — 文件上传与处理流水线](../architecture/06-file-upload-pipeline.md) — 文件处理管线架构
- [08 — 搜索系统架构](../architecture/08-search-architecture.md) — 搜索架构概览
