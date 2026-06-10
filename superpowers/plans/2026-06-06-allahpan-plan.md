# AllahPan 云盘系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零构建 AllahPan 共享云盘系统——Maven 多模块 Spring Boot 后端 + Vue 3 前端 + Docker Compose 一键部署。

**Architecture:** 5 个 Maven 模块（common → security → mbg → core + search），单队列 + 状态机处理文件流水线，MinIO 预签名 URL 直传，ES 文件内容搜索。

**Tech Stack:** Spring Boot 3.5 / JDK 17 / MyBatis + MBG / MySQL 8.0 / Redis 7.0 / RabbitMQ 3.12 / Elasticsearch 7.17 / MinIO / Ollama 千问3-VL / Vue 3 + Element Plus / Docker Compose

---

## 文件结构总览

```
allahpan/
├── pom.xml                                  # Maven 聚合 POM
├── docker-compose.yml                       # 生产环境一键编排（含 Cloudflare Tunnel）
├── docker-compose-dev.yml                   # 开发环境精简编排
├── nginx/nginx.conf                         # nginx 反向代理配置
├── cloudflared/                             # Cloudflare Tunnel 配置
│   ├── config.yml
│   └── credentials.json
│
├── allahpan-common/
│   └── src/main/java/com/allahpan/common/
│       ├── api/CommonResult.java
│       ├── api/CommonPage.java
│       ├── api/ResultCode.java
│       ├── exception/ApiException.java
│       ├── exception/Asserts.java
│       ├── exception/GlobalExceptionHandler.java
│       ├── service/RedisService.java
│       ├── service/impl/RedisServiceImpl.java
│       ├── config/BaseRedisConfig.java
│       ├── domain/WebLog.java
│       ├── log/WebLogAspect.java
│       └── util/MinioUtil.java
│
├── allahpan-security/
│   └── src/main/java/com/allahpan/security/
│       ├── util/JwtTokenUtil.java
│       ├── component/JwtAuthenticationTokenFilter.java
│       ├── component/RestAuthenticationEntryPoint.java
│       ├── component/RestfulAccessDeniedHandler.java
│       ├── config/SecurityConfig.java
│       ├── aspect/RedisCacheAspect.java
│       └── annotation/CacheException.java
│
├── allahpan-mbg/
│   ├── pom.xml (mysql-connector, mbg dependencies)
│   ├── generatorConfig.xml
│   └── src/main/java/com/allahpan/mbg/
│       └── Generator.java
│
├── allahpan-core/
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/main/
│       ├── java/com/allahpan/
│       │   ├── AllahPanApplication.java
│       │   ├── bo/AdminUserDetails.java
│       │   ├── config/
│       │   │   ├── MallSecurityConfig.java
│       │   │   ├── MinioConfig.java
│       │   │   ├── RabbitMqConfig.java
│       │   │   └── ThreadPoolConfig.java
│       │   ├── controller/
│       │   │   ├── AuthController.java
│       │   │   ├── UserController.java
│       │   │   ├── FileController.java
│       │   │   ├── FavoriteController.java
│       │   │   ├── SearchController.java
│       │   │   └── ShareController.java
│       │   ├── service/
│       │   │   ├── UserService.java → impl/UserServiceImpl.java
│       │   │   ├── FileService.java → impl/FileServiceImpl.java
│       │   │   ├── FavoriteService.java → impl/FavoriteServiceImpl.java
│       │   │   ├── ShareService.java → impl/ShareServiceImpl.java
│       │   │   ├── UserCacheService.java → impl/UserCacheServiceImpl.java
│       │   │   └── AuthCodeService.java → impl/AuthCodeServiceImpl.java
│       │   ├── dao/ + resources/dao/
│       │   │   └── FileDao.java / FileDao.xml
│       │   ├── component/
│       │   │   ├── FileProcessSender.java
│       │   │   ├── FileProcessReceiver.java
│       │   │   ├── SmsService.java
│       │   │   └── OllamaService.java
│       │   ├── domain/
│       │   │   ├── FileProcessMessage.java
│       │   │   ├── LoginRequest.java
│       │   │   └── FileUploadResult.java
│       │   └── dto/
│       │       └── SearchResultDto.java
│       └── resources/
│           ├── application.yml
│           ├── application-dev.yml
│           ├── application-prod.yml
│           └── dao/FileDao.xml
│
├── allahpan-search/
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/main/
│       ├── java/com/allahpan/search/
│       │   ├── SearchApplication.java
│       │   ├── domain/EsFile.java
│       │   ├── repository/EsFileRepository.java
│       │   ├── service/EsFileService.java → impl/EsFileServiceImpl.java
│       │   └── controller/EsFileController.java
│       └── resources/
│           ├── application.yml
│           └── application-dev.yml
│
└── allahpan-web/                            # Vue 3 前端（略）
```

---

### Task 1: 项目骨架 — Maven 聚合 + common + mbg

**目标:** 搭建 Maven 多模块骨架，创建 common 和 mbg 两个基础模块，生成初始数据库模型

- [ ] **Step 1.1: 创建项目根目录和聚合 POM**

```bash
# 创建项目根目录（根据你的环境调整路径）
# Mac/Linux:  mkdir -p ~/projects/allahpan
# Windows:    mkdir F:\Java\allahpan  (或在 IDEA 中直接创建 Maven 项目)
mkdir -p ~/projects/allahpan
```

```xml
<!-- allahpan/pom.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.allahpan</groupId>
    <artifactId>allahpan</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>
    <name>AllahPan</name>
    <description>AllahPan 共享云盘系统</description>

    <modules>
        <module>allahpan-common</module>
        <module>allahpan-mbg</module>
        <module>allahpan-security</module>
        <module>allahpan-core</module>
        <module>allahpan-search</module>
    </modules>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.5.14</version>
        <relativePath/>
    </parent>

    <properties>
        <java.version>17</java.version>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <skipTests>true</skipTests>
        <mybatis-starter.version>3.0.4</mybatis-starter.version>
        <mybatis.version>3.5.19</mybatis.version>
        <mysql-connector.version>9.3.0</mysql-connector.version>
        <druid.version>1.2.24</druid.version>
        <pagehelper.version>6.1.1</pagehelper.version>
        <hutool.version>5.8.40</hutool.version>
        <springdoc.version>2.8.17</springdoc.version>
        <minio.version>8.5.7</minio.version>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>com.allahpan</groupId>
                <artifactId>allahpan-common</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.allahpan</groupId>
                <artifactId>allahpan-mbg</artifactId>
                <version>${project.version}</version>
            </dependency>
            <dependency>
                <groupId>com.allahpan</groupId>
                <artifactId>allahpan-security</artifactId>
                <version>${project.version}</version>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

- [ ] **Step 1.2: 创建 allahpan-common 模块**

```bash
# 创建 allahpan-common 包目录结构
# Mac/Linux (bash):
mkdir -p allahpan-common/src/main/java/com/allahpan/common/{api,exception,service/impl,config,domain,log,util}
# Windows (PowerShell) — 逐条创建:
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/api
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/exception
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/service/impl
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/config
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/domain
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/log
# New-Item -ItemType Directory -Force -Path allahpan-common/src/main/java/com/allahpan/common/util
```

```xml
<!-- allahpan-common/pom.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.allahpan</groupId>
        <artifactId>allahpan</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>allahpan-common</artifactId>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-aop</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>io.minio</groupId>
            <artifactId>minio</artifactId>
            <version>${minio.version}</version>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 1.3: 创建 CommonResult、ResultCode、CommonPage**

```java
// allahpan-common/src/main/java/com/allahpan/common/api/ResultCode.java
package com.allahpan.common.api;

public enum ResultCode {
    SUCCESS(200, "操作成功"),
    FAILED(500, "操作失败"),
    VALIDATE_FAILED(404, "参数检验失败"),
    UNAUTHORIZED(401, "暂未登录或 token 已过期"),
    FORBIDDEN(403, "没有相关权限"),
    TOO_MANY_REQUESTS(429, "操作过于频繁，请稍后再试"),
    CODE_SEND_LIMIT(429, "请 30 秒后再获取验证码"),
    CODE_ERROR(400, "验证码错误"),
    CODE_EXPIRED(400, "验证码已过期");

    private final long code;
    private final String message;

    ResultCode(long code, String message) {
        this.code = code;
        this.message = message;
    }
    public long getCode() { return code; }
    public String getMessage() { return message; }
}
```

```java
// allahpan-common/src/main/java/com/allahpan/common/api/CommonResult.java
package com.allahpan.common.api;

public class CommonResult<T> {
    private long code;
    private String message;
    private T data;

    protected CommonResult() {}
    protected CommonResult(long code, String message, T data) {
        this.code = code; this.message = message; this.data = data;
    }

    public static <T> CommonResult<T> success(T data) {
        return new CommonResult<>(ResultCode.SUCCESS.getCode(), ResultCode.SUCCESS.getMessage(), data);
    }
    public static <T> CommonResult<T> success(T data, String message) {
        return new CommonResult<>(ResultCode.SUCCESS.getCode(), message, data);
    }
    public static <T> CommonResult<T> failed(String message) {
        return new CommonResult<>(ResultCode.FAILED.getCode(), message, null);
    }
    public static <T> CommonResult<T> failed(ResultCode code) {
        return new CommonResult<>(code.getCode(), code.getMessage(), null);
    }
    public static <T> CommonResult<T> validateFailed(String message) {
        return new CommonResult<>(ResultCode.VALIDATE_FAILED.getCode(), message, null);
    }
    public static <T> CommonResult<T> unauthorized(T data) {
        return new CommonResult<>(ResultCode.UNAUTHORIZED.getCode(), ResultCode.UNAUTHORIZED.getMessage(), data);
    }
    public static <T> CommonResult<T> forbidden(T data) {
        return new CommonResult<>(ResultCode.FORBIDDEN.getCode(), ResultCode.FORBIDDEN.getMessage(), data);
    }

    public long getCode() { return code; }
    public void setCode(long code) { this.code = code; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public T getData() { return data; }
    public void setData(T data) { this.data = data; }
}
```

```java
// allahpan-common/src/main/java/com/allahpan/common/api/CommonPage.java
package com.allahpan.common.api;

import com.github.pagehelper.Page;
import java.util.List;

public class CommonPage<T> {
    private Integer pageNum;
    private Integer pageSize;
    private Integer totalPage;
    private Long total;
    private List<T> list;

    public static <T> CommonPage<T> restPage(List<T> list) {
        CommonPage<T> result = new CommonPage<>();
        if (list instanceof Page<T> page) {
            result.setPageNum(page.getPageNum());
            result.setPageSize(page.getPageSize());
            result.setTotalPage(page.getPages());
            result.setTotal(page.getTotal());
            result.setList(page.getResult());
        }
        return result;
    }

    public Integer getPageNum() { return pageNum; }
    public void setPageNum(Integer pageNum) { this.pageNum = pageNum; }
    public Integer getPageSize() { return pageSize; }
    public void setPageSize(Integer pageSize) { this.pageSize = pageSize; }
    public Integer getTotalPage() { return totalPage; }
    public void setTotalPage(Integer totalPage) { this.totalPage = totalPage; }
    public Long getTotal() { return total; }
    public void setTotal(Long total) { this.total = total; }
    public List<T> getList() { return list; }
    public void setList(List<T> list) { this.list = list; }
}
```

- [ ] **Step 1.4: 创建 ApiException、Asserts、GlobalExceptionHandler**

```java
// allahpan-common/src/main/java/com/allahpan/common/exception/ApiException.java
package com.allahpan.common.exception;

import com.allahpan.common.api.ResultCode;

public class ApiException extends RuntimeException {
    private final ResultCode resultCode;

    public ApiException(ResultCode resultCode) {
        super(resultCode.getMessage());
        this.resultCode = resultCode;
    }
    public ApiException(String message) {
        super(message);
        this.resultCode = ResultCode.FAILED;
    }
    public ResultCode getResultCode() { return resultCode; }
}
```

```java
// allahpan-common/src/main/java/com/allahpan/common/exception/Asserts.java
package com.allahpan.common.exception;

import com.allahpan.common.api.ResultCode;

public class Asserts {
    public static void fail(String message) {
        throw new ApiException(message);
    }
    public static void fail(ResultCode resultCode) {
        throw new ApiException(resultCode);
    }
    public static void isTrue(boolean condition, String message) {
        if (!condition) throw new ApiException(message);
    }
    public static void isTrue(boolean condition, ResultCode resultCode) {
        if (!condition) throw new ApiException(resultCode);
    }
}
```

```java
// allahpan-common/src/main/java/com/allahpan/common/exception/GlobalExceptionHandler.java
package com.allahpan.common.exception;

import com.allahpan.common.api.CommonResult;
import org.springframework.validation.BindException;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseBody;

@ControllerAdvice
public class GlobalExceptionHandler {

    @ResponseBody
    @ExceptionHandler(ApiException.class)
    public CommonResult<Object> handleApiException(ApiException e) {
        if (e.getResultCode() != null) {
            return CommonResult.failed(e.getResultCode());
        }
        return CommonResult.failed(e.getMessage());
    }

    @ResponseBody
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public CommonResult<Object> handleValidException(MethodArgumentNotValidException e) {
        BindingResult bindingResult = e.getBindingResult();
        String message = bindingResult.getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .reduce((a, b) -> a + "; " + b)
                .orElse("参数校验失败");
        return CommonResult.validateFailed(message);
    }

    @ResponseBody
    @ExceptionHandler(BindException.class)
    public CommonResult<Object> handleBindException(BindException e) {
        return CommonResult.validateFailed(e.getBindingResult().getAllErrors().get(0).getDefaultMessage());
    }
}
```

- [ ] **Step 1.5: 创建 RedisService 接口**

```java
// allahpan-common/src/main/java/com/allahpan/common/service/RedisService.java
package com.allahpan.common.service;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

public interface RedisService {
    // String 操作
    void set(String key, Object value);
    void set(String key, Object value, long time);
    void set(String key, Object value, long time, TimeUnit timeUnit);
    Object get(String key);
    Boolean del(String key);
    Long del(List<String> keys);
    Boolean expire(String key, long time);
    Long getExpire(String key);
    Boolean hasKey(String key);
    Long incr(String key, long delta);
    Long decr(String key, long delta);

    // Hash 操作
    void hSet(String key, String hashKey, Object value);
    void hSet(String key, String hashKey, Object value, long time);
    Object hGet(String key, String hashKey);
    Map<Object, Object> hGetAll(String key);
    void hDel(String key, Object... hashKeys);
    Boolean hHasKey(String key, String hashKey);
    Long hIncr(String key, String hashKey, Long delta);

    // Set 操作
    Long sAdd(String key, Object... values);
    Long sAdd(String key, long time, Object... values);
    Set<Object> sMembers(String key);
    Boolean sIsMember(String key, Object value);
    Long sRemove(String key, Object... values);

    // List 操作
    Long lPush(String key, Object value);
    List<Object> lRange(String key, long start, long end);
    Long lRemove(String key, long count, Object value);
}
```

```java
// allahpan-common/src/main/java/com/allahpan/common/service/impl/RedisServiceImpl.java
package com.allahpan.common.service.impl;

import com.allahpan.common.service.RedisService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

@Service
public class RedisServiceImpl implements RedisService {
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Override
    public void set(String key, Object value) {
        redisTemplate.opsForValue().set(key, value);
    }
    @Override
    public void set(String key, Object value, long time) {
        set(key, value, time, TimeUnit.SECONDS);
    }
    @Override
    public void set(String key, Object value, long time, TimeUnit timeUnit) {
        redisTemplate.opsForValue().set(key, value, time, timeUnit);
    }
    @Override
    public Object get(String key) {
        return redisTemplate.opsForValue().get(key);
    }
    @Override
    public Boolean del(String key) {
        return redisTemplate.delete(key);
    }
    @Override
    public Long del(List<String> keys) {
        return redisTemplate.delete(keys);
    }
    @Override
    public Boolean expire(String key, long time) {
        return redisTemplate.expire(key, time, TimeUnit.SECONDS);
    }
    @Override
    public Long getExpire(String key) {
        return redisTemplate.getExpire(key, TimeUnit.SECONDS);
    }
    @Override
    public Boolean hasKey(String key) {
        return redisTemplate.hasKey(key);
    }
    @Override
    public Long incr(String key, long delta) {
        return redisTemplate.opsForValue().increment(key, delta);
    }
    @Override
    public Long decr(String key, long delta) {
        return redisTemplate.opsForValue().decrement(key, delta);
    }
    @Override
    public void hSet(String key, String hashKey, Object value) {
        redisTemplate.opsForHash().put(key, hashKey, value);
    }
    @Override
    public void hSet(String key, String hashKey, Object value, long time) {
        redisTemplate.opsForHash().put(key, hashKey, value);
        expire(key, time);
    }
    @Override
    public Object hGet(String key, String hashKey) {
        return redisTemplate.opsForHash().get(key, hashKey);
    }
    @Override
    public Map<Object, Object> hGetAll(String key) {
        return redisTemplate.opsForHash().entries(key);
    }
    @Override
    public void hDel(String key, Object... hashKeys) {
        redisTemplate.opsForHash().delete(key, hashKeys);
    }
    @Override
    public Boolean hHasKey(String key, String hashKey) {
        return redisTemplate.opsForHash().hasKey(key, hashKey);
    }
    @Override
    public Long hIncr(String key, String hashKey, Long delta) {
        return redisTemplate.opsForHash().increment(key, hashKey, delta);
    }
    @Override
    public Long sAdd(String key, Object... values) {
        return redisTemplate.opsForSet().add(key, values);
    }
    @Override
    public Long sAdd(String key, long time, Object... values) {
        Long count = redisTemplate.opsForSet().add(key, values);
        expire(key, time);
        return count;
    }
    @Override
    public Set<Object> sMembers(String key) {
        return redisTemplate.opsForSet().members(key);
    }
    @Override
    public Boolean sIsMember(String key, Object value) {
        return redisTemplate.opsForSet().isMember(key, value);
    }
    @Override
    public Long sRemove(String key, Object... values) {
        return redisTemplate.opsForSet().remove(key, values);
    }
    @Override
    public Long lPush(String key, Object value) {
        return redisTemplate.opsForList().rightPush(key, value);
    }
    @Override
    public List<Object> lRange(String key, long start, long end) {
        return redisTemplate.opsForList().range(key, start, end);
    }
    @Override
    public Long lRemove(String key, long count, Object value) {
        return redisTemplate.opsForList().remove(key, count, value);
    }
}
```

- [ ] **Step 1.6: 创建 BaseRedisConfig（Jackson JSON 序列化）**

