# 017 — Ollama 管线停止工作（RabbitMQ + Redis 双故障排查）

## 现象

上传图片后，文件一直停留在"排队中"状态。Ollama 不会主动分析提取图片信息。

## 根因 1：RedisProperties 绑定失败（Spring Boot 3.5.14 + Lettuce 6.6）

Spring Boot 3.5.14 引入的 `lettuce-core:6.6.0.RELEASE` 依赖 `redis-authx-core:0.1.1-beta2`，导致 `RedisProperties` 配置绑定抛出 `IllegalStateException: has not been refreshed yet`，应用启动失败。

**诊断**：运行 `mvn spring-boot:run -pl allahpan-core`，观察启动日志中是否出现 `Error creating bean with name 'spring.data.redis-...RedisProperties': Could not bind properties to 'RedisProperties'`。

**修复**：在 `allahpan-common/pom.xml` 中将 Lettuce 替换为 Jedis：

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-redis</artifactId>
    <exclusions>
        <exclusion>
            <groupId>io.lettuce</groupId>
            <artifactId>lettuce-core</artifactId>
        </exclusion>
    </exclusions>
</dependency>
<dependency>
    <groupId>redis.clients</groupId>
    <artifactId>jedis</artifactId>
</dependency>
```

## 根因 2：RabbitMQ 队列声明竞态

`RabbitMqConfig` 自定义的 `RabbitAdmin` bean 覆盖了 Spring Boot 自动配置的 `RabbitAdmin`，导致后者无法扫描容器中的 Exchange/Queue/Binding bean 进行自动声明。

多次尝试通过 `ApplicationRunner` + `AmqpAdmin`/`RabbitAdmin`/`RabbitTemplate.execute()` 显式声明均失败（日志显示声明成功但队列未创建），根因是 `RabbitAdmin` 内部 `RabbitTemplate` 在 `afterPropertiesSet()` 执行前为 null，`declare*()` 方法静默失败。

**实际情况**：`@RabbitListener` 注解容器启动时自动声明队列，管线消息可以正常传递。日志中 `ntContainer#0-1` 线程的出现证实了这一点。

**最终方案**：移除 `RabbitMqConfig` 中自定义的 `RabbitAdmin` bean，并在 `AllahPanApplication` 中用 `ApplicationRunner` + `RabbitTemplate.execute()` 做兜底声明（通过 AMQP Channel 直接声明）。

## 涉及文件

| 文件 | 改动 |
|------|------|
| `allahpan-common/pom.xml` | Lettuce → Jedis |
| `allahpan-core/.../RabbitMqConfig.java` | 移除自定义 RabbitAdmin bean |
| `allahpan-core/.../AllahPanApplication.java` | 新增 ApplicationRunner 兜底队列声明 |
| `allahpan-core/.../EsIndexServiceImpl.java` | @PostConstruct 恢复 |
| `application-dev.yml` | 恢复 redis 配置 |

## 验证

1. `mvn spring-boot:run -pl allahpan-core` 正常启动（无 RedisProperties 错误）
2. `mvn spring-boot:run -pl allahpan-search` 正常启动
3. 上传图片 → 处理管线自动运行（缩略图 → OCR → ES 索引）
4. 搜索中文关键词返回正确结果
