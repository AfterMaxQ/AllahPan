# 013 - 搜索页同时出现"暂未登录或token过期"和"未找到相关内容"

**日期:** 2026-06-09

## 症状

用户在 `/search?q=hi` 搜索时同时看到两个问题：

1. 弹出错误提示 "暂未登录或token过期"
2. 搜索结果显示 "未找到相关内容" / "换个关键词试试，或文件可能尚未被 AI 识别"

## 根因

**一个根因 + 两个设计缺陷导致双症状：**

### 请求全链路

```
浏览器 GET /api/search?keyword=hi
  → Spring Security JwtAuthenticationTokenFilter 验证 token → ❌ 失败
  → RestAuthenticationEntryPoint 返回 HTTP 200 + JSON:
    {"code":401, "message":"暂未登录或token过期"}
  → 前端 axios 响应拦截器:
    - res.code !== undefined → 不跳过
    - res.code !== 200 → 不进成功分支
    - res.code === 401 → ❌ 无专门处理 → 落入通用错误分支
    - ElMessage.error("暂未登录或token过期")  ← 症状 1
    - Promise.reject()
  → Search.vue catch 块: console.error() 静默吞错
  → results 仍为 [] → v-else-if 渲染 EmptyState
  → "未找到相关内容"  ← 症状 2
```

### 关键设计不匹配

| 层 | 行为 |
|---|---|
| **后端** `RestAuthenticationEntryPoint` (line 29) | 返回 **HTTP 200** + 业务码 401 |
| **前端** 响应拦截器错误分支 (line 35) | 只处理 **HTTP status 401** 做登出重定向 |
| **前端** 响应拦截器成功分支 (line 22-32) | 业务码 401 没有 `res.code === 401` 的判断 → 落入通用 `ElMessage.error` → 不重定向 |

前端只在一个地方处理 401 重定向：HTTP status 401 的错误回调。但后端返回的是 HTTP 200 + 业务码 401，永远无法触发那个分支。用户看到错误弹窗但留在原地，陷入"报错但不跳转"的僵死状态。

## 修复

### 修复 1：前端响应拦截器 — 增加业务码 401 处理

**文件:** `allahpan-web/src/api/index.js`

在成功拦截器中，`res.code === 200` 检查之后、通用错误提示之前，新增业务码 401 的判断：

```js
// 业务码 401：未登录或 token 过期 → 登出并跳转登录页
// 后端 RestAuthenticationEntryPoint 返回 HTTP 200 + code=401，不走 HTTP 401 分支
if (res.code === 401) {
  const userStore = useUserStore()
  userStore.logout()
  router.push('/login')
  ElMessage.warning(res.message || '登录已过期，请重新登录')
  return Promise.reject(new Error(res.message || '未授权'))
}
```

### 修复 2：Search.vue — 增加用户可见的错误反馈

**文件:** `allahpan-web/src/views/Search.vue`

```js
} catch (e) {
  console.error('搜索失败', e)
  // 非认证错误（认证错误已由拦截器处理并跳转登录页）
  if (e.message !== '未授权') {
    ElMessage.error('搜索服务暂不可用，请稍后重试')
  }
}
```

## 为什么 token 会失效

Vue Router 守卫 (`router/index.js` line 42) 只检查 `!!userStore.token`（token 是否存在于 localStorage），不验证 token 是否有效。用户可能持有过期 token（JWT 7 天过期）仍能进入受保护页面，但 API 调用会被后端拒绝。

## 关联文档

- [003 - JWT 过滤器认证失败](003-jwt-filter-authentication-failure.md) — 相关的后端 JWT 验证 bug（已修复）
- [02-认证流程](../architecture/02-authentication-flow.md) — JWT 认证架构