```java
// allahpan-common/src/main/java/com/allahpan/common/config/BaseRedisConfig.java
package com.allahpan.common.config;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.Jackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.RedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import java.time.Duration;

@Configuration
public class BaseRedisConfig {

    @Bean
    public RedisSerializer<Object> redisSerializer() {
        ObjectMapper objectMapper = new ObjectMapper();
        objectMapper.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.ANY);
        objectMapper.activateDefaultTyping(
            com.fasterxml.jackson.databind.jsontype.impl.LaissezFaireSubTypeValidator.instance,
            ObjectMapper.DefaultTyping.NON_FINAL
        );
        return new Jackson2JsonRedisSerializer<>(objectMapper, Object.class);
    }

    @Bean
    public RedisTemplate<String, Object> redisTemplate(
            RedisConnectionFactory connectionFactory,
            RedisSerializer<Object> redisSerializer) {
        RedisTemplate<String, Object> redisTemplate = new RedisTemplate<>();
        redisTemplate.setConnectionFactory(connectionFactory);
        redisTemplate.setKeySerializer(new StringRedisSerializer());
        redisTemplate.setValueSerializer(redisSerializer);
        redisTemplate.setHashKeySerializer(new StringRedisSerializer());
        redisTemplate.setHashValueSerializer(redisSerializer);
        redisTemplate.afterPropertiesSet();
        return redisTemplate;
    }

    @Bean
    public RedisCacheManager redisCacheManager(
            RedisConnectionFactory connectionFactory,
            RedisSerializer<Object> redisSerializer) {
        RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofDays(1))
                .serializeKeysWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair
                        .fromSerializer(redisSerializer))
                .disableCachingNullValues();
        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(config)
                .build();
    }
}
```

- [ ] **Step 1.7: 创建 allahpan-mbg 模块 + MBG 生成**

```xml
<!-- allahpan-mbg/pom.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.allahpan</groupId>
        <artifactId>allahpan</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>allahpan-mbg</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.allahpan</groupId>
            <artifactId>allahpan-common</artifactId>
        </dependency>
        <dependency>
            <groupId>org.mybatis</groupId>
            <artifactId>mybatis</artifactId>
            <version>${mybatis.version}</version>
        </dependency>
        <dependency>
            <groupId>org.mybatis.generator</groupId>
            <artifactId>mybatis-generator-core</artifactId>
            <version>1.4.2</version>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <version>${mysql-connector.version}</version>
        </dependency>
        <dependency>
            <groupId>io.swagger.core.v3</groupId>
            <artifactId>swagger-annotations</artifactId>
            <version>2.2.20</version>
        </dependency>
    </dependencies>
</project>
```

```sql
-- 先执行建表 SQL（在 MySQL allahpan 数据库中）
CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    phone VARCHAR(20) NOT NULL UNIQUE COMMENT '手机号',
    password VARCHAR(255) COMMENT 'BCrypt 密文，首次登录前为 NULL',
    nickname VARCHAR(50) COMMENT '昵称',
    avatar_url VARCHAR(255) COMMENT '头像 MinIO key',
    status TINYINT DEFAULT 1 COMMENT '0=禁用 1=正常',
    first_login TINYINT DEFAULT 1 COMMENT '0=已设密码 1=首次登录',
    last_login_time DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT '用户表';

CREATE TABLE files (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    uploader_id BIGINT COMMENT '上传者',
    parent_id BIGINT DEFAULT 0 COMMENT '父目录ID，0=根目录',
    file_name VARCHAR(255) NOT NULL COMMENT '文件名',
    file_path VARCHAR(500) COMMENT '虚拟路径',
    storage_key VARCHAR(500) COMMENT 'MinIO 存储 key',
    file_type VARCHAR(20) COMMENT 'FOLDER/IMAGE/VIDEO/DOCUMENT/OTHER',
    file_size BIGINT DEFAULT 0 COMMENT '文件大小（字节）',
    content_type VARCHAR(100) COMMENT 'MIME 类型',
    thumbnail_key VARCHAR(500) COMMENT '缩略图 MinIO key',
    is_folder TINYINT DEFAULT 0 COMMENT '0=文件 1=文件夹',
    origin_text LONGTEXT COMMENT 'PDF 解析/OCR 提取的文本',
    process_status TINYINT DEFAULT 0 COMMENT '0=待处理 1=缩略图完成 2=文本提取完成 3=索引完成 -1=失败',
    md5 VARCHAR(32) COMMENT '文件 MD5',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    delete_time DATETIME COMMENT '软删除时间'
) COMMENT '文件表';

CREATE TABLE file_favorites (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    file_id BIGINT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_file (user_id, file_id)
) COMMENT '文件收藏表';
```

```java
// allahpan-mbg/src/main/java/com/allahpan/mbg/Generator.java
package com.allahpan.mbg;

import org.mybatis.generator.api.MyBatisGenerator;
import org.mybatis.generator.config.Configuration;
import org.mybatis.generator.config.xml.ConfigurationParser;
import org.mybatis.generator.internal.DefaultShellCallback;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;

public class Generator {
    public static void main(String[] args) throws Exception {
        List<String> warnings = new ArrayList<>();
        try (InputStream is = Generator.class.getResourceAsStream("/generatorConfig.xml")) {
            ConfigurationParser cp = new ConfigurationParser(warnings);
            Configuration config = cp.parseConfiguration(is);
            DefaultShellCallback callback = new DefaultShellCallback(true);
            MyBatisGenerator generator = new MyBatisGenerator(config, callback, warnings);
            generator.generate(null);
            warnings.forEach(System.out::println);
        }
    }
}
```

```xml
<!-- allahpan-mbg/src/main/resources/generatorConfig.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE generatorConfiguration PUBLIC
    "-//mybatis.org//DTD MyBatis Generator Configuration 1.0//EN"
    "http://mybatis.org/dtd/mybatis-generator-config_1_0.dtd">
<generatorConfiguration>
    <context id="AllahPanTables" targetRuntime="MyBatis3">
        <commentGenerator type="com.allahpan.mbg.CommentGenerator"/>
        <jdbcConnection driverClass="com.mysql.cj.jdbc.Driver"
            connectionURL="jdbc:mysql://localhost:3306/allahpan?useSSL=false&amp;serverTimezone=Asia/Shanghai"
            userId="root" password="root"/>
        <javaModelGenerator targetPackage="com.allahpan.mbg.model"
            targetProject="src/main/java"/>
        <sqlMapGenerator targetPackage="com.allahpan.mbg.mapper"
            targetProject="src/main/resources"/>
        <javaClientGenerator type="XMLMAPPER"
            targetPackage="com.allahpan.mbg.mapper"
            targetProject="src/main/java"/>
        <table tableName="users" domainObjectName="User">
            <generatedKey column="id" sqlStatement="MySQL" identity="true"/>
        </table>
        <table tableName="files" domainObjectName="File">
            <generatedKey column="id" sqlStatement="MySQL" identity="true"/>
        </table>
        <table tableName="file_favorites" domainObjectName="FileFavorite">
            <generatedKey column="id" sqlStatement="MySQL" identity="true"/>
        </table>
    </context>
</generatorConfiguration>
```

- [ ] **Step 1.8: 验证: 编译聚合项目**

```bash
# 在项目根目录下执行（以下命令均假设你已 cd 到项目根目录）
mvn clean compile
# 预期: BUILD SUCCESS，所有模块编译通过
```

- [ ] **Step 1.9: WebLog — 控制器请求日志 AOP**

```java
// allahpan-common/src/main/java/com/allahpan/common/domain/WebLog.java
package com.allahpan.common.domain;

public class WebLog {
    private String method;
    private String url;
    private String ip;
    private String className;
    private String methodName;
    private Object[] args;
    private Object result;
    private long spendTime;
    private String errorMessage;

    public String getMethod() { return method; }
    public void setMethod(String method) { this.method = method; }
    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
    public String getIp() { return ip; }
    public void setIp(String ip) { this.ip = ip; }
    public String getClassName() { return className; }
    public void setClassName(String className) { this.className = className; }
    public String getMethodName() { return methodName; }
    public void setMethodName(String methodName) { this.methodName = methodName; }
    public Object[] getArgs() { return args; }
    public void setArgs(Object[] args) { this.args = args; }
    public Object getResult() { return result; }
    public void setResult(Object result) { this.result = result; }
    public long getSpendTime() { return spendTime; }
    public void setSpendTime(long spendTime) { this.spendTime = spendTime; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("\n========== 请求日志 ==========\n");
        sb.append("IP      : ").append(ip).append("\n");
        sb.append("URL     : ").append(method).append(" ").append(url).append("\n");
        sb.append("Class   : ").append(className).append(".").append(methodName).append("\n");
        if (errorMessage != null) {
            sb.append("Error   : ").append(errorMessage).append("\n");
        }
        sb.append("Time    : ").append(spendTime).append(" ms\n");
        sb.append("================================");
        return sb.toString();
    }
}
```

```java
// allahpan-common/src/main/java/com/allahpan/common/log/WebLogAspect.java
package com.allahpan.common.log;

import com.allahpan.common.domain.WebLog;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpServletRequest;

@Aspect
@Component
public class WebLogAspect {

    private static final Logger log = LoggerFactory.getLogger(WebLogAspect.class);

    @Pointcut("execution(public * com.allahpan..controller..*.*(..))")
    public void controllerPointcut() {}

    @Around("controllerPointcut()")
    public Object doAround(ProceedingJoinPoint joinPoint) throws Throwable {
        long startTime = System.currentTimeMillis();
        WebLog webLog = new WebLog();

        ServletRequestAttributes attributes =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attributes != null) {
            HttpServletRequest request = attributes.getRequest();
            webLog.setUrl(request.getRequestURL().toString());
            webLog.setMethod(request.getMethod());
            webLog.setIp(request.getRemoteAddr());
        }
        webLog.setClassName(joinPoint.getTarget().getClass().getName());
        webLog.setMethodName(joinPoint.getSignature().getName());
        webLog.setArgs(joinPoint.getArgs());

        Object result;
        try {
            result = joinPoint.proceed();
            webLog.setResult(result);
            webLog.setSpendTime(System.currentTimeMillis() - startTime);
            log.info("{}", webLog);
        } catch (Throwable e) {
            webLog.setSpendTime(System.currentTimeMillis() - startTime);
            webLog.setErrorMessage(e.getMessage());
            log.error("{}", webLog);
            throw e;
        }
        return result;
    }
}
```

---

### Task 2: 认证模块 — security + 验证码 + 双通道登录

**目标:** 创建 security 模块，实现三层验证码防护 + 双通道登录 + JWT

- [ ] **Step 2.1: 创建 allahpan-security 模块**

```xml
<!-- allahpan-security/pom.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.allahpan</groupId>
        <artifactId>allahpan</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>allahpan-security</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.allahpan</groupId>
            <artifactId>allahpan-common</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>cn.hutool</groupId>
            <artifactId>hutool-jwt</artifactId>
            <version>${hutool.version}</version>
        </dependency>
        <dependency>
            <groupId>jakarta.servlet</groupId>
            <artifactId>jakarta.servlet-api</artifactId>
            <scope>provided</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2.2: 创建 JwtTokenUtil（复用 mall 的 Hutool JWT 模式）**

```java
// allahpan-security/src/main/java/com/allahpan/security/util/JwtTokenUtil.java
package com.allahpan.security.util;

import cn.hutool.core.date.DateUtil;
import cn.hutool.jwt.JWT;
import cn.hutool.jwt.JWTUtil;
import cn.hutool.jwt.signers.JWTSigner;
import cn.hutool.jwt.signers.JWTSignerUtil;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;

@Component
public class JwtTokenUtil {

    private static final String CLAIM_USER_ID = "userId";
    private static final String CLAIM_HAS_PASSWORD = "hasPassword";
    private static final String CLAIM_CREATED = "created";

    @Value("${jwt.secret}")
    private String secret;
    @Value("${jwt.expiration}")
    private Long expiration;
    @Value("${jwt.tokenHead}")
    private String tokenHead;

    public String generateToken(Long userId, String phone, boolean hasPassword) {
        Map<String, Object> claims = new HashMap<>();
        claims.put(CLAIM_USER_ID, userId);
        claims.put(CLAIM_HAS_PASSWORD, hasPassword);
        claims.put(CLAIM_CREATED, new Date());
        return generateToken(claims, phone);
    }

    private String generateToken(Map<String, Object> claims, String subject) {
        JWTSigner signer = JWTSignerUtil.hs512(secret.getBytes());
        return JWT.create()
                .addHeaders(Map.of("typ", "JWT", "alg", "HS512"))
                .addPayloads(claims)
                .setPayload("sub", subject)
                .setExpiresAt(DateUtil.offsetSecond(new Date(), expiration.intValue()))
                .setSigner(signer)
                .sign();
    }

    public boolean validateToken(String token, String phone) {
        String sub = getSubjectFromToken(token);
        return sub != null && sub.equals(phone) && !isTokenExpired(token);
    }

    public String getSubjectFromToken(String token) {
        try {
            return (String) JWTUtil.parseToken(token)
                    .getPayload().getClaim("sub");
        } catch (Exception e) {
            return null;
        }
    }

    public Long getUserIdFromToken(String token) {
        try {
            Object userId = JWTUtil.parseToken(token)
                    .getPayload().getClaim(CLAIM_USER_ID);
            return userId instanceof Number ? ((Number) userId).longValue() : null;
        } catch (Exception e) {
            return null;
        }
    }

    public boolean getHasPasswordFromToken(String token) {
        try {
            Object val = JWTUtil.parseToken(token)
                    .getPayload().getClaim(CLAIM_HAS_PASSWORD);
            return val instanceof Boolean ? (Boolean) val : false;
        } catch (Exception e) {
            return false;
        }
    }

    private boolean isTokenExpired(String token) {
        try {
            Object expObj = JWTUtil.parseToken(token)
                    .getPayload().getClaim("exp");
            if (expObj == null) return true;
            Date exp;
            if (expObj instanceof Date) {
                exp = (Date) expObj;
            } else if (expObj instanceof Number) {
                // exp 存储为 Unix 时间戳（秒），需乘以 1000 转为毫秒
                exp = new Date(((Number) expObj).longValue() * 1000);
            } else {
                return true;
            }
            return exp.before(new Date());
        } catch (Exception e) {
            return true;
        }
    }

    public boolean canRefresh(String token) {
        return !isTokenExpired(token);
    }

    public String refreshToken(String token) {
        Date created = (Date) JWTUtil.parseToken(token)
                .getPayload().getClaim(CLAIM_CREATED);
        // 距过期 < 30 分钟才刷新
        if (created != null && System.currentTimeMillis() - created.getTime() <
                (expiration - 1800) * 1000) {
            return null;
        }
        String phone = getSubjectFromToken(token);
        Long userId = getUserIdFromToken(token);
        boolean hasPassword = getHasPasswordFromToken(token);
        return generateToken(userId, phone, hasPassword);
    }
}
```

- [ ] **Step 2.3: 创建 JwtAuthenticationTokenFilter**

```java
// allahpan-security/src/main/java/com/allahpan/security/component/JwtAuthenticationTokenFilter.java
package com.allahpan.security.component;

import com.allahpan.security.util.JwtTokenUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

public class JwtAuthenticationTokenFilter extends OncePerRequestFilter {

    @Autowired
    private UserDetailsService userDetailsService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;
    @Value("${jwt.tokenHead}")
    private String tokenHead;
    @Value("${jwt.tokenHeader}")
    private String tokenHeader;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String authHeader = request.getHeader(tokenHeader);
        if (authHeader != null && authHeader.startsWith(tokenHead)) {
            String token = authHeader.substring(tokenHead.length());
            String phone = jwtTokenUtil.getSubjectFromToken(token);
            if (phone != null && SecurityContextHolder.getContext().getAuthentication() == null) {
                UserDetails userDetails = userDetailsService.loadUserByUsername(phone);
                if (jwtTokenUtil.validateToken(token, phone)) {
                    UsernamePasswordAuthenticationToken authentication =
                            new UsernamePasswordAuthenticationToken(
                                    userDetails, null, userDetails.getAuthorities());
                    authentication.setDetails(
                            new WebAuthenticationDetailsSource().buildDetails(request));
                    SecurityContextHolder.getContext().setAuthentication(authentication);
                }
            }
        }
        chain.doFilter(request, response);
    }
}
```

- [ ] **Step 2.4: 创建 Security 辅助组件**

```java
// allahpan-security/src/main/java/com/allahpan/security/component/RestAuthenticationEntryPoint.java
package com.allahpan.security.component;

import com.allahpan.common.api.CommonResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;

import java.io.IOException;

public class RestAuthenticationEntryPoint implements AuthenticationEntryPoint {
    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response,
            AuthenticationException e) throws IOException {
        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json");
        response.setStatus(HttpServletResponse.SC_OK);
        response.getWriter().println(
            new ObjectMapper().writeValueAsString(CommonResult.unauthorized("暂未登录或 token 已过期"))
        );
    }
}
```

```java
// allahpan-security/src/main/java/com/allahpan/security/component/RestfulAccessDeniedHandler.java
package com.allahpan.security.component;

import com.allahpan.common.api.CommonResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.web.access.AccessDeniedHandler;

import java.io.IOException;

public class RestfulAccessDeniedHandler implements AccessDeniedHandler {
    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response,
            AccessDeniedException e) throws IOException {
        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json");
        response.setStatus(HttpServletResponse.SC_OK);
        response.getWriter().println(
            new ObjectMapper().writeValueAsString(CommonResult.forbidden("没有相关权限"))
        );
    }
}
```

- [ ] **Step 2.5: 创建 SecurityConfig**

```java
// allahpan-security/src/main/java/com/allahpan/security/config/SecurityConfig.java
package com.allahpan.security.config;

import com.allahpan.security.component.JwtAuthenticationTokenFilter;
import com.allahpan.security.component.RestAuthenticationEntryPoint;
import com.allahpan.security.component.RestfulAccessDeniedHandler;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import java.util.List;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    @ConfigurationProperties(prefix = "secure.ignored")
    public IgnoredUrlsConfig ignoredUrlsConfig() {
        return new IgnoredUrlsConfig();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http,
            JwtAuthenticationTokenFilter jwtFilter) throws Exception {
        List<String> urls = ignoredUrlsConfig().getUrls();
        http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers(urls.toArray(new String[0])).permitAll()
                .requestMatchers(HttpMethod.OPTIONS).permitAll()
                .anyRequest().authenticated())
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint(new RestAuthenticationEntryPoint())
                .accessDeniedHandler(new RestfulAccessDeniedHandler()))
            .addFilterBefore(jwtFilter,
                UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    public static class IgnoredUrlsConfig {
        private List<String> urls;
        public List<String> getUrls() { return urls; }
        public void setUrls(List<String> urls) { this.urls = urls; }
    }
}
```

- [ ] **Step 2.6: 创建 CacheException 注解 + RedisCacheAspect**

```java
// allahpan-security/src/main/java/com/allahpan/security/annotation/CacheException.java
package com.allahpan.security.annotation;

import java.lang.annotation.*;

@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface CacheException {
}
```

```java
// allahpan-security/src/main/java/com/allahpan/security/aspect/RedisCacheAspect.java
package com.allahpan.security.aspect;

import com.allahpan.security.annotation.CacheException;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.aspectj.lang.reflect.MethodSignature;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Aspect
@Component
@Order(2)
public class RedisCacheAspect {
    private static final Logger LOGGER = LoggerFactory.getLogger(RedisCacheAspect.class);

    @Pointcut("execution(public * com.allahpan.service.*CacheService.*(..))")
    public void cacheAspect() {}

