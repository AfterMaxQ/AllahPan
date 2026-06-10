# 05 — 缓存与 AOP 架构图

## Redis 整体架构

```mermaid
graph TD
    subgraph "应用层"
        UserCache["UserCacheServiceImpl<br/>@Service"]
        AuthCode["AuthCodeServiceImpl<br/>@Service"]
    end

    subgraph "AOP 层 (allahpan-security)"
        Aspect["RedisCacheAspect<br/>@Aspect @Order(2)"]
        Annotation["@CacheException<br/>标记注解"]
    end

    subgraph "服务层 (allahpan-common)"
        RedisSvc["RedisService<br/>接口"]
        RedisImpl["RedisServiceImpl<br/>@Service"]
    end

    subgraph "配置层 (allahpan-common)"
        Config["BaseRedisConfig<br/>@Configuration"]
        Serializer["Jackson2JsonRedisSerializer<br/>ObjectMapper + DefaultTyping"]
        Template["RedisTemplate<br/><String, Object>"]
        CacheManager["RedisCacheManager<br/>TTL: 1天"]
    end

    subgraph "基础设施"
        Redis[(Redis<br/>:6379)]
    end

    UserCache --> Aspect
    AuthCode -.->|"不走切面(类名不匹配)"| RedisSvc
    Aspect -->|"拦截 *CacheService.*"| UserCache
    Aspect -->|"默认吞异常"| UserCache
    Annotation -.->|"标记后异常传播"| Aspect
    UserCache --> RedisSvc
    AuthCode --> RedisSvc
    RedisSvc --> RedisImpl
    RedisImpl --> Template
    Template --> Redis
    Config --> Serializer
    Config --> Template
    Config --> CacheManager
```

## RedisCacheAspect 切面逻辑

```mermaid
flowchart TD
    A["方法调用: *CacheService.*"] --> B{"切入点匹配?<br/>execution(public *<br/>com.allahpan.service.*CacheService.*(..))"}
    B -->|"是"| C["进入 @Around 通知"]
    C --> D["proceed() 执行目标方法"]
    D --> E{"抛出异常?"}
    E -->|"否"| F["返回结果"]
    E -->|"是"| G{"方法或类上<br/>有 @CacheException?"}
    G -->|"是"| H["重新抛出异常<br/>→ 调用方感知"]
    G -->|"否"| I["log.error(异常信息)"]
    I --> J["返回 null<br/>调用方无感知"]
```

**设计意图**: 缓存是加速层，缓存挂了不应影响业务。`*CacheService` 的方法默认 best-effort，加上 `@CacheException` 才传播异常。

## AuthCodeService 不走切面

`AuthCodeServiceImpl` 直接调用 `RedisService`，**不走** `RedisCacheAspect`：

- 类名是 `AuthCodeServiceImpl`，不匹配 `*CacheService` 切点
- 验证码是核心业务，Redis 挂了应该直接报错，不能静默吞异常

## Redis Key 命名空间

```
allahpan                         ← redis.database 配置值
├── allahpan:member:{email}      ← UserCacheService (TTL 24h)
├── allahpan:authCode:{email}    ← AuthCodeService (TTL 5min)
├── allahpan:sendLimit:{email}   ← 发送间隔 (TTL 30s)
└── allahpan:attempts:{email}    ← 小时上限 50 次 (TTL 1h)
```

```mermaid
graph LR
    subgraph "UserCacheService"
        UK["memberKey(email)"]
        UK -->|"拼接"| MK["allahpan:member:user@example.com"]
        MK -->|"TTL: 86400s"| RV["User 对象 (JSON)"]
    end

    subgraph "AuthCodeService"
        AK["authCodeKey(email)"]
        AK -->|"拼接"| AV["allahpan:authCode:user@example.com"]
        AV -->|"TTL: 300s"| CV["6位验证码"]
    end
```

## 序列化配置

```java
// BaseRedisConfig.java
Jackson2JsonRedisSerializer<Object> serializer = new Jackson2JsonRedisSerializer<>(Object.class);
ObjectMapper mapper = new ObjectMapper();
mapper.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
mapper.activateDefaultTyping(
    LaissezFaireSubTypeValidator.instance,
    DefaultTyping.NON_FINAL  // 存类型信息, 反序列化时知道具体类
);
```

> **注意**: `activateDefaultTyping` 在 Jackson 2.15+ 已废弃，但序列化功能正常。这可能导致 `redis-cli KEYS *` 看不到预期的简单字符串值（实际存的是 JSON + 类型头）。

## 用户缓存生命周期

```mermaid
sequenceDiagram
    participant Login as 登录
    participant Cache as UserCacheService
    participant Redis as Redis
    participant Logout as 登出/删用户

    Login->>Cache: setUser(user)
    Cache->>Redis: SET allahpan:member:{email} = user (TTL 24h)
    Note over Redis: 24小时自动过期

    Note over Login: 后续请求
    Login->>Cache: getUser(email)
    Cache->>Redis: GET allahpan:member:{email}
    Redis-->>Cache: User JSON

    Logout->>Cache: delUser(userId)
    Cache->>Cache: userMapper.selectByPrimaryKey(userId)
    Cache->>Cache: 取 email → memberKey(email)
    Cache->>Redis: DEL allahpan:member:{email}
```

## 关键文件索引

| 组件 | 文件 | 关键方法/注解 |
|------|------|--------------|
| Redis 配置 | `BaseRedisConfig.java` | `redisTemplate()`, `redisSerializer()` |
| Redis 接口 | `RedisService.java` | `set/get/del/exists/expire/incr` |
| Redis 实现 | `RedisServiceImpl.java` | 所有 `opsForXxx()` 操作 |
| 缓存切面 | `RedisCacheAspect.java` | `@Around("cacheAspect()")` |
| 异常标记 | `CacheException.java` | `@Target({METHOD, TYPE})` |
| 用户缓存 | `UserCacheServiceImpl.java` | `getUser/setUser/delUser` |
| 验证码缓存 | `AuthCodeServiceImpl.java` | `sendCode/verifyCode` |
