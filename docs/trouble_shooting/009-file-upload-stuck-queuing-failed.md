# 009 — 文件上传卡在"排队中"或"失败"

## 现象

无论上传什么文件（包括 20MB 图片），文件列表始终显示 `processStatus=0`（排队中）或 `processStatus=-1`（失败），文件永远无法变为"可用"状态。

## 根因分析（三层叠加）

### 第一层：应用无法启动

`FileProcessReceiver.java` 类上的 `@RabbitListener` 注解使用了 SpEL 表达式：

```java
@RabbitListener(queues = "#{T(com.allahpan.config.RabbitMqConfig).PROCESS_QUEUE}")
```

Spring 在创建该 Bean 时报错：

```
Error creating bean with name 'fileProcessReceiver': Lookup method resolution failed
```

导致整个 ApplicationContext 初始化失败 → RabbitMQ 消费者从未注册 → 消息无人消费 → 所有文件卡在 status=0。

**原因**：Spring Boot 3.5.x + Spring AMQP 对 `@RabbitListener` 的 SpEL 表达式中的 `T()` 静态引用解析方式发生了变化，`determineCandidateConstructors` 阶段无法正确处理，抛出 `Lookup method resolution failed`。

### 第二层：RabbitMQ 端口冲突

修复 SpEL 后应用可以启动，但 Docker RabbitMQ 容器映射到宿主机 5672 端口时，与 Windows 上已安装的原生 RabbitMQ 服务冲突。

- **原生 RabbitMQ**（`erl.exe`）：绑定 `0.0.0.0:5672` 和 `0.0.0.0:15672`，优先级高于 Docker 代理
- **Docker RabbitMQ**：端口映射 `0.0.0.0:5672->5672` 实际失败，但 Docker 不报错

结果：
- Spring 应用通过 `127.0.0.1:5672` 连接到**原生** RabbitMQ（v3.10.5）
- 管理界面 `http://localhost:15672` 却访问到**Docker** RabbitMQ（v3.12.14）
- 两边看到的队列/连接状态完全不一致，导致排查方向错误

### 第三层：管线无韧性

即使 RabbitMQ 正常工作，当 MinIO 或 Ollama 不可用时，`FileProcessReceiver` 的 catch 块在所有重试耗尽后统一设置 `processStatus = -1`：

```java
} else {
    file.setProcessStatus((byte) -1);  // 不管什么错误都标记失败
}
```

这导致：Ollama 离线 → IMAGE 文件在 THUMBNAILED 阶段 OCR 失败 → 3 次重试 → 标记 -1，而实际上文件本身完好可用。

## 解决方案

### 1. 修复 SpEL（`FileProcessReceiver.java`）

将 SpEL 表达式替换为纯字符串：

```java
// 修复前
@RabbitListener(queues = "#{T(com.allahpan.config.RabbitMqConfig).PROCESS_QUEUE}")

// 修复后
@RabbitListener(queues = "allahpan.file.process")
```

### 2. 使用原生 RabbitMQ

应用配置 `application-dev.yml` 保持 `spring.rabbitmq.port: 5672`，连接 Windows 原生 RabbitMQ 服务。Docker 中的 RabbitMQ 容器仅作为备选（端口映射可能被占用，不影响应用使用原生服务）。

### 3. 管线韧性降级（`FileProcessReceiver.java`）

在重试耗尽时区分基础设施错误和致命错误：

```java
} else {
    if (isInfrastructureError(e)) {
        // 非关键组件（MinIO/Ollama/ES）不可用 → 降级
        LOG.warn("非关键组件不可用，文件部分功能降级: {}", file.getFileName());
    } else {
        file.setProcessStatus((byte) -1);  // 仅致命错误标记 -1
    }
}
```

`isInfrastructureError()` 通过异常类型和消息关键词判断：
- `DataAccessException` → 致命（数据库错误）
- 消息含 `connect/timeout/refused/unreachable/minio/ollama` → 基础设施（降级）

## 验证

- ✅ 应用正常启动，消费者注册成功
- ✅ `.txt` 文件 130B/16KB/2MB 上传→处理→下载全链路通过
- ✅ `FileProcessReceiverTest` 8 项单元测试全部通过（含降级行为验证）