    @Around("cacheAspect()")
    public Object doAround(ProceedingJoinPoint joinPoint) throws Throwable {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        java.lang.reflect.Method method = signature.getMethod();
        Object result = null;
        try {
            result = joinPoint.proceed();
        } catch (Throwable throwable) {
            if (method.isAnnotationPresent(CacheException.class)) {
                throw throwable;
            }
            LOGGER.error("Redis cache error: {}", throwable.getMessage());
        }
        return result;
    }
}
```

- [ ] **Step 2.7: 创建 allahpan-core 模块骨架**

```xml
<!-- allahpan-core/pom.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.allahpan</groupId>
        <artifactId>allahpan</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>allahpan-core</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.allahpan</groupId>
            <artifactId>allahpan-security</artifactId>
        </dependency>
        <dependency>
            <groupId>com.allahpan</groupId>
            <artifactId>allahpan-mbg</artifactId>
        </dependency>
        <dependency>
            <groupId>org.mybatis.spring.boot</groupId>
            <artifactId>mybatis-spring-boot-starter</artifactId>
            <version>${mybatis-starter.version}</version>
        </dependency>
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
        </dependency>
        <dependency>
            <groupId>com.alibaba</groupId>
            <artifactId>druid-spring-boot-3-starter</artifactId>
            <version>${druid.version}</version>
        </dependency>
        <dependency>
            <groupId>com.github.pagehelper</groupId>
            <artifactId>pagehelper-spring-boot-starter</artifactId>
            <version>${pagehelper.version}</version>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-amqp</artifactId>
        </dependency>
        <!-- springdoc-openapi 2.8.17 兼容 Spring Boot 3.x jakarta 命名空间 -->
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>${springdoc.version}</version>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

```java
// allahpan-core/src/main/java/com/allahpan/AllahPanApplication.java
package com.allahpan;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan({"com.allahpan.mbg.mapper", "com.allahpan.dao"})
public class AllahPanApplication {
    public static void main(String[] args) {
        SpringApplication.run(AllahPanApplication.class, args);
    }
}
```

```yaml
# allahpan-core/src/main/resources/application-dev.yml
server:
  port: 8088

spring:
  datasource:
    url: jdbc:mysql://localhost:3306/allahpan?useSSL=false&serverTimezone=Asia/Shanghai&characterEncoding=utf-8
    username: root
    password: root
    driver-class-name: com.mysql.cj.jdbc.Driver
    type: com.alibaba.druid.pool.DruidDataSource
  data:
    redis:
      host: localhost
      port: 6379
      password:
      timeout: 3000ms
  rabbitmq:
    host: localhost
    port: 5672
    username: guest
    password: guest

mybatis:
  mapper-locations:
    - classpath:com/allahpan/mbg/mapper/*.xml
    - classpath:dao/*.xml
  configuration:
    map-underscore-to-camel-case: true

jwt:
  tokenHeader: Authorization
  tokenHead: "Bearer "
  secret: allahpan-jwt-secret
  expiration: 604800  # 7天

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

redis:
  database: allahpan
  key:
    authCode: 'authCode'
    member: 'member'
  expire:
    common: 86400        # 24小时
    authCode: 300        # 5分钟

allahpan:
  file:
    # 云盘根目录。留空则自动检测（通过 Java System.getProperty("os.name")）:
    #   Windows → %USERPROFILE%/AllahPan（如 C:/Users/用户名/AllahPan）
    #   Mac     → ~/Desktop/AllahPan
    # 手动设置示例（Windows: D:/CloudDisk  Mac/Linux: /data/allahpan）
    # 注意: Java Paths.get() 会自动处理路径分隔符，使用 / 即可跨平台
    root-dir:

minio:
  endpoint: http://localhost:9000
  accessKey: minioadmin
  secretKey: minioadmin
  bucketName: allahpan-files
  thumbnailBucket: allahpan-thumbnails
  preSignExpiry: 300      # 预签名 URL 有效期（秒）

ollama:
  base-url: http://localhost:11434
  model: qwen3-vl
  timeout: 60             # OCR 超时（秒）
```

- [ ] **Step 2.8: 创建 MallSecurityConfig（core 模块的 UserDetailsService + DynamicSecurityService）**

```java
// allahpan-core/src/main/java/com/allahpan/config/MallSecurityConfig.java
package com.allahpan.config;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.mbg.model.UserExample;
import com.allahpan.service.UserCacheService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

import java.util.Collections;

@Configuration
public class MallSecurityConfig {

    @Autowired
    private UserMapper userMapper;
    @Autowired
    private UserCacheService userCacheService;

    @Bean
    public UserDetailsService userDetailsService() {
        return username -> {
            // 先查缓存
            User user = userCacheService.getUser(username);
            if (user == null) {
                UserExample example = new UserExample();
                example.createCriteria().andPhoneEqualTo(username).andStatusEqualTo(1);
                var list = userMapper.selectByExample(example);
                if (!list.isEmpty()) {
                    user = list.get(0);
                    userCacheService.setUser(user);
                }
            }
            if (user == null) {
                throw new UsernameNotFoundException("用户不存在: " + username);
            }
            return new AdminUserDetails(user, Collections.emptyList());
        };
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/bo/AdminUserDetails.java
package com.allahpan.bo;

import com.allahpan.mbg.model.User;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.List;

public class AdminUserDetails implements UserDetails {
    private final User user;
    private final List<? extends GrantedAuthority> authorities;

    public AdminUserDetails(User user, List<? extends GrantedAuthority> authorities) {
        this.user = user;
        this.authorities = authorities;
    }

    public User getUser() { return user; }
    public Long getUserId() { return user.getId(); }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() { return authorities; }
    @Override
    public String getPassword() { return user.getPassword(); }
    @Override
    public String getUsername() { return user.getPhone(); }
    @Override
    public boolean isAccountNonExpired() { return true; }
    @Override
    public boolean isAccountNonLocked() { return true; }
    @Override
    public boolean isCredentialsNonExpired() { return true; }
    @Override
    public boolean isEnabled() { return user.getStatus() == 1; }
}
```

- [ ] **Step 2.9: 创建 AuthCodeService（三层验证码防护）**

```java
// allahpan-core/src/main/java/com/allahpan/service/AuthCodeService.java
package com.allahpan.service;

public interface AuthCodeService {
    void sendCode(String phone);
    void verifyCode(String phone, String code);
}
```

```java
// allahpan-core/src/main/java/com/allahpan/service/impl/AuthCodeServiceImpl.java
package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.service.RedisService;
import com.allahpan.security.annotation.CacheException;
import com.allahpan.service.AuthCodeService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Random;

@Service
public class AuthCodeServiceImpl implements AuthCodeService {
    @Autowired
    private RedisService redisService;

    @Value("${redis.database}")
    private String REDIS_DATABASE;
    @Value("${redis.key.authCode}")
    private String REDIS_KEY_AUTH_CODE;
    @Value("${redis.expire.authCode}")
    private Long REDIS_EXPIRE_AUTH_CODE;

    private static final int SEND_LIMIT_SECONDS = 30;
    private static final int MAX_ATTEMPTS_PER_HOUR = 50;
    private static final int ATTEMPTS_TTL = 3600; // 1小时

    private String codeKey(String phone) {
        return REDIS_DATABASE + ":" + REDIS_KEY_AUTH_CODE + ":" + phone;
    }
    private String sendLimitKey(String phone) {
        return REDIS_DATABASE + ":sendLimit:" + phone;
    }
    private String attemptsKey(String phone) {
        return REDIS_DATABASE + ":attempts:" + phone;
    }

    @Override
    public void sendCode(String phone) {
        // ① 检查发送频率
        if (redisService.hasKey(sendLimitKey(phone))) {
            Asserts.fail(ResultCode.CODE_SEND_LIMIT);
        }
        // ② 生成 6 位验证码
        String code = String.format("%06d", new Random().nextInt(1000000));
        // ③ 存入 Redis，5 分钟过期
        redisService.set(codeKey(phone), code, REDIS_EXPIRE_AUTH_CODE);
        // ④ 设置 30 秒发送间隔
        redisService.set(sendLimitKey(phone), "1", SEND_LIMIT_SECONDS);
        // 开发环境：控制台打印验证码
        System.out.println("========== 验证码: " + code + " (手机号: " + phone + ") ==========");
    }

    @Override
    @CacheException  // Redis 挂了直接抛异常，不降级
    public void verifyCode(String phone, String code) {
        // ① 检查小时重试次数
        Object attemptsObj = redisService.get(attemptsKey(phone));
        long attempts = attemptsObj instanceof Number ? ((Number) attemptsObj).longValue() : 0;
        if (attempts >= MAX_ATTEMPTS_PER_HOUR) {
            Asserts.fail(ResultCode.TOO_MANY_REQUESTS);
        }
        // ② 比对验证码
        Object stored = redisService.get(codeKey(phone));
        if (stored == null) {
            Asserts.fail(ResultCode.CODE_EXPIRED);
        }
        if (!stored.toString().equals(code)) {
            // 失败：递增错误计数并设置过期时间
            redisService.incr(attemptsKey(phone), 1);
            redisService.expire(attemptsKey(phone), ATTEMPTS_TTL);
            Asserts.fail(ResultCode.CODE_ERROR);
        }
        // ③ 验证成功：删除验证码（不删 attempts，保留小时计数）
        redisService.del(codeKey(phone));
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/component/SmsService.java
package com.allahpan.component;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 短信发送服务 —— 开发阶段使用控制台打印替代真实短信网关
 */
@Component
public class SmsService {

    private static final Logger LOG = LoggerFactory.getLogger(SmsService.class);

    /**
     * 发送短信验证码
     * @param phone 手机号
     * @param code  验证码
     */
    public void send(String phone, String code) {
        LOG.info("========== 短信验证码: {} (手机号: {}) ==========", code, phone);
    }
}
```

- [ ] **Step 2.10: 创建 UserCacheService**

```java
// allahpan-core/src/main/java/com/allahpan/service/UserCacheService.java
package com.allahpan.service;

import com.allahpan.mbg.model.User;

public interface UserCacheService {
    User getUser(String phone);
    void setUser(User user);
    void delUser(Long userId);
}
```

```java
// allahpan-core/src/main/java/com/allahpan/service/impl/UserCacheServiceImpl.java
package com.allahpan.service.impl;

import com.allahpan.common.service.RedisService;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.service.UserCacheService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class UserCacheServiceImpl implements UserCacheService {
    @Autowired
    private RedisService redisService;
    @Autowired
    private UserMapper userMapper;
    @Value("${redis.database}")
    private String REDIS_DATABASE;
    @Value("${redis.key.member}")
    private String REDIS_KEY_MEMBER;
    @Value("${redis.expire.common}")
    private Long REDIS_EXPIRE;

    private String memberKey(String phone) {
        return REDIS_DATABASE + ":" + REDIS_KEY_MEMBER + ":" + phone;
    }

    @Override
    public User getUser(String phone) {
        return (User) redisService.get(memberKey(phone));
    }

    @Override
    public void setUser(User user) {
        redisService.set(memberKey(user.getPhone()), user, REDIS_EXPIRE);
    }

    @Override
    public void delUser(Long userId) {
        User user = userMapper.selectByPrimaryKey(userId);
        if (user != null) {
            redisService.del(memberKey(user.getPhone()));
        }
    }
}
```

- [ ] **Step 2.11: 创建 AuthController（双通道登录）**

```java
// allahpan-core/src/main/java/com/allahpan/controller/AuthController.java
package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.security.util.JwtTokenUtil;
import com.allahpan.service.AuthCodeService;
import com.allahpan.service.UserService;
import com.allahpan.domain.LoginRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Tag(name = "AuthController", description = "认证管理")
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @Autowired
    private AuthCodeService authCodeService;
    @Autowired
    private UserService userService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;

    @Operation(summary = "发送验证码")
    @PostMapping("/send-code")
    public CommonResult<Void> sendCode(@Valid @RequestBody LoginRequest req) {
        authCodeService.sendCode(req.getPhone());
        return CommonResult.success(null, "验证码已发送");
    }

    @Operation(summary = "验证码登录")
    @PostMapping("/login-by-code")
    public CommonResult<Map<String, Object>> loginByCode(@Valid @RequestBody LoginRequest req) {
        authCodeService.verifyCode(req.getPhone(), req.getCode());
        var user = userService.loginByCode(req.getPhone());
        return buildLoginResponse(user.getId(), user.getPhone(), user.getFirstLogin() == 0);
    }

    @Operation(summary = "密码登录")
    @PostMapping("/login-by-password")
    public CommonResult<Map<String, Object>> loginByPassword(@Valid @RequestBody LoginRequest req) {
        var user = userService.loginByPassword(req.getPhone(), req.getPassword());
        return buildLoginResponse(user.getId(), user.getPhone(), true);
    }

    private CommonResult<Map<String, Object>> buildLoginResponse(Long userId, String phone, boolean hasPassword) {
        String token = jwtTokenUtil.generateToken(userId, phone, hasPassword);
        return CommonResult.success(Map.of(
            "token", token,
            "tokenHead", "Bearer ",
            "userId", userId,
            "phone", phone,
            "hasPassword", hasPassword,
            "firstLogin", !hasPassword  // 前端据此判断是否跳转设置密码页
        ));
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/domain/LoginRequest.java
package com.allahpan.domain;

import jakarta.validation.constraints.NotBlank;

public class LoginRequest {
    @NotBlank(message = "手机号不能为空")
    private String phone;
    private String code;
    private String password;

    public String getPhone() { return phone; }
    public void setPhone(String phone) { this.phone = phone; }
    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
}
```

- [ ] **Step 2.12: 创建 UserService + UserController**

```java
// allahpan-core/src/main/java/com/allahpan/service/UserService.java
package com.allahpan.service;

import com.allahpan.mbg.model.User;

public interface UserService {
    User loginByCode(String phone);
    User loginByPassword(String phone, String password);
    User setPassword(Long userId, String newPassword);
    User getCurrentUser();
}
```

```java
// allahpan-core/src/main/java/com/allahpan/service/impl/UserServiceImpl.java
package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.bo.AdminUserDetails;
import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.User;
import com.allahpan.mbg.model.UserExample;
import com.allahpan.service.UserCacheService;
import com.allahpan.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.Date;

@Service
public class UserServiceImpl implements UserService {
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private UserCacheService userCacheService;
    @Autowired
    private PasswordEncoder passwordEncoder;

    @Override
    public User loginByCode(String phone) {
        UserExample example = new UserExample();
        example.createCriteria().andPhoneEqualTo(phone);
        var list = userMapper.selectByExample(example);
        User user;
        if (list.isEmpty()) {
            // 自动注册
            user = new User();
            user.setPhone(phone);
            user.setNickname("用户" + phone.substring(phone.length() - 4));
            user.setStatus(1);
            user.setFirstLogin(1);
            user.setCreateTime(new Date());
            userMapper.insert(user);
        } else {
            user = list.get(0);
            Asserts.isTrue(user.getStatus() == 1, "账号已被禁用");
            user.setLastLoginTime(new Date());
            userMapper.updateByPrimaryKeySelective(user);
        }
        userCacheService.setUser(user);
        return user;
    }

    @Override
    public User loginByPassword(String phone, String password) {
        UserExample example = new UserExample();
        example.createCriteria().andPhoneEqualTo(phone);
        var list = userMapper.selectByExample(example);
        Asserts.isTrue(!list.isEmpty(), "手机号未注册");
        User user = list.get(0);
        Asserts.isTrue(user.getStatus() == 1, "账号已被禁用");
        Asserts.isTrue(passwordEncoder.matches(password, user.getPassword()), "密码错误");
        user.setLastLoginTime(new Date());
        userMapper.updateByPrimaryKeySelective(user);
        userCacheService.setUser(user);
        return user;
    }

    @Override
    public User setPassword(Long userId, String newPassword) {
        User user = userMapper.selectByPrimaryKey(userId);
        Asserts.isTrue(user != null, "用户不存在");
        user.setPassword(passwordEncoder.encode(newPassword));
        user.setFirstLogin(0);
        userMapper.updateByPrimaryKeySelective(user);
        userCacheService.setUser(user);
        return user;
    }

    @Override
    public User getCurrentUser() {
        AdminUserDetails details = (AdminUserDetails) SecurityContextHolder
                .getContext().getAuthentication().getPrincipal();
        return details.getUser();
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/controller/UserController.java
package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.security.util.JwtTokenUtil;
import com.allahpan.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Tag(name = "UserController", description = "用户管理")
@RestController
@RequestMapping("/api/user")
public class UserController {

    @Autowired
    private UserService userService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;

    @Operation(summary = "首次设置密码")
    @PostMapping("/set-password")
    public CommonResult<Map<String, Object>> setPassword(@Valid @RequestBody SetPasswordRequest req) {
        var user = userService.getCurrentUser();
        userService.setPassword(user.getId(), req.getNewPassword());
        String token = jwtTokenUtil.generateToken(user.getId(), user.getPhone(), true);
        return CommonResult.success(Map.of("token", token, "hasPassword", true));
    }

    @Operation(summary = "获取当前用户信息")
    @GetMapping("/me")
    public CommonResult<?> getCurrentUser() {
        var user = userService.getCurrentUser();
        user.setPassword(null); // 不返回密码
        return CommonResult.success(user);
    }

    public static class SetPasswordRequest {
        @NotBlank(message = "新密码不能为空")
        private String newPassword;
        public String getNewPassword() { return newPassword; }
        public void setNewPassword(String newPassword) { this.newPassword = newPassword; }
    }
}
```

- [ ] **Step 2.13: 验证: 启动应用 + 测试登录接口**

```bash
# 在项目根目录下执行
mvn clean package -pl allahpan-core -am -DskipTests
mvn spring-boot:run -pl allahpan-core

# 另开终端测试（以下 curl 命令适用于 bash/zsh；Windows PowerShell 用户见注释）
curl -X POST http://localhost:8088/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000"}'
# 预期: {"code":200,"message":"验证码已发送"}
# 控制台输出验证码

curl -X POST http://localhost:8088/api/auth/login-by-code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000","code":"483921"}'
# 预期: {"code":200,"data":{"token":"...","firstLogin":true,...}}

# Windows PowerShell 等效写法（PowerShell 不支持 \ 续行和单引号 JSON，需转义双引号）:
# curl.exe -X POST http://localhost:8088/api/auth/send-code -H "Content-Type: application/json" -d '{\"phone\":\"13800138000\"}'
```

---

### Task 3: 文件模块 — MinIO 直传 + 目录树

**目标:** 实现 MinIO 预签名 URL 上传、文件 CRUD、目录树查询

- [ ] **Step 3.1: 创建 MinioUtil + MinioConfig**

