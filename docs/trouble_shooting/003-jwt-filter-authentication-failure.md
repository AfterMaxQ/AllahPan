# 003 - JWT 过滤器认证失败：token 始终被判定为过期

**日期:** 2026-06-07

## 错误日志

```
[JWT Filter] authHeader=Bearer eyJ0eXAi...
[JWT Filter] phone=13800138000
[JWT Filter] userDetails=com.allahpan.bo.AdminUserDetails@69364bfc
[JWT Filter] token INVALID
```

所有需要 JWT 认证的接口统一返回：
```json
{"code":401,"message":"暂未登录或token过期","data":"暂未登录或 token 已过期"}
```

## 原因

两个 Bug 叠加导致 JWT 过滤器始终无法认证通过：

### Bug 1：SecurityConfig 创建了未注入依赖的 Filter 实例

`SecurityConfig` 中通过 `@Bean` 方法创建 `JwtAuthenticationTokenFilter`：

```java
@Bean
public JwtAuthenticationTokenFilter jwtAuthenticationTokenFilter() {
    return new JwtAuthenticationTokenFilter();  // 这里 new 出来的实例，@Autowired 字段为 null
}
```

虽然 `JwtAuthenticationTokenFilter` 类上也有 `@Component`，但 Spring 容器在遇到同名同类型的 `@Bean` 定义时，`@Bean` 优先。`@Bean` 方法直接 `new` 出来的实例，其 `@Autowired` 字段（`userDetailsService`、`jwtTokenUtil`）和 `@Value` 字段（`tokenHeader`、`tokenHead`）都是 null，导致过滤器静默跳过认证逻辑。

**修复**：删除 `jwtAuthenticationTokenFilter()` 这个 `@Bean` 方法，在 `filterChain(HttpSecurity http, JwtAuthenticationTokenFilter jwtFilter)` 中直接注入 `@Component` 扫描出来的实例（依赖已自动注入）。

### Bug 2：JwtTokenUtil.isTokenExpired() 类型转换错误

`isTokenExpired()` 方法将 JWT 的 `exp` 字段强制转换为 `Date`：

```java
Date exp = (Date) JWTUtil.parseToken(token).getPayload().getClaim("exp");
```

Hutool JWT 5.8.x 在解析 token 时，`exp` 字段（标准 JWT 规范中是 Unix 时间戳整数）会被解析为 `Long` 类型，而不是 `Date`。强制转换 `(Date) expObj` 抛出 `ClassCastException`，被 `catch (Exception e) { return true; }` 捕获，导致**所有 token 都被判定为过期**。

**修复**：改为类型检测，兼容 `Date` 和 `Number` 两种类型：

```java
Object expObj = ...getClaim("exp");
Date exp;
if (expObj instanceof Date) {
    exp = (Date) expObj;
} else if (expObj instanceof Number) {
    exp = new Date(((Number) expObj).longValue() * 1000);
}
```

## 影响范围

- `allahpan-security/src/main/java/.../config/SecurityConfig.java`
- `allahpan-security/src/main/java/.../util/JwtTokenUtil.java`

两个文件都需要更新。