```java
// allahpan-common/src/main/java/com/allahpan/common/util/MinioUtil.java
package com.allahpan.common.util;

import io.minio.*;
import io.minio.http.Method;

import java.util.concurrent.TimeUnit;

public class MinioUtil {
    private final MinioClient client;
    private final String bucketName;
    private final String thumbnailBucket;
    private final int preSignExpiry;

    public MinioUtil(MinioClient client, String bucketName, String thumbnailBucket, int preSignExpiry) {
        this.client = client;
        this.bucketName = bucketName;
        this.thumbnailBucket = thumbnailBucket;
        this.preSignExpiry = preSignExpiry;
        createBucketIfNotExists(bucketName);
        createBucketIfNotExists(thumbnailBucket);
    }

    private void createBucketIfNotExists(String bucket) {
        try {
            if (!client.bucketExists(BucketExistsArgs.builder().bucket(bucket).build())) {
                client.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
            }
        } catch (Exception e) {
            throw new RuntimeException("创建 MinIO bucket 失败: " + bucket, e);
        }
    }

    public String generatePreSignedUrl(String storageKey) {
        try {
            return client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.PUT)
                    .bucket(bucketName)
                    .object(storageKey)
                    .expiry(preSignExpiry, TimeUnit.SECONDS)
                    .build());
        } catch (Exception e) {
            throw new RuntimeException("生成预签名 URL 失败", e);
        }
    }

    public String generateAccessUrl(String storageKey) {
        try {
            return client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(bucketName)
                    .object(storageKey)
                    .expiry(7, TimeUnit.DAYS)
                    .build());
        } catch (Exception e) {
            return null;
        }
    }

    public String getThumbnailAccessUrl(String storageKey) {
        if (storageKey == null) return null;
        try {
            return client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(Method.GET)
                    .bucket(thumbnailBucket)
                    .object(storageKey)
                    .expiry(7, TimeUnit.DAYS)
                    .build());
        } catch (Exception e) {
            return null;
        }
    }

    public void removeObject(String storageKey) {
        try {
            client.removeObject(RemoveObjectArgs.builder()
                    .bucket(bucketName).object(storageKey).build());
        } catch (Exception ignored) {}
    }

    /** 永久删除文件对象（垃圾站物理删除用） */
    public void deleteObject(String storageKey) {
        removeObject(storageKey);
    }

    /** 永久删除缩略图对象（垃圾站物理删除用） */
    public void deleteThumbnail(String thumbnailKey) {
        if (thumbnailKey == null) return;
        try {
            client.removeObject(RemoveObjectArgs.builder()
                    .bucket(thumbnailBucket).object(thumbnailKey).build());
        } catch (Exception e) {
            throw new RuntimeException("删除缩略图失败: " + thumbnailKey, e);
        }
    }

    public MinioClient getClient() { return client; }
    public String getBucketName() { return bucketName; }
    public String getThumbnailBucket() { return thumbnailBucket; }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/config/MinioConfig.java
package com.allahpan.config;

import com.allahpan.common.util.MinioUtil;
import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MinioConfig {

    @Value("${minio.endpoint}")
    private String endpoint;
    @Value("${minio.accessKey}")
    private String accessKey;
    @Value("${minio.secretKey}")
    private String secretKey;
    @Value("${minio.bucketName}")
    private String bucketName;
    @Value("${minio.thumbnailBucket}")
    private String thumbnailBucket;
    @Value("${minio.preSignExpiry}")
    private int preSignExpiry;

    @Bean
    public MinioClient minioClient() {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .build();
    }

    @Bean
    public MinioUtil minioUtil(MinioClient minioClient) {
        return new MinioUtil(minioClient, bucketName, thumbnailBucket, preSignExpiry);
    }
}
```

- [ ] **Step 3.1.5: 创建 FileStorageConfig（OS 感知云盘根目录）**

```java
// allahpan-core/src/main/java/com/allahpan/config/FileStorageConfig.java
package com.allahpan.config;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Configuration
public class FileStorageConfig {

    private static final Logger log = LoggerFactory.getLogger(FileStorageConfig.class);

    @Value("${allahpan.file.root-dir:}")
    private String configuredRootDir;

    private Path rootDir;

    @PostConstruct
    public void init() {
        if (configuredRootDir != null && !configuredRootDir.isBlank()) {
            rootDir = Paths.get(configuredRootDir);
        } else {
            String os = System.getProperty("os.name").toLowerCase();
            String userHome = System.getProperty("user.home");
            if (os.contains("win")) {
                rootDir = Paths.get(userHome, "AllahPan");
            } else if (os.contains("mac")) {
                rootDir = Paths.get(userHome, "Desktop", "AllahPan");
            } else {
                rootDir = Paths.get(userHome, "AllahPan");
            }
        }
        try {
            Files.createDirectories(rootDir);
            log.info("云盘根目录: {}", rootDir.toAbsolutePath());
        } catch (Exception e) {
            throw new RuntimeException("无法创建云盘根目录: " + rootDir, e);
        }
    }

    public Path getRootDir() { return rootDir; }
    public Path getUserDir(Long userId) { return rootDir.resolve("user_" + userId); }
}
```

- [ ] **Step 3.2: 创建 FileService + FileController**

```java
// allahpan-core/src/main/java/com/allahpan/service/FileService.java
package com.allahpan.service;

import com.allahpan.mbg.model.File;
import com.allahpan.domain.FileUploadResult;

import java.util.List;

public interface FileService {
    FileUploadResult preUpload(String md5, String fileName, Long parentId);
    File confirmUpload(String storageKey, String fileName, Long parentId,
                       String md5, Long fileSize, String contentType);
    File createFolder(String folderName, Long parentId);
    List<File> listFiles(Long parentId);
    List<File> getDirectoryTree(Long folderId);
    void deleteFile(Long fileId);
    File getFileById(Long fileId);

    // ========== 垃圾站 ==========
    List<File> listTrash(int pageNum, int pageSize);
    void restoreFile(Long fileId);
    void permanentDelete(Long fileId);
}
```

```java
// allahpan-core/src/main/java/com/allahpan/domain/FileUploadResult.java
package com.allahpan.domain;

public class FileUploadResult {
    private boolean instant;        // 是否秒传
    private String storageKey;
    private String preSignedUrl;
    private Long fileId;

    public static FileUploadResult instant(Long fileId) {
        FileUploadResult r = new FileUploadResult();
        r.instant = true;
        r.fileId = fileId;
        return r;
    }
    public static FileUploadResult needUpload(String storageKey, String preSignedUrl) {
        FileUploadResult r = new FileUploadResult();
        r.instant = false;
        r.storageKey = storageKey;
        r.preSignedUrl = preSignedUrl;
        return r;
    }

    public boolean isInstant() { return instant; }
    public void setInstant(boolean instant) { this.instant = instant; }
    public String getStorageKey() { return storageKey; }
    public void setStorageKey(String storageKey) { this.storageKey = storageKey; }
    public String getPreSignedUrl() { return preSignedUrl; }
    public void setPreSignedUrl(String preSignedUrl) { this.preSignedUrl = preSignedUrl; }
    public Long getFileId() { return fileId; }
    public void setFileId(Long fileId) { this.fileId = fileId; }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/service/impl/FileServiceImpl.java
package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.util.MinioUtil;
import com.allahpan.domain.FileUploadResult;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.FileService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Date;
import java.util.List;
import java.util.UUID;

@Service
public class FileServiceImpl implements FileService {
    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private MinioUtil minioUtil;

    @Override
    public FileUploadResult preUpload(String md5, String fileName, Long parentId) {
        // 秒传检测
        FileExample example = new FileExample();
        example.createCriteria().andMd5EqualTo(md5).andIsFolderEqualTo(0)
                .andDeleteTimeIsNull();
        var list = fileMapper.selectByExample(example);
        if (!list.isEmpty()) {
            // 秒传：创建一条新记录指向同一个 storage_key
            File existing = list.get(0);
            File dup = new File();
            dup.setUploaderId(getCurrentUserId());
            dup.setParentId(parentId);
            dup.setFileName(fileName);
            dup.setStorageKey(existing.getStorageKey());
            dup.setFileSize(existing.getFileSize());
            dup.setContentType(existing.getContentType());
            dup.setMd5(md5);
            dup.setFileType(existing.getFileType());
            dup.setIsFolder(0);
            dup.setProcessStatus(3); // 秒传直接标记完成
            dup.setCreateTime(new Date());
            fileMapper.insert(dup);
            return FileUploadResult.instant(dup.getId());
        }
        // 生成 storageKey + 预签名URL
        String dateStr = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy/MM"));
        String ext = "";
        int dotIdx = fileName.lastIndexOf('.');
        if (dotIdx > 0) ext = fileName.substring(dotIdx);
        String storageKey = getCurrentUserId() + "/" + dateStr + "/" + UUID.randomUUID() + ext;
        String preSignedUrl = minioUtil.generatePreSignedUrl(storageKey);
        return FileUploadResult.needUpload(storageKey, preSignedUrl);
    }

    @Override
    public File confirmUpload(String storageKey, String fileName, Long parentId,
                              String md5, Long fileSize, String contentType) {
        File file = new File();
        file.setUploaderId(getCurrentUserId());
        file.setParentId(parentId != null ? parentId : 0L);
        // 验证 parentId 指向一个文件夹
        if (file.getParentId() > 0) {
            File parent = fileMapper.selectByPrimaryKey(file.getParentId());
            if (parent == null || parent.getIsFolder() == null || parent.getIsFolder() != 1) {
                Asserts.fail(ResultCode.VALIDATE_FAILED);
            }
        }
        file.setFileName(fileName);
        file.setStorageKey(storageKey);
        file.setFileSize(fileSize);
        file.setContentType(contentType);
        file.setMd5(md5);
        file.setIsFolder(0);
        file.setProcessStatus(0);
        file.setFileType(detectFileType(contentType));
        file.setCreateTime(new Date());

        // 构建虚拟路径
        StringBuilder path = new StringBuilder("/" + fileName);
        Long pid = parentId;
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            path.insert(0, "/" + parent.getFileName());
            pid = parent.getParentId();
        }
        file.setFilePath(path.toString());
        fileMapper.insert(file);
        return file;
    }

    @Override
    public File createFolder(String folderName, Long parentId) {
        File file = new File();
        file.setUploaderId(getCurrentUserId());
        file.setParentId(parentId != null ? parentId : 0L);
        file.setFileName(folderName);
        file.setIsFolder(1);
        file.setFileType("FOLDER");
        file.setProcessStatus(3); // 文件夹不需要处理
        file.setCreateTime(new Date());
        // 构建完整路径（包含父级链）
        StringBuilder path = new StringBuilder("/" + folderName);
        Long pid = parentId;
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            path.insert(0, "/" + parent.getFileName());
            pid = parent.getParentId();
        }
        file.setFilePath(path.toString());
        fileMapper.insert(file);
        return file;
    }

    @Override
    public List<File> listFiles(Long parentId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(parentId)
                .andDeleteTimeIsNull();
        example.setOrderByClause("is_folder DESC, create_time DESC");
        return fileMapper.selectByExample(example);
    }

    @Override
    public List<File> getDirectoryTree(Long folderId) {
        // 从当前目录追溯到根
        var list = new java.util.ArrayList<File>();
        Long current = folderId;
        while (current != null && current > 0) {
            File f = fileMapper.selectByPrimaryKey(current);
            if (f == null) break;
            list.add(0, f);
            current = f.getParentId();
        }
        return list;
    }

    @Override
    public void deleteFile(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        // 软删除
        file.setDeleteTime(new Date());
        fileMapper.updateByPrimaryKeySelective(file);
        // 如果是文件夹，递归软删除子节点
        if (file.getIsFolder() == 1) {
            deleteChildren(fileId);
        }
    }

    private void deleteChildren(Long folderId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId).andDeleteTimeIsNull();
        var children = fileMapper.selectByExample(example);
        for (File child : children) {
            child.setDeleteTime(new Date());
            fileMapper.updateByPrimaryKeySelective(child);
            if (child.getIsFolder() == 1) {
                deleteChildren(child.getId());
            }
        }
    }

    @Override
    public File getFileById(Long fileId) {
        return fileMapper.selectByPrimaryKey(fileId);
    }

    // ========== 垃圾站实现 ==========
    // 注意: 永久删除需要注入 MinioUtil（已有）和 FileProcessSender（Task 4 中创建后注入）
    // @Autowired
    // private FileProcessSender fileProcessSender;

    @Override
    public List<File> listTrash(int pageNum, int pageSize) {
        FileExample example = new FileExample();
        example.createCriteria().andDeleteTimeIsNotNull();
        example.setOrderByClause("delete_time DESC");
        PageHelper.startPage(pageNum, pageSize);
        return fileMapper.selectByExample(example);
    }

    @Override
    public void restoreFile(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        Asserts.isTrue(file.getDeleteTime() != null, "文件不在垃圾站中");
        // 检查父目录是否在垃圾站中
        if (file.getParentId() != null && file.getParentId() > 0) {
            File parent = fileMapper.selectByPrimaryKey(file.getParentId());
            if (parent != null && parent.getDeleteTime() != null) {
                Asserts.fail("父文件夹在垃圾站中，请先恢复父文件夹");
            }
        }
        file.setDeleteTime(null);
        fileMapper.updateByPrimaryKeySelective(file);
        if (file.getIsFolder() == 1) {
            restoreChildren(fileId);
        }
    }

    private void restoreChildren(Long folderId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId).andDeleteTimeIsNotNull();
        var children = fileMapper.selectByExample(example);
        for (File child : children) {
            child.setDeleteTime(null);
            fileMapper.updateByPrimaryKeySelective(child);
            if (child.getIsFolder() == 1) {
                restoreChildren(child.getId());
            }
        }
    }

    @Override
    public void permanentDelete(Long fileId) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        // 物理删除 MinIO 文件和缩略图
        if (file.getStorageKey() != null) {
            try {
                minioUtil.deleteObject(file.getStorageKey());
            } catch (Exception e) {
                log.warn("删除 MinIO 文件失败: {}", file.getStorageKey(), e);
            }
        }
        if (file.getThumbnailKey() != null) {
            try {
                minioUtil.deleteThumbnail(file.getThumbnailKey());
            } catch (Exception e) {
                log.warn("删除缩略图失败: {}", file.getThumbnailKey(), e);
            }
        }
        // 物理删除子节点
        if (file.getIsFolder() == 1) {
            permanentDeleteChildren(fileId);
        }
        // 从 ES 索引移除（FileProcessSender 在 Task 4 中创建）
        // if (fileProcessSender != null) fileProcessSender.deleteFromEs(fileId);
        // 删除数据库记录
        fileMapper.deleteByPrimaryKey(fileId);
    }

    private void permanentDeleteChildren(Long folderId) {
        FileExample example = new FileExample();
        example.createCriteria().andParentIdEqualTo(folderId);
        var children = fileMapper.selectByExample(example);
        for (File child : children) {
            permanentDelete(child.getId());
        }
    }

    private String detectFileType(String contentType) {
        if (contentType == null) return "OTHER";
        if (contentType.startsWith("image/")) return "IMAGE";
        if (contentType.startsWith("video/")) return "VIDEO";
        if (contentType.startsWith("application/pdf") ||
            contentType.contains("document") ||
            contentType.contains("spreadsheet")) return "DOCUMENT";
        return "OTHER";
    }

    private Long getCurrentUserId() {
        var auth = org.springframework.security.core.context.SecurityContextHolder
                .getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof com.allahpan.bo.AdminUserDetails details) {
            return details.getUserId();
        }
        Asserts.fail(ResultCode.UNAUTHORIZED);
        return 0L; // unreachable, but required by compiler
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/controller/FileController.java
package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.common.util.MinioUtil;
import com.allahpan.component.FileProcessSender;
import com.allahpan.mbg.model.File;
import com.allahpan.service.FileService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Tag(name = "FileController", description = "文件管理")
@RestController
@RequestMapping("/api/file")
public class FileController {

    @Autowired
    private FileService fileService;
    @Autowired
    private MinioUtil minioUtil;
    @Autowired
    private FileProcessSender fileProcessSender;

    @Operation(summary = "预上传")
    @PostMapping("/pre-upload")
    public CommonResult<?> preUpload(@RequestBody Map<String, Object> req) {
        String md5 = (String) req.get("md5");
        String fileName = (String) req.get("fileName");
        Long parentId = req.get("parentId") != null
                ? ((Number) req.get("parentId")).longValue() : 0L;
        var result = fileService.preUpload(md5, fileName, parentId);
        return CommonResult.success(result);
    }

    @Operation(summary = "确认上传")
    @PostMapping("/confirm-upload")
    public CommonResult<File> confirmUpload(@RequestBody Map<String, Object> req) {
        String storageKey = (String) req.get("storageKey");
        String fileName = (String) req.get("fileName");
        Long parentId = req.get("parentId") != null
                ? ((Number) req.get("parentId")).longValue() : 0L;
        String md5 = (String) req.get("md5");
        Long fileSize = req.get("fileSize") != null
                ? ((Number) req.get("fileSize")).longValue() : 0L;
        String contentType = (String) req.get("contentType");
        File file = fileService.confirmUpload(storageKey, fileName, parentId, md5, fileSize, contentType);
        return CommonResult.success(file);
    }

    @Operation(summary = "创建文件夹")
    @PostMapping("/create-folder")
    public CommonResult<File> createFolder(@RequestBody Map<String, Object> req) {
        String folderName = (String) req.get("folderName");
        Long parentId = req.get("parentId") != null
                ? ((Number) req.get("parentId")).longValue() : 0L;
        return CommonResult.success(fileService.createFolder(folderName, parentId));
    }

    @Operation(summary = "文件列表")
    @GetMapping("/list")
    public CommonResult<?> listFiles(@RequestParam(defaultValue = "0") Long parentId) {
        var list = fileService.listFiles(parentId);
        // 附加缩略图URL
        list.forEach(f -> {
            if (f.getThumbnailKey() != null) {
                f.setThumbnailKey(minioUtil.getThumbnailAccessUrl(f.getThumbnailKey()));
            }
        });
        return CommonResult.success(list);
    }

    @Operation(summary = "目录树（面包屑导航）")
    @GetMapping("/tree/{folderId}")
    public CommonResult<?> getDirectoryTree(@PathVariable Long folderId) {
        return CommonResult.success(fileService.getDirectoryTree(folderId));
    }

    @Operation(summary = "删除文件")
    @DeleteMapping("/{fileId}")
    public CommonResult<Void> deleteFile(@PathVariable Long fileId) {
        fileService.deleteFile(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "文件详情")
    @GetMapping("/{fileId}")
    public CommonResult<File> getFile(@PathVariable Long fileId) {
        File file = fileService.getFileById(fileId);
        // 附加下载 URL
        if (file.getStorageKey() != null) {
            String accessUrl = minioUtil.generateAccessUrl(file.getStorageKey());
            // 临时标记（后续改为 DTO 或 transient 字段）
        }
        return CommonResult.success(file);
    }

    // ========== 垃圾站 ==========

    @Operation(summary = "垃圾站列表")
    @GetMapping("/trash")
    public CommonResult<List<File>> listTrash(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return CommonResult.success(fileService.listTrash(pageNum, pageSize));
    }

    @Operation(summary = "恢复文件")
    @PutMapping("/trash/{fileId}/restore")
    public CommonResult<Void> restoreFile(@PathVariable Long fileId) {
        fileService.restoreFile(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "永久删除")
    @DeleteMapping("/trash/{fileId}")
    public CommonResult<Void> permanentDelete(@PathVariable Long fileId) {
        fileService.permanentDelete(fileId);
        return CommonResult.success(null);
    }

    // ========== Phase 4 新增端点 ==========
    // 下载: GET /{fileId}/download → minioUtil.generateAccessUrl()
    // 重命名: PUT /{fileId}/rename {newName} → 递归重建子孙 filePath
    // 移动: PUT /{fileId}/move {targetParentId} → 循环检测 + 递归重建路径
    // 批量删除: DELETE /batch {fileIds} → 遍历 deleteFile() 容错
    // 详见 docs/api/03-file.md
}
```

- [ ] **Step 3.4: 新增文件操作端点**

Phase 4 新增 4 个文件端点和 1 个分享模块（独立 Task）：

| 端点 | 服务方法 | 核心逻辑 |
|------|----------|----------|
| `GET /{fileId}/download` | 复用 `getFileById()` + `MinioUtil.generateAccessUrl()` | 返回 `{downloadUrl, fileName, fileSize}` |
| `PUT /{fileId}/rename` | `renameFile(fileId, newName)` | 更新 fileName + `buildPath()` 重算 filePath，文件夹递归 `rebuildDescendantPaths()` |
| `PUT /{fileId}/move` | `moveFile(fileId, targetParentId)` | 校验目标 → 循环检测 `isDescendant()` → 更新 parentId + 重建路径 |
| `DELETE /batch` | `batchDelete(fileIds)` | 遍历调用 `deleteFile()`，容错返回 `{deletedCount, failedIds}` |

新增 3 个私有辅助方法：`buildPath()`（提取 confirmUpload/createFolder 重复逻辑）、`rebuildDescendantPaths()`、`isDescendant()`。

- [ ] **Step 3.5: 验证新增端点**

```bash
# 下载
curl "http://localhost:8088/api/file/43/download" -H "Authorization: Bearer $TOKEN"

# 重命名
curl -X PUT http://localhost:8088/api/file/43/rename -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"newName":"renamed.png"}'

# 移动
curl -X PUT http://localhost:8088/api/file/43/move -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"targetParentId":45}'

# 批量删除
curl -X DELETE http://localhost:8088/api/file/batch -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"fileIds":[43,44,45]}'
```
```

- [ ] **Step 3.3: 验证文件上传流程**

```bash
# 启动 MinIO（Docker）
# bash/zsh:
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
# Windows PowerShell（用反引号 ` 续行）:
# docker run -d --name minio -p 9000:9000 -p 9001:9001 `
#   -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin `
#   minio/minio server /data --console-address ":9001"

# 获取预签名URL（需要先登录获取 token）
# 以下命令适用于 bash/zsh:
TOKEN="<login-token>"
curl -X POST http://localhost:8080/api/file/pre-upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"md5":"d41d8cd98f00b204e9800998ecf8427e","fileName":"test.png","parentId":0}'
# Windows PowerShell 等效:
# $TOKEN = "<login-token>"
# curl.exe -X POST http://localhost:8080/api/file/pre-upload -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{\"md5\":\"d41d8cd98f00b204e9800998ecf8427e\",\"fileName\":\"test.png\",\"parentId\":0}'
# 预期: {"code":200,"data":{"instant":false,"storageKey":"1/2026/06/xxx.png","preSignedUrl":"http://..."}}
```

---

### Task 4: 处理流水线 — RabbitMQ 状态机 + 缩略图 + OCR

**目标:** 实现文件处理状态机，缩略图生成、PDF 文本提取、Ollama OCR

- [ ] **Step 4.1: 创建 RabbitMqConfig（队列 + DLX 重试）**

```java
// allahpan-core/src/main/java/com/allahpan/config/RabbitMqConfig.java
package com.allahpan.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMqConfig {

    public static final String PROCESS_EXCHANGE = "allahpan.file.process";
    public static final String PROCESS_QUEUE = "allahpan.file.process";
    public static final String PROCESS_ROUTING_KEY = "allahpan.file.process";

    // 重试相关（复用 mall 的 TTL + DLX 模式）
    public static final String RETRY_EXCHANGE = "allahpan.file.retry.direct";
    public static final String RETRY_QUEUE_TTL = "allahpan.file.retry.ttl";
    public static final String RETRY_ROUTING_KEY_TTL = "allahpan.file.retry.ttl";
    public static final String RETRY_ROUTING_KEY = "allahpan.file.retry";

    @Bean
    public DirectExchange processExchange() {
        return ExchangeBuilder.directExchange(PROCESS_EXCHANGE).durable(true).build();
    }

    @Bean
    public Queue processQueue() {
        return QueueBuilder.durable(PROCESS_QUEUE).build();
    }

    @Bean
    public Binding processBinding(DirectExchange processExchange, Queue processQueue) {
        return BindingBuilder.bind(processQueue).to(processExchange).with(PROCESS_ROUTING_KEY);
    }

    // ====== 重试延迟队列（TTL + DLX）======

    @Bean
    public DirectExchange retryExchange() {
        return ExchangeBuilder.directExchange(RETRY_EXCHANGE).durable(true).build();
    }

    @Bean
    public Queue retryTtlQueue() {
        return QueueBuilder.durable(RETRY_QUEUE_TTL)
                .withArgument("x-dead-letter-exchange", PROCESS_EXCHANGE)
                .withArgument("x-dead-letter-routing-key", PROCESS_ROUTING_KEY)
                .build();
    }

    @Bean
    public Binding retryTtlBinding(DirectExchange retryExchange, Queue retryTtlQueue) {
        return BindingBuilder.bind(retryTtlQueue).to(retryExchange).with(RETRY_ROUTING_KEY_TTL);
    }

    @Bean
    public MessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
```

- [ ] **Step 4.2: 创建 FileProcessMessage**

```java
// allahpan-core/src/main/java/com/allahpan/domain/FileProcessMessage.java
package com.allahpan.domain;

import java.io.Serializable;

public class FileProcessMessage implements Serializable {
    public enum Stage {
        UPLOADED, THUMBNAILED, TEXT_EXTRACTED, INDEXED, FAILED
    }

    private Long fileId;
    private Stage currentStage;
    private int retryCount;
    private String lastError;

    public FileProcessMessage() {}
    public FileProcessMessage(Long fileId, Stage currentStage) {
        this.fileId = fileId;
        this.currentStage = currentStage;
        this.retryCount = 0;
    }

    public Long getFileId() { return fileId; }
    public void setFileId(Long fileId) { this.fileId = fileId; }
    public Stage getCurrentStage() { return currentStage; }
    public void setCurrentStage(Stage currentStage) { this.currentStage = currentStage; }
    public int getRetryCount() { return retryCount; }
    public void setRetryCount(int retryCount) { this.retryCount = retryCount; }
    public String getLastError() { return lastError; }
    public void setLastError(String lastError) { this.lastError = lastError; }
}
```

- [ ] **Step 4.3: 创建 FileProcessSender**

```java
// allahpan-core/src/main/java/com/allahpan/component/FileProcessSender.java
package com.allahpan.component;

import com.allahpan.config.RabbitMqConfig;
import com.allahpan.domain.FileProcessMessage;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class FileProcessSender {

    @Autowired
    private RabbitTemplate rabbitTemplate;

    public void sendProcess(FileProcessMessage message) {
        rabbitTemplate.convertAndSend(
                RabbitMqConfig.PROCESS_EXCHANGE,
                RabbitMqConfig.PROCESS_ROUTING_KEY,
                message);
    }

    public void sendRetry(FileProcessMessage message, long delayMs) {
        MessagePostProcessor postProcessor = msg -> {
            msg.getMessageProperties().setExpiration(String.valueOf(delayMs));
            return msg;
        };
        rabbitTemplate.convertAndSend(
                RabbitMqConfig.RETRY_EXCHANGE,
                RabbitMqConfig.RETRY_ROUTING_KEY_TTL,
                message, postProcessor);
    }
}
```

- [ ] **Step 4.4: 创建 FileProcessReceiver（状态机核心）**

```java
// allahpan-core/src/main/java/com/allahpan/component/FileProcessReceiver.java
package com.allahpan.component;

import com.allahpan.common.util.MinioUtil;
import com.allahpan.domain.FileProcessMessage;
import com.allahpan.domain.FileProcessMessage.Stage;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.service.FileService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitHandler;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
@RabbitListener(queues = "#{T(com.allahpan.config.RabbitMqConfig).PROCESS_QUEUE}")
public class FileProcessReceiver {
    private static final Logger LOG = LoggerFactory.getLogger(FileProcessReceiver.class);
    private static final int MAX_RETRY = 3;

    @Autowired
    private ThumbnailGenerator thumbnailGenerator;
    @Autowired
    private TextExtractor textExtractor;
    @Autowired
    private EsIndexService esIndexService;
    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileProcessSender sender;

    @RabbitHandler
    public void handle(FileProcessMessage message) {
        File file = fileMapper.selectByPrimaryKey(message.getFileId());
        if (file == null || file.getDeleteTime() != null) {
            LOG.warn("文件不存在或已删除: {}", message.getFileId());
            return;
        }
        try {
            switch (message.getCurrentStage()) {
                case UPLOADED -> {
                    String thumbnailKey = thumbnailGenerator.generate(file);
                    if (thumbnailKey != null) {
                        file.setThumbnailKey(thumbnailKey);
                    }
                    file.setProcessStatus(1);
                    fileMapper.updateByPrimaryKeySelective(file);
                    if (needsTextExtraction(file)) {
                        sender.sendProcess(new FileProcessMessage(file.getId(), Stage.THUMBNAILED));
                    } else {
                        // 缩略图和文本提取都不需要，直接跳到索引
                        sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                    }
                }
                case THUMBNAILED -> {
                    String text = textExtractor.extract(file);
                    if (text != null && !text.isEmpty()) {
                        file.setOriginText(text);
                    }
                    file.setProcessStatus(2);
                    fileMapper.updateByPrimaryKeySelective(file);
                    sender.sendProcess(new FileProcessMessage(file.getId(), Stage.TEXT_EXTRACTED));
                }
                case TEXT_EXTRACTED -> {
                    esIndexService.index(file);
                    file.setProcessStatus(3);
                    fileMapper.updateByPrimaryKeySelective(file);
                    LOG.info("文件处理完成: {}", file.getFileName());
                }
                default -> LOG.warn("未知处理阶段: {}", message.getCurrentStage());
            }
        } catch (Exception e) {
            LOG.error("文件处理失败: {}, 阶段: {}, 重试: {}",
                    file.getFileName(), message.getCurrentStage(), message.getRetryCount(), e);
            if (message.getRetryCount() < MAX_RETRY) {
                // 递增延迟: 30s / 60s / 120s
                long delay = 30_000L * (1L << message.getRetryCount());
                message.setRetryCount(message.getRetryCount() + 1);
                message.setLastError(e.getMessage());
                sender.sendRetry(message, delay);
            } else {
                file.setProcessStatus(-1);
                fileMapper.updateByPrimaryKeySelective(file);
                LOG.error("文件处理彻底失败: {}", file.getFileName());
            }
        }
    }

    /**
     * 判断文件是否需要文本提取。
     * IMAGE 类型通过 OCR 提取，DOCUMENT 可通过 PDFBox 提取。
     */
    private boolean needsTextExtraction(File file) {
        if (file.getFileType() == null) return false;
        return "IMAGE".equals(file.getFileType()) || "DOCUMENT".equals(file.getFileType());
    }
}
```

- [ ] **Step 4.5: 创建 ThumbnailGenerator + TextExtractor + EsIndexService（骨架）**

```java
// allahpan-core/src/main/java/com/allahpan/component/ThumbnailGenerator.java
package com.allahpan.component;

import com.allahpan.common.util.MinioUtil;
import com.allahpan.mbg.model.File;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.util.UUID;

@Component
public class ThumbnailGenerator {

    @Autowired
    private MinioUtil minioUtil;

    public String generate(File file) {
        if ("IMAGE".equals(file.getFileType())) {
            return generateImageThumbnail(file);
        } else if ("DOCUMENT".equals(file.getFileType()) &&
                file.getContentType() != null &&
                file.getContentType().contains("pdf")) {
            return generatePdfThumbnail(file);
        }
        return null; // 视频或其他类型暂时跳过
    }

    private String generateImageThumbnail(File file) {
        try {
            // 从 MinIO 下载原始图片
            try (InputStream is = minioUtil.getClient().getObject(
                    io.minio.GetObjectArgs.builder()
                            .bucket(minioUtil.getBucketName())
                            .object(file.getStorageKey())
                            .build())) {
                BufferedImage original = ImageIO.read(is);
                if (original == null) return null;
                // 缩放到 300px 宽
                int thumbWidth = 300;
                int thumbHeight = (int) (original.getHeight() * (300.0 / original.getWidth()));
                BufferedImage thumb = new BufferedImage(thumbWidth, thumbHeight, BufferedImage.TYPE_INT_RGB);
                Graphics2D g = thumb.createGraphics();
                g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                        RenderingHints.VALUE_INTERPOLATION_BILINEAR);
                g.drawImage(original, 0, 0, thumbWidth, thumbHeight, null);
                g.dispose();
                // 上传到 MinIO 缩略图 bucket
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                ImageIO.write(thumb, "jpg", baos);
                String thumbnailKey = "thumb/" + UUID.randomUUID() + ".jpg";
                minioUtil.getClient().putObject(
                        io.minio.PutObjectArgs.builder()
                                .bucket(minioUtil.getThumbnailBucket())
                                .object(thumbnailKey)
                                .stream(new ByteArrayInputStream(baos.toByteArray()),
                                        baos.size(), -1)
                                .contentType("image/jpeg")
                                .build());
                return thumbnailKey;
            }
        } catch (Exception e) {
            throw new RuntimeException("生成缩略图失败", e);
        }
    }

    private String generatePdfThumbnail(File file) {
        // TODO: PDF 缩略图实现步骤 —— 依赖 Apache PDFBox
        // 1. 添加依赖: org.apache.pdfbox:pdfbox:3.0.4
        // 2. 从 MinIO 下载 PDF 字节: minioUtil.getClient().getObject(...)
        // 3. PDDocument.load(inputStream) 加载文档
        // 4. PDFRenderer.renderPage(0) 渲染首页为 BufferedImage
        // 5. 缩放到缩略图尺寸（同图片缩略图逻辑）并上传到 thumbnail bucket
        return null;
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/component/TextExtractor.java
package com.allahpan.component;

import com.allahpan.mbg.model.File;
import org.springframework.stereotype.Component;

@Component
public class TextExtractor {

    private final OllamaService ollamaService;

    public TextExtractor(OllamaService ollamaService) {
        this.ollamaService = ollamaService;
    }

    public String extract(File file) {
        if ("IMAGE".equals(file.getFileType())) {
            return ollamaService.ocr(file);
        }
        // TODO: PDF 文本提取实现步骤 —— 依赖 Apache PDFBox
        // 1. 添加依赖: org.apache.pdfbox:pdfbox:3.0.4
        // 2. 从 MinIO 下载 PDF 字节
        // 3. PDDocument.load(inputStream) 加载文档
        // 4. PDFTextStripper.getText(document) 提取全文
        // 5. 截取前 10000 字符存入 originText
        if ("DOCUMENT".equals(file.getFileType())) {
            // PDF 文本提取待实现
            return null;
        }
        return null;
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/component/EsIndexService.java
package com.allahpan.component;

import com.allahpan.mbg.model.File;

public interface EsIndexService {
    void index(File file);
    void delete(Long fileId);
}
```

```java
// allahpan-core/src/main/java/com/allahpan/component/EsIndexServiceImpl.java
package com.allahpan.component;

import com.allahpan.mbg.mapper.UserMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Component
public class EsIndexServiceImpl implements EsIndexService {

    @Autowired
    private UserMapper userMapper;

    private final RestTemplate restTemplate = new RestTemplate();
    private static final String SEARCH_SERVICE_URL = "http://localhost:8081/es-admin/files";

    @Override
    public void index(File file) {
        try {
            String uploaderName = "未知";
            if (file.getUploaderId() != null) {
                User user = userMapper.selectByPrimaryKey(file.getUploaderId());
                if (user != null) uploaderName = user.getNickname();
            }
            Map<String, Object> body = new HashMap<>();
            body.put("fileId", file.getId());
            body.put("fileName", file.getFileName() != null ? file.getFileName() : "");
            body.put("fileType", file.getFileType() != null ? file.getFileType() : "OTHER");
            body.put("filePath", file.getFilePath() != null ? file.getFilePath() : "");
            body.put("fileSize", file.getFileSize() != null ? file.getFileSize() : 0L);
            body.put("isFolder", file.getIsFolder() != null && file.getIsFolder() == 1);
            body.put("uploaderId", file.getUploaderId() != null ? file.getUploaderId() : 0L);
            body.put("uploaderName", uploaderName);
            body.put("originText", file.getOriginText() != null ? file.getOriginText() : "");
            body.put("createTime", file.getCreateTime() != null ? file.getCreateTime().toString() : "");
            restTemplate.postForEntity(SEARCH_SERVICE_URL + "/index", body, String.class);
        } catch (Exception e) {
            throw new RuntimeException("ES 索引失败", e);
        }
    }

    @Override
    public void delete(Long fileId) {
        try {
            restTemplate.delete(SEARCH_SERVICE_URL + "/" + fileId);
        } catch (Exception ignored) {}
    }
}
```

- [ ] **Step 4.6: 创建 OllamaService**

```java
// allahpan-core/src/main/java/com/allahpan/component/OllamaService.java
package com.allahpan.component;

import com.allahpan.common.util.MinioUtil;
import com.allahpan.mbg.model.File;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class OllamaService {

    @Value("${ollama.base-url}")
    private String baseUrl;
    @Value("${ollama.model}")
    private String model;

    @Autowired
    private MinioUtil minioUtil;

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 调用千问3-VL 对文件进行 OCR 文本提取
     * 从 MinIO 下载图片字节，base64 编码后发送到 Ollama vision API
     */
    public String ocr(File file) {
        try {
            // 从 MinIO 下载图片字节
            byte[] imageBytes;
            try (var is = minioUtil.getClient().getObject(
                    io.minio.GetObjectArgs.builder()
                            .bucket(minioUtil.getBucketName())
                            .object(file.getStorageKey())
                            .build())) {
                imageBytes = is.readAllBytes();
            }
            // Base64 编码
            String base64Image = Base64.getEncoder().encodeToString(imageBytes);

            // 构建 Ollama vision API 请求（chat 格式 + images 字段）
            Map<String, Object> request = new HashMap<>();
            request.put("model", model);
            request.put("stream", false);
            request.put("messages", List.of(
                Map.of("role", "user",
                    "content", "请提取这张图片中的所有文字内容，只返回文字，不要添加任何解释。",
                    "images", List.of(base64Image))
            ));

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> entity = new HttpEntity<>(request, headers);

            ResponseEntity<Map> response = restTemplate.exchange(
                    baseUrl + "/api/chat", HttpMethod.POST, entity, Map.class);

            if (response.getBody() != null && response.getBody().get("message") != null) {
                Map<String, Object> message = (Map<String, Object>) response.getBody().get("message");
                return (String) message.get("content");
            }
            return null;
        } catch (Exception e) {
            throw new RuntimeException("Ollama OCR 调用失败", e);
        }
    }
}
```

- [ ] **Step 4.7: confirmUpload 中集成发送消息**

在 `FileController.confirmUpload()` 末尾添加：

```java
// 发送文件处理消息
if (!"FOLDER".equals(file.getFileType())) {
    fileProcessSender.sendProcess(new FileProcessMessage(file.getId(), FileProcessMessage.Stage.UPLOADED));
}
```

- [ ] **Step 4.8: 垃圾站定时清理 — 超过 60 天物理删除**

```java
// allahpan-core/src/main/java/com/allahpan/config/SchedulingConfig.java
package com.allahpan.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

@Configuration
@EnableScheduling
public class SchedulingConfig {
}
```

```java
// allahpan-core/src/main/java/com/allahpan/task/TrashCleanupTask.java
package com.allahpan.task;

import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.FileService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.Date;
import java.util.List;

/**
 * 垃圾站定时清理：每天凌晨 3 点扫描，物理删除超过 60 天的垃圾文件
 */
@Component
public class TrashCleanupTask {

    private static final Logger log = LoggerFactory.getLogger(TrashCleanupTask.class);

    /** 垃圾站保留天数 */
    private static final int TRASH_RETENTION_DAYS = 60;

    @Autowired
    private FileMapper fileMapper;
    @Autowired
    private FileService fileService;

    @Scheduled(cron = "0 0 3 * * ?")  // 每天凌晨 3:00
    public void cleanExpiredTrash() {
        log.info("========== 垃圾站定时清理开始 ==========");

        // 计算 60 天前的时间
        LocalDateTime threshold = LocalDateTime.now().minusDays(TRASH_RETENTION_DAYS);
        Date thresholdDate = Date.from(threshold.atZone(ZoneId.systemDefault()).toInstant());

        // 查询 delete_time <= 60天前 的所有文件
        FileExample example = new FileExample();
        example.createCriteria().andDeleteTimeLessThanOrEqualTo(thresholdDate);
        List<File> expiredFiles = fileMapper.selectByExample(example);

        if (expiredFiles.isEmpty()) {
            log.info("没有过期垃圾文件需要清理");
            return;
        }

        int success = 0;
        int fail = 0;
        for (File file : expiredFiles) {
            try {
                fileService.permanentDelete(file.getId());
                success++;
            } catch (Exception e) {
                log.error("清理垃圾文件失败: fileId={}, fileName={}", file.getId(), file.getFileName(), e);
                fail++;
            }
        }

        log.info("垃圾站清理完成: 总计={}, 成功={}, 失败={}", expiredFiles.size(), success, fail);
        log.info("========== 垃圾站定时清理结束 ==========");
    }
}
```

---

### Task 5: 搜索模块 — allahpan-search 独立应用

**目标:** 创建 ES 搜索模块，实现文件索引、高亮搜索、聚合

- [ ] **Step 5.1: 创建 allahpan-search 模块 pom + Application**

```xml
<!-- allahpan-search/pom.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>com.allahpan</groupId>
        <artifactId>allahpan</artifactId>
        <version>1.0.0</version>
    </parent>
    <artifactId>allahpan-search</artifactId>

    <dependencies>
        <dependency>
            <groupId>com.allahpan</groupId>
            <artifactId>allahpan-common</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-elasticsearch</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

```java
// allahpan-search/src/main/java/com/allahpan/search/SearchApplication.java
package com.allahpan.search;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SearchApplication {
    public static void main(String[] args) {
        SpringApplication.run(SearchApplication.class, args);
    }
}
```

```yaml
# allahpan-search/src/main/resources/application.yml
server:
  port: 8081

spring:
  elasticsearch:
    uris: http://localhost:9200
```

- [ ] **Step 5.2: 创建 EsFile 文档**

```java
// allahpan-search/src/main/java/com/allahpan/search/domain/EsFile.java
package com.allahpan.search.domain;

import org.springframework.data.annotation.Id;
import org.springframework.data.elasticsearch.annotations.*;

import java.util.Date;

@Document(indexName = "allahpan_files")
@Setting(shards = 1, replicas = 0)
public class EsFile {

    @Id
    private Long fileId;

    @Field(type = FieldType.Text, analyzer = "ik_max_word")
    private String fileName;

    @Field(type = FieldType.Keyword)
    private String fileType;

    @Field(type = FieldType.Text, analyzer = "ik_max_word")
    private String originText;

    @Field(type = FieldType.Keyword)
    private String filePath;

    private Long uploaderId;

    @Field(type = FieldType.Keyword)
    private String uploaderName;

    private Long fileSize;
    private Boolean isFolder;

    @Field(type = FieldType.Date)
    private Date createTime;

    // getters / setters
    public Long getFileId() { return fileId; }
    public void setFileId(Long fileId) { this.fileId = fileId; }
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    public String getFileType() { return fileType; }
    public void setFileType(String fileType) { this.fileType = fileType; }
    public String getOriginText() { return originText; }
    public void setOriginText(String originText) { this.originText = originText; }
    public String getFilePath() { return filePath; }
    public void setFilePath(String filePath) { this.filePath = filePath; }
    public Long getUploaderId() { return uploaderId; }
    public void setUploaderId(Long uploaderId) { this.uploaderId = uploaderId; }
    public String getUploaderName() { return uploaderName; }
    public void setUploaderName(String uploaderName) { this.uploaderName = uploaderName; }
    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
    public Boolean getIsFolder() { return isFolder; }
    public void setIsFolder(Boolean folder) { isFolder = folder; }
    public Date getCreateTime() { return createTime; }
    public void setCreateTime(Date createTime) { this.createTime = createTime; }
}
```

- [ ] **Step 5.3: 创建 EsFileRepository + EsFileService + EsFileController**

```java
// allahpan-search/src/main/java/com/allahpan/search/repository/EsFileRepository.java
package com.allahpan.search.repository;

import com.allahpan.search.domain.EsFile;
import org.springframework.data.elasticsearch.repository.ElasticsearchRepository;

public interface EsFileRepository extends ElasticsearchRepository<EsFile, Long> {
}
```

```java
// allahpan-search/src/main/java/com/allahpan/search/service/EsFileService.java
package com.allahpan.search.service;

import java.util.Map;

public interface EsFileService {
    void index(Map<String, Object> fileData);
    void delete(Long fileId);
    Map<String, Object> search(String keyword, String fileType, int pageNum, int pageSize);
}
```

```java
// allahpan-search/src/main/java/com/allahpan/search/service/impl/EsFileServiceImpl.java
package com.allahpan.search.service.impl;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.SortOrder;
import co.elastic.clients.elasticsearch._types.query_dsl.TextQueryType;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.elasticsearch.core.search.HighlightField;
import co.elastic.clients.json.JsonData;
import com.allahpan.search.domain.EsFile;
import com.allahpan.search.repository.EsFileRepository;
import com.allahpan.search.service.EsFileService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.elasticsearch.client.elc.ElasticsearchTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class EsFileServiceImpl implements EsFileService {

    @Autowired
    private EsFileRepository repository;
    @Autowired
    private ElasticsearchTemplate esTemplate;

    @Override
    public void index(Map<String, Object> data) {
        EsFile f = new EsFile();
        f.setFileId(toLong(data.get("fileId")));
        f.setFileName((String) data.get("fileName"));
        f.setFileType((String) data.get("fileType"));
        f.setOriginText((String) data.getOrDefault("originText", ""));
        f.setFilePath((String) data.get("filePath"));
        f.setUploaderId(toLong(data.get("uploaderId")));
        f.setUploaderName((String) data.get("uploaderName"));
        f.setFileSize(toLong(data.get("fileSize")));
        f.setIsFolder((Boolean) data.getOrDefault("isFolder", false));
        f.setCreateTime(parseDate((String) data.get("createTime")));
        repository.save(f);
    }

    @Override
    public void delete(Long fileId) {
        repository.deleteById(fileId);
    }

    @Override
    public Map<String, Object> search(String keyword, String fileType, int pageNum, int pageSize) {
        var request = co.elastic.clients.elasticsearch.core.SearchRequest.of(s -> s
                .index("allahpan_files")
                .query(q -> q
                        .bool(b -> {
                            var builder = b.must(m -> m
                                    .multiMatch(mm -> mm
                                            .fields("fileName^10", "originText^5")
                                            .query(keyword)
                                            .type(TextQueryType.BestFields)));
                            if (fileType != null && !fileType.isEmpty()) {
                                builder.filter(f -> f.term(t -> t.field("fileType").value(fileType)));
                            }
                            return builder;
                        }))
                .highlight(h -> h
                        .fields("fileName", hf -> hf.numberOfFragments(0)
                                .preTags("<mark>").postTags("</mark>"))
                        .fields("originText", hf -> hf.numberOfFragments(3).fragmentSize(100)
                                .preTags("<mark>").postTags("</mark>")))
                .aggregations("fileTypes", a -> a
                        .terms(t -> t.field("fileType").size(10)))
                .from((pageNum - 1) * pageSize)
                .size(pageSize));

        SearchResponse<EsFile> response = esTemplate.search(request, EsFile.class);

        List<Map<String, Object>> list = response.hits().hits().stream()
                .map(hit -> {
                    Map<String, Object> item = new HashMap<>();
                    EsFile f = hit.content();
                    item.put("fileId", f.getFileId());
                    item.put("fileName", f.getFileName());
                    item.put("fileType", f.getFileType());
                    item.put("filePath", f.getFilePath());
                    item.put("uploaderName", f.getUploaderName());
                    item.put("fileSize", f.getFileSize());
                    item.put("createTime", f.getCreateTime());
                    // 高亮
                    if (hit.highlight() != null) {
                        if (hit.highlight().containsKey("fileName")) {
                            item.put("fileNameHighlight",
                                    String.join("", hit.highlight().get("fileName")));
                        }
                        if (hit.highlight().containsKey("originText")) {
                            item.put("contentSnippets", hit.highlight().get("originText"));
                        }
                    }
                    item.put("score", hit.score());
                    return item;
                }).toList();

        Map<String, Object> result = new HashMap<>();
        result.put("list", list);
        result.put("totalCount", response.hits().total() != null ? response.hits().total().value() : 0);

        // 聚合
        if (response.aggregations() != null && response.aggregations().containsKey("fileTypes")) {
            var buckets = response.aggregations().get("fileTypes").sterms().buckets().array();
            var aggList = buckets.stream()
                    .map(b -> Map.of("type", b.key().stringValue(), "count", b.docCount()))
                    .toList();
            result.put("aggregations", Map.of("fileTypes", aggList));
        }
        return result;
    }

    private Long toLong(Object v) {
        if (v instanceof Number n) return n.longValue();
        if (v instanceof String s) return Long.parseLong(s);
        return 0L;
    }

    private Date parseDate(String s) {
        if (s == null) return new Date();
        try {
            return Date.from(Instant.parse(s));
        } catch (Exception e) {
            try {
                return Date.from(LocalDateTime.parse(s,
                        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
                        .atZone(ZoneId.systemDefault()).toInstant());
            } catch (Exception e2) {
                return new Date();
            }
        }
    }
}
```

```java
// allahpan-search/src/main/java/com/allahpan/search/controller/EsFileController.java
package com.allahpan.search.controller;

import com.allahpan.search.service.EsFileService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/es-admin/files")
public class EsFileController {

    @Autowired
    private EsFileService esFileService;

    @PostMapping("/index")
    public Map<String, Object> index(@RequestBody Map<String, Object> fileData) {
        esFileService.index(fileData);
        return Map.of("success", true);
    }

    @DeleteMapping("/{fileId}")
    public Map<String, Object> delete(@PathVariable Long fileId) {
        esFileService.delete(fileId);
        return Map.of("success", true);
    }

    @GetMapping("/search")
    public Map<String, Object> search(
            @RequestParam String keyword,
            @RequestParam(required = false) String fileType,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return esFileService.search(keyword, fileType, pageNum, pageSize);
    }
}
```

- [ ] **Step 5.4: 创建 SearchController（core 搜索代理）**

```java
// allahpan-core/src/main/java/com/allahpan/controller/SearchController.java
package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.Map;

@Tag(name = "SearchController", description = "搜索管理")
@RestController
@RequestMapping("/api/search")
public class SearchController {

    private static final String SEARCH_SERVICE = "http://localhost:8081/es-admin/files/search";

    @GetMapping
    public CommonResult<Map<String, Object>> search(
            @RequestParam String keyword,
            @RequestParam(required = false) String fileType,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        RestTemplate rt = new RestTemplate();
        UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(SEARCH_SERVICE)
                .queryParam("keyword", keyword)
                .queryParam("pageNum", pageNum)
                .queryParam("pageSize", pageSize);
        if (fileType != null && !fileType.isEmpty()) {
            builder.queryParam("fileType", fileType);
        }
        Map<String, Object> result = rt.getForObject(builder.toUriString(), Map.class);
        return CommonResult.success(result);
    }
}
```

- [ ] **Step 5.5: 创建 ES 索引重建管理接口（全量重建索引——设计 6.5）**

```java
// allahpan-search/src/main/java/com/allahpan/search/controller/EsAdminController.java
package com.allahpan.search.controller;

import com.allahpan.search.service.EsFileService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * ES 索引管理接口
 */
@RestController
@RequestMapping("/es-admin")
public class EsAdminController {

    @Autowired
    private EsFileService esFileService;

    /**
     * 全量重建索引 —— 由 core 模块传入全量文件数据进行重新索引
     */
    @PostMapping("/rebuild")
    public Map<String, Object> rebuild(@RequestBody List<Map<String, Object>> files) {
        int success = 0;
        int fail = 0;
        for (Map<String, Object> fileData : files) {
            try {
                esFileService.index(fileData);
                success++;
            } catch (Exception e) {
                fail++;
            }
        }
        return Map.of("success", true, "total", files.size(),
                "indexed", success, "failed", fail);
    }
}
```

---

### Task 6: 收藏模块

**目标:** 收藏夹 CRUD

- [ ] **Step 6.1: 创建 FavoriteService + FavoriteController**

```java
// allahpan-core/src/main/java/com/allahpan/service/FavoriteService.java
package com.allahpan.service;

import com.allahpan.mbg.model.File;
import java.util.List;

public interface FavoriteService {
    void addFavorite(Long fileId);
    void removeFavorite(Long fileId);
    boolean isFavorited(Long fileId);
    List<File> listFavorites(int pageNum, int pageSize);
}
```

```java
// allahpan-core/src/main/java/com/allahpan/service/impl/FavoriteServiceImpl.java
package com.allahpan.service.impl;

import com.allahpan.bo.AdminUserDetails;
import com.allahpan.common.exception.Asserts;
import com.allahpan.mbg.mapper.FileFavoriteMapper;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileFavorite;
import com.allahpan.mbg.model.FileFavoriteExample;
import com.allahpan.service.FavoriteService;
import com.github.pagehelper.PageHelper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class FavoriteServiceImpl implements FavoriteService {
    @Autowired
    private FileFavoriteMapper favoriteMapper;
    @Autowired
    private FileMapper fileMapper;

    @Override
    public void addFavorite(Long fileId) {
        Long userId = getCurrentUserId();
        // 幂等：已收藏直接返回
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId).andFileIdEqualTo(fileId);
        if (!favoriteMapper.selectByExample(example).isEmpty()) return;

        FileFavorite fav = new FileFavorite();
        fav.setUserId(userId);
        fav.setFileId(fileId);
        fav.setCreateTime(new Date());
        favoriteMapper.insert(fav);
    }

    @Override
    public void removeFavorite(Long fileId) {
        Long userId = getCurrentUserId();
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId).andFileIdEqualTo(fileId);
        favoriteMapper.deleteByExample(example);
    }

    @Override
    public boolean isFavorited(Long fileId) {
        Long userId = getCurrentUserId();
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId).andFileIdEqualTo(fileId);
        return !favoriteMapper.selectByExample(example).isEmpty();
    }

    @Override
    public List<File> listFavorites(int pageNum, int pageSize) {
        Long userId = getCurrentUserId();
        FileFavoriteExample example = new FileFavoriteExample();
        example.createCriteria().andUserIdEqualTo(userId);
        example.setOrderByClause("create_time DESC");
        PageHelper.startPage(pageNum, pageSize);
        var favs = favoriteMapper.selectByExample(example);
        // 批量查文件详情
        List<Long> fileIds = favs.stream().map(FileFavorite::getFileId).toList();
        if (fileIds.isEmpty()) return List.of();
        return fileIds.stream()
                .map(fileMapper::selectByPrimaryKey)
                .filter(f -> f != null)
                .collect(Collectors.toList());
    }

    private Long getCurrentUserId() {
        var auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AdminUserDetails details) {
            return details.getUserId();
        }
        throw new RuntimeException("未登录");
    }
}
```

```java
// allahpan-core/src/main/java/com/allahpan/controller/FavoriteController.java
package com.allahpan.controller;

import com.allahpan.common.api.CommonResult;
import com.allahpan.service.FavoriteService;
import io.swagger.v3.oas.annotations.Operation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/favorite")
public class FavoriteController {

    @Autowired
    private FavoriteService favoriteService;

    @Operation(summary = "收藏文件")
    @PostMapping("/{fileId}")
    public CommonResult<Void> addFavorite(@PathVariable Long fileId) {
        favoriteService.addFavorite(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "取消收藏")
    @DeleteMapping("/{fileId}")
    public CommonResult<Void> removeFavorite(@PathVariable Long fileId) {
        favoriteService.removeFavorite(fileId);
        return CommonResult.success(null);
    }

    @Operation(summary = "是否已收藏")
    @GetMapping("/check/{fileId}")
    public CommonResult<Boolean> isFavorited(@PathVariable Long fileId) {
        return CommonResult.success(favoriteService.isFavorited(fileId));
    }

    @Operation(summary = "收藏列表")
    @GetMapping("/list")
    public CommonResult<?> listFavorites(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        return CommonResult.success(favoriteService.listFavorites(pageNum, pageSize));
    }
}
```

---

### Task 7: 前端（Vue 3 + Element Plus）— 以函数为单位的开发清单

**目标:** 不写具体代码，列出每个文件里的每个函数/变量及其职责。方便你自己手打每一行代码，边写边理解。

---

#### 7.1 项目初始化

- [ ] **初始化 Vue 3 + Vite 项目**

```bash
# 在项目根目录下执行
npm create vite@latest allahpan-web -- --template vue
cd allahpan-web
npm install
npm install vue-router@4 pinia element-plus @element-plus/icons-vue axios spark-md5
npm install -D @vitejs/plugin-vue sass-embedded
```

- [ ] **配置 vite.config.js**

| 配置项 | 值 | 说明 |
|--------|----|------|
| `plugins` | `[vue()]` | Vue 3 SFC 编译 |
| `server.port` | `5173` | 开发服务器端口 |
| `server.proxy./api` | `http://localhost:8088` | 代理到后端 core |
| `resolve.alias.@` | `./src` | 路径别名 |

---

#### 7.2 目录结构

```
allahpan-web/src/
├── main.js                           # 入口：注册 Element Plus、Router、Pinia
├── App.vue                           # 根组件：<router-view />
├── router/index.js                   # 路由配置
├── api/
│   ├── index.js                      # Axios 实例 + 拦截器
│   ├── auth.js                       # 认证 API
│   ├── file.js                       # 文件 API
│   ├── search.js                     # 搜索 API
│   └── favorite.js                   # 收藏 API
├── stores/
│   ├── user.js                       # 用户状态（Pinia）
│   └── file.js                       # 文件浏览状态（Pinia）
├── utils/
│   ├── md5.js                        # 浏览器端 MD5 计算
│   └── format.js                     # 文件大小/日期格式化
├── views/
│   ├── Login.vue                     # 登录页（双通道）
│   ├── SetPassword.vue               # 首次登录设密码
│   ├── FileBrowser.vue               # 文件浏览器（主页）
│   ├── Favorites.vue                 # 收藏夹
│   └── Search.vue                    # 搜索结果页
├── components/
│   ├── layout/
│   │   ├── AppLayout.vue             # 主布局容器
│   │   ├── AppHeader.vue             # 顶部栏
│   │   └── AppSidebar.vue            # 侧边导航
│   ├── file/
│   │   ├── FileToolbar.vue           # 工具栏
│   │   ├── FileGridView.vue          # 网格视图
│   │   ├── FileListView.vue          # 列表视图
│   │   ├── FileCard.vue              # 网格卡片
│   │   ├── FileRow.vue               # 列表行
│   │   ├── FileUploadDialog.vue      # 上传弹窗（含拖拽）
│   │   ├── FolderCreateDialog.vue    # 新建文件夹弹窗
│   │   ├── BreadcrumbNav.vue         # 面包屑导航
│   │   ├── FileContextMenu.vue       # 右键菜单
│   │   └── FilePreviewDialog.vue     # 文件预览弹窗
│   ├── search/
│   │   ├── SearchBar.vue             # 全局搜索输入框
│   │   └── SearchResultItem.vue      # 搜索结果条目（高亮）
│   └── common/
│       ├── FileIcon.vue              # 文件类型图标
│       ├── ProcessBadge.vue          # 处理状态标签
│       └── EmptyState.vue            # 空状态占位图
├── styles/
│   └── global.css                    # 全局样式变量、Element Plus 覆盖
└── assets/                           # 静态资源（logo、空状态图等）
```

---

#### 7.3 路由配置 — `src/router/index.js`

| 路由路径 | 页面组件 | 是否需要登录 | 说明 |
|---------|---------|------------|------|
| `/login` | `Login.vue` | ❌ | 登录页，已登录则重定向到 `/files` |
| `/set-password` | `SetPassword.vue` | ✅ | 首次登录强制设密码，`hasPassword=true` 则重定向 |
| `/files` | `FileBrowser.vue` | ✅ | 主页面，文件浏览 |
| `/favorites` | `Favorites.vue` | ✅ | 收藏夹 |
| `/search` | `Search.vue` | ✅ | 搜索结果（query 参数 `?q=xxx`） |
| `/` | — | — | 重定向到 `/files` |

**路由守卫 `beforeEach` 逻辑**：
- 目标路由需要登录 + 无 token → 跳转 `/login`
- 已登录 + 访问 `/login` → 跳转 `/files`
- 已登录 + `hasPassword=false` + 访问非 `/set-password` → 跳转 `/set-password`

---

#### 7.4 API 层

##### `src/api/index.js` — Axios 实例

| 导出 | 类型 | 说明 |
|------|------|------|
| `api` | `AxiosInstance` | `baseURL=/api`, `timeout=30000` |

**拦截器函数**：

| 函数 | 位置 | 逻辑 |
|------|------|------|
| `requestInterceptor(config)` | request | 从 `localStorage` 取 token → 设 `Authorization: Bearer xxx` 头 |
| `responseInterceptor(response)` | response | 返回 `response.data`（去壳，直接拿 `CommonResult` 的 body） |
| `responseErrorInterceptor(error)` | response error | 如果 `error.response.data.code === 401` → 清 token → 跳转 `/login`；否则 `reject` |

##### `src/api/auth.js` — 认证 API

| 函数 | HTTP | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `sendCode(phone)` | `POST /api/auth/send-code` | `{phone}` | `CommonResult<null>` | 发送验证码 |
| `loginByCode(phone, code)` | `POST /api/auth/login-by-code` | `{phone, code}` | `CommonResult<{token, tokenHead, userId, phone, hasPassword, firstLogin}>` | 验证码登录 |
| `loginByPassword(phone, password)` | `POST /api/auth/login-by-password` | `{phone, password}` | `CommonResult<{token, tokenHead, userId, phone, hasPassword}>` | 密码登录 |
| `setPassword(newPassword)` | `POST /api/user/set-password` | `{newPassword}` | `CommonResult<{token, hasPassword}>` | 首次设置密码 |
| `getMe()` | `GET /api/user/me` | — | `CommonResult<{id,phone,nickname,avatarUrl,...}>` | 获取当前用户信息 |

##### `src/api/file.js` — 文件 API

| 函数 | HTTP | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `preUpload(md5, fileName, parentId)` | `POST /api/file/pre-upload` | `{md5, fileName, parentId}` | `CommonResult<{instant, storageKey, preSignedUrl, fileId}>` | 预上传（秒传检测） |
| `confirmUpload(data)` | `POST /api/file/confirm-upload` | `{storageKey, fileName, parentId, md5, fileSize, contentType}` | `CommonResult<File>` | 确认上传 |
| `uploadToMinio(preSignedUrl, file)` | — (直接 PUT 到 MinIO) | `PUT preSignedUrl` body=file blob | HTTP 200/206 | 前端直传文件到 MinIO |
| `listFiles(parentId)` | `GET /api/file/list?parentId=0` | `parentId` | `CommonResult<File[]>` | 目录文件列表 |
| `createFolder(folderName, parentId)` | `POST /api/file/create-folder` | `{folderName, parentId}` | `CommonResult<File>` | 新建文件夹 |
| `getDirectoryTree(folderId)` | `GET /api/file/tree/{folderId}` | `folderId` | `CommonResult<File[]>` | 面包屑路径（从根到当前目录） |
| `deleteFile(fileId)` | `DELETE /api/file/{fileId}` | `fileId` | `CommonResult<null>` | 软删除文件 |
| `getFileDetail(fileId)` | `GET /api/file/{fileId}` | `fileId` | `CommonResult<File>` | 文件详情（含下载 URL） |

##### `src/api/search.js` — 搜索 API

| 函数 | HTTP | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `search(keyword, fileType, pageNum, pageSize)` | `GET /api/search` | `keyword, fileType?, pageNum, pageSize` | `CommonResult<{list, totalCount, aggregations}>` | 搜索文件 |

##### `src/api/favorite.js` — 收藏 API

| 函数 | HTTP | 参数 | 返回值 | 说明 |
|------|------|------|--------|------|
| `addFavorite(fileId)` | `POST /api/favorite/{fileId}` | `fileId` | `CommonResult<null>` | 收藏 |
| `removeFavorite(fileId)` | `DELETE /api/favorite/{fileId}` | `fileId` | `CommonResult<null>` | 取消收藏 |
| `checkFavorite(fileId)` | `GET /api/favorite/check/{fileId}` | `fileId` | `CommonResult<boolean>` | 是否已收藏 |
| `listFavorites(pageNum, pageSize)` | `GET /api/favorite/list` | `pageNum, pageSize` | `CommonResult<File[]>` | 收藏列表 |

---

#### 7.5 状态管理（Pinia Stores）

##### `src/stores/user.js` — 用户状态

| 导出 | 类型 | 说明 |
|------|------|------|
| `useUserStore` | `DefineStore` | Pinia store |

**State**：

| 变量 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `token` | `string\|null` | `localStorage.getItem('token')` | JWT token |
| `userInfo` | `object\|null` | `null` | 当前用户信息 `{id, phone, nickname, avatarUrl, ...}` |
| `hasPassword` | `boolean` | `true` | 是否已设置密码（`false` 则强制跳转设密码页） |

**Actions**：

| 函数 | 参数 | 逻辑 |
|------|------|------|
| `setToken(token)` | `token: string` | 存入 state + `localStorage.setItem('token', token)` |
| `clearToken()` | — | 清空 state + `localStorage.removeItem('token')` |
| `loginByCode(phone, code)` | `phone, code` | 调 `authApi.loginByCode()` → `setToken()` + 更新 `userInfo` + `hasPassword` |
| `loginByPassword(phone, password)` | `phone, password` | 调 `authApi.loginByPassword()` → `setToken()` + 更新 `userInfo` + `hasPassword` |
| `setPasswordAfterLogin(newPassword)` | `newPassword` | 调 `authApi.setPassword()` → 更新 token + `hasPassword=true` |
| `fetchUserInfo()` | — | 调 `authApi.getMe()` → 更新 `userInfo` |
| `logout()` | — | `clearToken()` → `userInfo=null` → 跳转 `/login` |

**Getters**：

| 函数 | 返回值 | 说明 |
|------|--------|------|
| `isLoggedIn` | `boolean` | `!!token` |
| `displayName` | `string` | `userInfo.nickname` 或 `userInfo.phone`（兜底） |

##### `src/stores/file.js` — 文件浏览状态

**State**：

| 变量 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `currentFolderId` | `number` | `0` | 当前浏览的文件夹 ID（0=根目录） |
| `files` | `File[]` | `[]` | 当前目录下的文件列表 |
| `breadcrumb` | `File[]` | `[]` | 从根到当前的路径链 |
| `viewMode` | `'grid'\|'list'` | `'grid'` | 视图模式 |
| `loading` | `boolean` | `false` | 加载中 |
| `uploadQueue` | `UploadTask[]` | `[]` | 上传队列 |
| `selectedFileIds` | `Set<number>` | `new Set()` | 多选的文件 ID 集合 |

**Actions**：

| 函数 | 参数 | 逻辑 |
|------|------|------|
| `loadFiles()` | — | `fileApi.listFiles(currentFolderId)` → 更新 `files` |
| `navigateTo(folderId)` | `folderId: number` | 更新 `currentFolderId` → `loadFiles()` + `loadBreadcrumb()` |
| `navigateUp()` | — | 取 `breadcrumb` 倒数第二个的 id → `navigateTo()` |
| `loadBreadcrumb()` | — | `fileApi.getDirectoryTree(currentFolderId)` → 更新 `breadcrumb` |
| `toggleViewMode()` | — | 切换 `grid` / `list` |
| `selectFile(fileId)` | `fileId: number` | 多选用——`toggle/add/remove` |
| `clearSelection()` | — | `selectedFileIds.clear()` |
| `addUploadTask(file, parentId)` | `file: File, parentId` | 推入 `uploadQueue` → 依次执行上传流程 |
| `removeUploadTask(taskId)` | `taskId: string` | 从队列移除（取消上传） |
| `refreshUploadProgress(taskId, percent)` | `taskId, percent` | 更新某任务的进度 |

**UploadTask 对象结构**：
```
{
  id: string (UUID),         // 任务唯一 ID
  fileName: string,           // 文件名
  fileSize: number,           // 文件大小
  status: 'pending'|'hashing'|'uploading'|'confirming'|'done'|'error',
  progress: number (0-100),   // 上传进度
  errorMessage: string|null,  // 错误信息
  file: File                  // 原始浏览器 File 对象
}
```

---

#### 7.6 工具函数

##### `src/utils/md5.js`

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `computeMd5(file)` | `file: File` | `Promise<string>` | 用 SparkMD5 分片计算文件 MD5（大文件不阻塞主线程） |
| `computeMd5Sync(file)` | `file: File` | `Promise<string>` | 小文件（<10MB）同步计算 |

##### `src/utils/format.js`

| 函数 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `formatFileSize(bytes)` | `bytes: number` | `string` | `1024 → "1 KB"`, `1048576 → "1 MB"`, `1073741824 → "1 GB"` |
| `formatDate(dateStr)` | `dateStr: string\|Date` | `string` | `2026-06-06 15:30` 格式 |
| `formatRelativeTime(dateStr)` | `dateStr: string\|Date` | `string` | 刚刚/5分钟前/3小时前/2天前/2026-03-15 |
| `getFileExtension(fileName)` | `fileName: string` | `string` | `.pdf` → `pdf` |
| `getFileTypeLabel(fileType)` | `fileType: string` | `string` | `IMAGE`→图片, `DOCUMENT`→文档, `VIDEO`→视频, `FOLDER`→文件夹, `OTHER`→其他 |
| `getFileTypeColor(fileType)` | `fileType: string` | `string` | 每种类型对应一种 Element Plus 颜色值 |
| `isImage(file)` | `file: File对象` | `boolean` | `contentType.startsWith('image/')` |
| `isPdf(file)` | `file: File对象` | `boolean` | `contentType.includes('pdf')` |
| `isVideo(file)` | `file: File对象` | `boolean` | `contentType.startsWith('video/')` |

---

#### 7.7 页面组件

##### `src/views/Login.vue` — 登录页

**UI 布局**：居中卡片 → 手机号输入框 + 登录方式切换 Tab（验证码/密码）

**Data / State**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `phone` | `string` | 手机号输入 |
| `code` | `string` | 验证码输入 |
| `password` | `string` | 密码输入 |
| `loginMode` | `'code'\|'password'` | 当前登录方式 |
| `codeSending` | `boolean` | 发送验证码按钮 loading |
| `codeCountdown` | `number` | 验证码倒计时（30 秒） |
| `loginLoading` | `boolean` | 登录按钮 loading |

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `validatePhone()` | 输入校验 | `phone` 非空 + 11 位数字格式 |
| `sendCode()` | 点击"发送验证码" | 校验 → `authApi.sendCode(phone)` → 开始 `codeCountdown` 倒计时（30s） |
| `doLoginByCode()` | 点击登录（验证码模式） | 校验 → `userStore.loginByCode(phone, code)` → 成功跳转 |
| `doLoginByPassword()` | 点击登录（密码模式） | 校验 → `userStore.loginByPassword(phone, password)` → 成功跳转 |
| `switchMode(mode)` | 点击 Tab | 切换 `loginMode` |
| `handleAfterLogin(resp)` | 登录成功后回调 | 如果 `firstLogin` → 跳转 `/set-password`；否则 → 跳转 `/files` |

**登录成功后的跳转逻辑**（写在一个公共函数里，`SetPassword.vue` 也会用到）：
```
if (resp.firstLogin || !resp.hasPassword) → router.push('/set-password')
else → router.push(redirect || '/files')
```

##### `src/views/SetPassword.vue` — 设置密码页

**UI 布局**：居中卡片 → "首次登录，请设置密码" → 密码输入框 + 确认密码输入框 + 提交按钮

**Data**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `newPassword` | `string` | 新密码 |
| `confirmPassword` | `string` | 确认密码 |
| `loading` | `boolean` | 提交 loading |

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `validate()` | 提交前 | 非空 + 长度 ≥ 6 + `newPassword === confirmPassword` |
| `submit()` | 点击"确认设置" | 校验 → `userStore.setPasswordAfterLogin(newPassword)` → 跳转 `/files` |

##### `src/views/FileBrowser.vue` — 文件浏览器（主页面）

这是整个前端最核心的页面。包裹在 `AppLayout` 内。

**UI 布局**：
```
┌──────────────────────────────────────────┐
│  AppHeader                               │
├──────────┬───────────────────────────────┤
│AppSidebar│  BreadcrumbNav                 │
│  - 全部   │  FileToolbar                  │
│  - 收藏   │  ┌──────────┬──────────┐     │
│  - ...    │  │ FileCard │ FileCard │ ...  │  (Grid 模式)
│           │  └──────────┴──────────┘     │
│           │  或  FileListView (List 模式) │
└──────────┴───────────────────────────────┘
```

**Data**：
（全部从 `useFileStore` 取，不重复声明）

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onMounted()` | 页面加载 | `fileStore.loadFiles()` + `fileStore.loadBreadcrumb()` |
| `onFileClick(file)` | 点击文件 | 文件夹 → `fileStore.navigateTo(file.id)`；文件 → 打开 `FilePreviewDialog` |
| `onFolderDblClick(file)` | 双击文件夹 | `fileStore.navigateTo(file.id)` |
| `onBreadcrumbClick(folderId)` | 点击面包屑 | `fileStore.navigateTo(folderId)` |
| `onUploadComplete()` | 上传弹窗关闭 | `fileStore.loadFiles()` 刷新列表 |
| `showCreateFolderDialog()` | 点击"新建文件夹" | 打开 `FolderCreateDialog` |
| `showDeleteConfirm(file)` | 右键/按钮删除 | `ElMessageBox.confirm` → `fileApi.deleteFile(file.id)` → 刷新 |
| `handleFavoriteToggle(file)` | 点击收藏按钮 | `favoriteApi.check(file.id)` → 已收藏则取消，未收藏则添加 |
| `onContextMenu(event, file)` | 右键文件 | 打开 `FileContextMenu` 在鼠标位置 |
| `onDragOver(event)` | dragover 事件 | `event.preventDefault()` 允许 drop |
| `onDrop(event)` | drop 事件 | 取 `event.dataTransfer.files` → 打开上传弹窗 |

##### `src/views/Favorites.vue` — 收藏夹页

和 `FileBrowser.vue` 类似但不支持文件夹导航（收藏的是文件，不是目录）

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onMounted()` | 页面加载 | `favoriteApi.listFavorites(pageNum, pageSize)` |
| `loadMore()` | 滚动到底 | 加载下一页 |
| `onRemoveFavorite(fileId)` | 点击取消收藏 | `favoriteApi.removeFavorite(fileId)` → 从列表剔除 |

##### `src/views/Search.vue` — 搜索结果页

**Data**：

| 变量 | 类型 | 说明 |
|------|------|------|
| `keyword` | `string` | 搜索关键词（从 `route.query.q` 取） |
| `results` | `SearchResultItem[]` | 搜索结果 |
| `totalCount` | `number` | 总条数 |
| `aggregations` | `object` | 文件类型聚合 `{DOCUMENT: 30, IMAGE: 12, ...}` |
| `activeTypeFilter` | `string\|null` | 当前选中的类型过滤（null=全部） |
| `loading` | `boolean` | 搜索中 |

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onMounted()` | 页面加载 | 取 `route.query.q` → `doSearch()` |
| `doSearch()` | 搜索/翻页/切换类型 | `searchApi.search(keyword, activeTypeFilter, pageNum, pageSize)` → 更新 results |
| `onTypeFilterClick(type)` | 点击聚合标签 | 更新 `activeTypeFilter` → `doSearch()` |
| `onResultClick(item)` | 点击结果 | 跳转到 `FileBrowser` 并定位到该文件所在目录 |
| `onPageChange(pageNum)` | 翻页 | `doSearch()` |
| `watch(() => route.query.q)` | URL 参数变化 | 更新 `keyword` → `doSearch()` |

---

#### 7.8 布局组件

##### `src/components/layout/AppLayout.vue`

**UI**：`<AppHeader />` + `<el-container>` 内放 `<AppSidebar />` + `<router-view />`

**Slots**：`default` 为 `<router-view />` 内容区

##### `src/components/layout/AppHeader.vue`

**UI**：左侧 Logo（"AllahPan"） + 中间 `<SearchBar />` + 右侧用户头像/下拉菜单

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onSearch(keyword)` | SearchBar emit | `router.push({path: '/search', query: {q: keyword}})` |
| `onLogout()` | 下拉菜单点击 | `userStore.logout()` |
| `goToFavorites()` | 下拉菜单点击 | `router.push('/favorites')` |

##### `src/components/layout/AppSidebar.vue`

**UI**：导航菜单（"全部文件"→`/files`， "收藏夹"→`/favorites`）+ 存储用量显示

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onMenuSelect(index)` | 菜单项点击 | `router.push(index)` |

---

#### 7.9 文件相关组件

##### `src/components/file/FileToolbar.vue`

**Props**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `viewMode` | `'grid'\|'list'` | 当前视图 |
| `selectedCount` | `number` | 已选文件数 |

**Emits**：

| 事件 | 参数 | 说明 |
|------|------|------|
| `upload` | — | 触发上传 |
| `create-folder` | — | 新建文件夹 |
| `toggle-view` | — | 切换视图 |
| `delete-selected` | — | 批量删除 |
| `refresh` | — | 刷新列表 |

**Methods**：

| 函数 | 说明 |
|------|------|
| `onUploadClick()` | `emit('upload')` |
| `onCreateFolderClick()` | `emit('create-folder')` |
| `onToggleView()` | `emit('toggle-view')` |
| `onDeleteSelected()` | `emit('delete-selected')` |

##### `src/components/file/FileGridView.vue`

**Props**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `files` | `File[]` | 文件列表 |
| `selectedIds` | `Set<number>` | 已选 ID 集合 |

**Emits**：

| 事件 | 参数 | 说明 |
|------|------|------|
| `file-click` | `file: File` | 单击文件 |
| `file-dblclick` | `file: File` | 双击文件 |
| `favorite-toggle` | `file: File` | 切换收藏 |
| `context-menu` | `{event, file}` | 右键事件 |
| `selection-change` | `Set<number>` | 选中变化 |

**Methods**：

| 函数 | 说明 |
|------|------|
| `onCardClick(file)` | 如果 `isFolder` → `emit('file-click')`；否则 toggle 选中 |
| `onCardDblClick(file)` | `emit('file-dblclick')` |
| `onCardContextMenu(event, file)` | `event.preventDefault()` → `emit('context-menu', {event, file})` |
| `isSelected(fileId)` | 检查是否在 `selectedIds` 中 |

##### `src/components/file/FileListView.vue`

和 `FileGridView` 相同的 Props/Emits/Methods，只是渲染为 `<el-table>` 表格行。

##### `src/components/file/FileCard.vue`

**Props**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `file` | `File` | 文件对象 |
| `selected` | `boolean` | 是否选中 |
| `favorited` | `boolean` | 是否已收藏 |

**UI 结构**：
```
┌─────────────┐
│  [缩略图/图标] │  ← FileIcon 组件（有缩略图显示缩略图，没有显示类型图标）
│  ProcessBadge │  ← 处理中/失败状态标签
│  文件名.md    │  ← 截断溢出显示省略号
│  收藏⭐/取消  │
└─────────────┘
```

**Methods**：

| 函数 | 说明 |
|------|------|
| `getThumbnailUrl(file)` | 有 `thumbnailKey` 返回缩略图 URL，没有则返回 null |
| `getFileIcon(file)` | 根据 `fileType` 返回对应的 Element Plus 图标名 |

##### `src/components/file/FileRow.vue`

表格行版本，列：图标 | 文件名 | 大小 | 类型 | 上传者 | 上传时间 | 操作（收藏/删除）

##### `src/components/file/FileUploadDialog.vue`

**UI**：上传区域（`<el-upload>` 的 drag 模式）+ 文件队列列表 + 进度条

**Props**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `visible` | `boolean` | 弹窗可见 |
| `parentId` | `number` | 上传到的目标文件夹 |

**Emits**：

| 事件 | 参数 | 说明 |
|------|------|------|
| `close` | — | 关闭弹窗 |
| `upload-complete` | — | 上传完成 |

**Methods**：

| 函数 | 触发时机 | 逻辑 |
|------|---------|------|
| `onBeforeUpload(file)` | 文件加入队列前 | 返回 `false`（手动控制上传）→ 将文件加入 `fileStore.uploadQueue` |
| `processUploadTask(task)` | 队列处理 | ① `computeMd5(file)` → ② `fileApi.preUpload(md5, name, parentId)` → ③ 如果 `instant=true` 秒传完成 → ④ 否则 `PUT preSignedUrl` 上传文件 → ⑤ `fileApi.confirmUpload(...)` → ⑥ 更新 `task.progress` |
| `onDragOver(event)` | 拖拽悬停 | 高亮放置区域 |
| `onDrop(event)` | 文件拖入 | 提取 `event.dataTransfer.files` → 加入队列 |
| `removeTask(taskId)` | 点击取消 | 从队列移除 + 如果正在上传则 `xhr.abort()` |
| `retryTask(taskId)` | 点击重试 | 重新执行 `processUploadTask` |
| `handleClose()` | 关闭弹窗 | 如有正在上传的任务 → 提示确认 |

**上传进度追踪**：
- `PUT` 请求用原生 `XMLHttpRequest`（不用 axios），因为需要 `xhr.upload.onprogress` 事件
- 每 100ms 更新 `task.progress = (loaded/total)*100`

##### `src/components/file/FolderCreateDialog.vue`

**UI**：简单弹窗 → 文件夹名称输入框 + 确定/取消

**Props**：`visible: boolean`, `parentId: number`
**Emits**：`close`, `created`

**Methods**：

| 函数 | 逻辑 |
|------|------|
| `onSubmit()` | 校验非空 → `fileApi.createFolder(folderName, parentId)` → `emit('created')` |

##### `src/components/file/BreadcrumbNav.vue`

**UI**：`<el-breadcrumb>` → "根目录 / 工作 / 项目"（可点击跳转）

**Props**：`breadcrumb: File[]`（从 store 取）

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onItemClick(folderId)` | 点击某级 | `emit('navigate', folderId)` |

##### `src/components/file/FileContextMenu.vue`

**UI**：右键弹出的 `<ul>` 菜单列表

**Props**：`visible: boolean`, `position: {x, y}`, `file: File`

**Emits**：`close`

**菜单项**：

| 菜单项 | 条件 | 操作 |
|--------|------|------|
| 打开 | 文件 | `emit('preview')` |
| 进入 | 文件夹 | `emit('navigate')` |
| 下载 | 非文件夹 | `window.open(downloadUrl)` |
| 收藏/取消收藏 | — | `emit('favorite-toggle')` |
| 删除 | — | `emit('delete')` |

**Methods**：

| 函数 | 说明 |
|------|------|
| `onClickOutside()` | 点击菜单外部 → `emit('close')`（用 `document.addEventListener('click')`） |

##### `src/components/file/FilePreviewDialog.vue`

**UI**：全屏/大弹窗预览文件

**Props**：`visible: boolean`, `file: File`

**Emits**：`close`

**Methods**：

| 函数 | 逻辑 |
|------|------|
| `getPreviewContent()` | `IMAGE` → `<img>` 直接渲染缩略图/原图；`PDF` → `<iframe src=downloadUrl>`；`VIDEO` → `<video src=downloadUrl>`；`OTHER` → 显示文件信息（无预览） |
| `getDownloadUrl()` | 调 `fileApi.getFileDetail(file.id)` 取下载 URL |

---

#### 7.10 搜索组件

##### `src/components/search/SearchBar.vue`

**UI**：`<el-input>` + 搜索图标 + 支持回车触发搜索

**Methods**：

| 函数 | 触发 | 逻辑 |
|------|------|------|
| `onSearch()` | 回车/点击搜索图标 | `router.push({path: '/search', query: {q: keyword}})` |
| `onInput(value)` | 输入变化 | 可选：显示搜索历史下拉（localStorage 存最近 5 条） |

##### `src/components/search/SearchResultItem.vue`

**Props**：`item: SearchResult`

**SearchResult 结构**：
```
{
  fileId, fileName, fileType, filePath,
  uploaderName, fileSize, createTime, score,
  fileNameHighlight: string,        // 含 <mark> 标签
  contentSnippets: string[]         // 含 <mark> 标签（originText 匹配片段）
}
```

**UI**：
```
┌──────────────────────────────────────────────┐
│ 📄 fileNameHighlight (v-html)                │
│ /工作/项目/...                                 │
│ "这是一张办公用品<mark>发票</mark>，总金额..." │
│ 2024-03-15 · 张三 · 2.3 MB                    │
└──────────────────────────────────────────────┘
```

**Methods**：

| 函数 | 逻辑 |
|------|------|
| `onItemClick()` | `router.push` 到 FileBrowser 并尝试定位到 `filePath` |

---

#### 7.11 通用组件

##### `src/components/common/FileIcon.vue`

**Props**：`fileType: string`, `thumbnailUrl?: string`

**渲染逻辑**：
- 如果有 `thumbnailUrl` → 显示 `<img>` 标签（缩略图）
- `FOLDER` → `<el-icon><Folder /></el-icon>` 蓝色文件夹图标
- `IMAGE` → `<el-icon><Picture /></el-icon>`
- `VIDEO` → `<el-icon><VideoCamera /></el-icon>`
- `DOCUMENT` → `<el-icon><Document /></el-icon>`
- `OTHER` → `<el-icon><Files /></el-icon>`

##### `src/components/common/ProcessBadge.vue`

**Props**：`processStatus: number`

**渲染逻辑**：
- `0` → 橙色 `<el-tag>` "待处理"
- `1` → 蓝色 `"缩略图完成"`
- `2` → 紫色 `"文本提取中"`
- `3` → 不显示（已完成）
- `-1` → 红色 `"处理失败"`

##### `src/components/common/EmptyState.vue`

**Props**：`message?: string`, `icon?: string`

**UI**：居中空状态插图 + "暂无文件"（或其他 message）+ 可选的 action 插槽

---

#### 7.12 全局入口

##### `src/main.js`

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './assets/styles/global.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.mount('#app')
```

##### `src/App.vue`

```vue
<template>
  <router-view />
</template>
```

---

#### 7.13 开发顺序建议

| 序号 | 文件 | 原因 |
|------|------|------|
| 1 | `main.js` + `App.vue` + `router/index.js` | 骨架跑通 |
| 2 | `api/index.js` + `api/auth.js` | 登录依赖 API |
| 3 | `stores/user.js` | 登录依赖状态 |
| 4 | `views/Login.vue` | 用 mock 数据先测试 UI |
| 5 | `views/SetPassword.vue` | 登录流程闭环 |
| 6 | `components/layout/*` | 主布局 |
| 7 | `api/file.js` + `stores/file.js` | 文件数据层 |
| 8 | `components/file/BreadcrumbNav.vue` | 导航 |
| 9 | `components/common/FileIcon.vue` | 基础组件 |
| 10 | `components/file/FileCard.vue` + `FileGridView.vue` | 文件展示 |
| 11 | `components/file/FileToolbar.vue` | 工具栏 |
| 12 | `views/FileBrowser.vue` | 拼装主页面 |
| 13 | `components/file/FolderCreateDialog.vue` | 新建文件夹 |
| 14 | `components/file/FileUploadDialog.vue` + `utils/md5.js` | 上传流程 |
| 15 | `components/file/FileContextMenu.vue` | 右键菜单 |
| 16 | `components/file/FilePreviewDialog.vue` | 文件预览 |
| 17 | `components/file/FileListView.vue` + `FileRow.vue` | 列表视图 |
| 18 | `api/search.js` + `utils/format.js` | 搜索数据层 |
| 19 | `components/search/SearchBar.vue` + `SearchResultItem.vue` | 搜索组件 |
| 20 | `views/Search.vue` | 搜索页面 |
| 21 | `api/favorite.js` | 收藏 API |
| 22 | `views/Favorites.vue` | 收藏页面 |
| 23 | `components/common/ProcessBadge.vue` + `EmptyState.vue` | 通用组件收尾 |

---

### Task 8: 分享模块 — Redis 分享码 + 公开访问

**目标:** 创建文件分享链接，Redis 存储分享码 + TTL 过期，GET 端点公开无需认证

- [ ] **Step 8.1: 创建 ShareService + ShareController**

```java
// allahpan-core/src/main/java/com/allahpan/service/ShareService.java
public interface ShareService {
    Map<String, Object> createShare(Long fileId, int expireHours);
    Map<String, Object> getShare(String code);      // 公开
    void deleteShare(String code);                   // 创建者
}
```

```java
// allahpan-core/src/main/java/com/allahpan/controller/ShareController.java
@RestController
@RequestMapping("/api/share")
public class ShareController {
    // POST /{fileId}?expireHours=24    创建分享 → {shareCode, shareUrl, expireTime}
    // GET  /{code}                     获取分享（公开）→ {fileId, fileName, downloadUrl}
    // DELETE /{code}                   删除分享（仅创建者）
}
```

**Redis 存储:**
- Key: `allahpan:share:{code}` (8 位 UUID 随机码)
- Value: `{"fileId":43, "creatorId":1, "expireTime":1749999999999}`
- TTL: `expireHours * 3600 + 3600`（1 小时缓冲）

**实现细节:**
- 分享码生成: `UUID.randomUUID().toString().replace("-","").substring(0,8)`，重试 3 次防碰撞
- 有效期限制: 1~168 小时（7 天）
- 公开 GET 端点: 无需 JWT token，通过 `secure.ignored.urls` 添加 `/api/share/*`
- 过期处理: 访问时检查 `expireTime < currentTime`，过期则自动 `redisService.del()`
- 删除鉴权: 比对 `creatorId` 和当前登录用户，非创建者拒绝

```bash
# 创建分享
curl -X POST "http://localhost:8088/api/share/43?expireHours=48" \
  -H "Authorization: Bearer $TOKEN"

# 访问分享（无需 token）
curl "http://localhost:8088/api/share/a1b2c3d4"

# 删除分享
curl -X DELETE http://localhost:8088/api/share/a1b2c3d4 \
  -H "Authorization: Bearer $TOKEN"
```

---

### Task 9: 部署 — Docker Compose + Cloudflare Tunnel

**目标:** 一键部署整个系统，通过 Cloudflare Tunnel 安全暴露到公网

> Cloudflare Tunnel 的优势：无需开放宿主机端口（443/80），Cloudflare 自动处理 SSL 证书和 DDoS 防护，`cloudflared` 守护进程通过出站连接将流量从 Cloudflare 边缘节点转发到本地 nginx。

- [ ] **Step 8.1: 创建 Dockerfile（allahpan-core）**

```dockerfile
# allahpan-core/Dockerfile
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY target/allahpan-core-1.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "-Dspring.profiles.active=prod", "app.jar"]
```

```dockerfile
# allahpan-search/Dockerfile
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY target/allahpan-search-1.0.0.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
```

- [ ] **Step 8.2: 创建 docker-compose.yml（Cloudflare Tunnel 版）**

> 与原 spec 7.1 相比：① 移除 certbot（Cloudflare 自动签发 SSL）；② 新增 cloudflared 服务；③ nginx 只监听内网 80，不暴露 443；④ 应用容器无需映射宿主机端口（cloudflared 通过 Docker 内部网络访问 nginx）

```yaml
# docker-compose.yml
services:

  # ========== Cloudflare Tunnel ==========
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel run
    volumes:
      - ./cloudflared/config.yml:/etc/cloudflared/config.yml
      - ./cloudflared/credentials.json:/etc/cloudflared/credentials.json
    depends_on:
      - nginx
    restart: unless-stopped

  # ========== 网关层 ==========
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"       # 仅留本地测试用，公网流量走 Cloudflare Tunnel
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./allahpan-web/dist:/usr/share/nginx/html
    depends_on:
      - allahpan-core
      - allahpan-search

  # ========== 应用层 ==========
  allahpan-core:
    build: ./allahpan-core
    # 不映射宿主机端口（cloudflared → nginx → core 走 Docker 内网）
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    depends_on:
      - mysql
      - redis
      - minio
      - rabbitmq

  allahpan-search:
    build: ./allahpan-search
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    depends_on:
      - elasticsearch

  # ========== 数据层（与原版相同） ==========
  mysql:
    image: mysql:8.0
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: allahpan
    volumes:
      - ./docker-data/mysql:/var/lib/mysql

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
    volumes:
      - ./docker-data/redis:/data

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ./docker-data/minio:/data
    command: server /data --console-address ":9001"

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - ./docker-data/rabbitmq:/var/lib/rabbitmq

  elasticsearch:
    image: elasticsearch:7.17.0
    ports:
      - "9200:9200"
    environment:
      - "discovery.type=single-node"
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - ./docker-data/es:/usr/share/elasticsearch/data

# .env 文件示例（放在项目根目录）:
# MYSQL_ROOT_PASSWORD=root
# MINIO_ROOT_USER=minioadmin
# MINIO_ROOT_PASSWORD=minioadmin
```

> ⚠️ **开发模式**只需启动基础设施容器（mysql/redis/minio/rabbitmq/es），应用模块在 IDE 中运行。详见 CLAUDE.md 开发环境设置章节。

- [ ] **Step 8.3: 创建 nginx.conf（Cloudflare Tunnel 版 — 无 SSL）**

nginx 只处理 HTTP（Cloudflare 在边缘节点完成 TLS 终止），并将 `X-Forwarded-*` 头透传给后端：

```nginx
# nginx/nginx.conf
server {
    listen 80;
    server_name allah.cn;  # Cloudflare DNS 指向的域名

    client_max_body_size 2G;

    # Cloudflare Tunnel 通过 HTTP 连接，nginx 信任其转发头
    real_ip_header CF-Connecting-IP;
    set_real_ip_from 0.0.0.0/0;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://allahpan-core:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /es-admin/ {
        proxy_pass http://allahpan-search:8081/es-admin/;
        proxy_set_header Host $host;
    }
}
```

- [ ] **Step 8.4: 创建 Cloudflare Tunnel 配置**

```bash
# 在 Cloudflare Zero Trust 面板创建 Tunnel
# 1. 登录 https://one.dash.cloudflare.com
# 2. Networks → Tunnels → Create a tunnel
# 3. 命名（如 allahpan-tunnel）→ 保存 → 记下 tunnel ID
# 4. 将 credentials.json 下载到项目 cloudflared/ 目录
```

```yaml
# cloudflared/config.yml
tunnel: <your-tunnel-id>
credentials-file: /etc/cloudflared/credentials.json

ingress:
  # 所有流量转发到 nginx
  - hostname: allah.cn
    service: http://nginx:80
  # 可选：子域名转发到搜索服务
  - hostname: search.allah.cn
    service: http://allahpan-search:8081
  # 兜底规则（必须）
  - service: http_status:404
```

```
# cloudflared/credentials.json（从 Cloudflare 下载，格式如下）
{
  "AccountTag": "<account-tag>",
  "TunnelSecret": "<base64-encoded-secret>",
  "TunnelID": "<tunnel-id>"
}
```

- [ ] **Step 8.5: 一键启动验证**

```bash
# 1. 编译全部模块
# 在项目根目录下执行
mvn clean package -DskipTests

# 2. 复制前端构建产物（如果已构建前端）
# cp -r allahpan-web/dist ./allahpan-web/dist

# 3. 启动全部服务
docker compose up -d

# 4. 查看状态
docker compose ps
# 预期: 8 个容器 running（nginx + cloudflared + 2 应用 + 5 基础设施）

# 5. 查看 cloudflared 日志，确认隧道已连接
docker compose logs cloudflared
# 预期: "Registered tunnel connection..."

# 6. 本地验证（bash/zsh）:
curl http://localhost/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"phone":"13800138000"}'
# Windows PowerShell: curl.exe http://localhost/api/auth/send-code -H "Content-Type: application/json" -d '{\"phone\":\"13800138000\"}'

# 7. 公网验证（通过域名访问）:
# curl https://allah.cn/api/auth/send-code \
#   -H "Content-Type: application/json" \
#   -d '{"phone":"13800138000"}'
```


---

## 实现顺序依赖图

```
Task 1（骨架）
  └── Task 2（认证）
        └── Task 3（文件模块）
              ├── Task 4（处理流水线）
              │     └── Task 5（搜索模块）
              ├── Task 6（收藏模块）
              └── Task 8（分享模块）
                    └── Task 7（前端）
                          └── Task 9（部署）
```

每个 Task 完成后都可以独立验证——编译通过、API 可用。

---

> 计划完成。共 9 个 Task，覆盖从零到部署的完整实现路径。
