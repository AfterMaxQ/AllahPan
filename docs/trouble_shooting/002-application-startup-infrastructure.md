# 002 - 应用首次启动：基础设施连接 & 配置问题

**日期：** 2026-06-07

## 现象

```text
APPLICATION FAILED TO START

Failed to configure a DataSource: 'url' attribute is not specified and
no embedded datasource could be configured.

Reason: Failed to determine suitable jdbc url
```

日志关键行：
```
No active profile set, falling back to 1 default profile: "default"
```

## 原因分析

三个问题叠加导致启动失败：

### 1. dev profile 未激活

`allahpan-core/src/main/resources/` 下只有 `application-dev.yml`，没有 `application.yml`。Spring Boot 默认不激活任何 profile，DataSource 等配置全在 `application-dev.yml` 中，因此完全未被加载。

### 2. Docker 镜像拉取失败（网络）

Docker Desktop 直连 Docker Hub 超时。中国大陆网络环境需配置镜像加速器。且 `daemon.json` 中的 `registry-mirrors` 配置有时不会立刻生效，用 `docker pull <镜像站前缀>/<image>` 直接拉取更可靠。

### 3. 端口占用

前一次启动残留的 Java 进程占用 8080 端口。

## 修复方法

### Step 1 — 创建 `application.yml` 激活 dev profile

```yaml
# allahpan-core/src/main/resources/application.yml
spring:
  profiles:
    active: dev
```

### Step 2 — 启动基础设施

**确认本地 MySQL 已运行：**

```bash
# 检查 3306 端口
netstat -ano | findstr ":3306"
```

如果 `mysqld.exe` 已在监听 3306，则无需 Docker MySQL。否则：

```bash
docker run -d --name mysql-allahpan -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=123456 \
  -e MYSQL_DATABASE=allahpan \
  mysql:8.0
```

**启动 Redis：**

```bash
docker run -d --name redis-allahpan -p 6379:6379 redis:7.0-alpine
```

**启动 RabbitMQ：**

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.12-management-alpine
```

### Step 3 — Docker 镜像拉取（网络问题备用）

如果 `docker pull` 超时，用镜像站前缀直接拉取后重新打标签：

```bash
# 拉取（以 docker.1ms.run 为例）
docker pull docker.1ms.run/redis:7.0-alpine
docker pull docker.1ms.run/rabbitmq:3.12-management

# 重新打标签
docker tag docker.1ms.run/redis:7.0-alpine redis:7.0-alpine
docker tag docker.1ms.run/rabbitmq:3.12-management rabbitmq:3.12-management-alpine
```

### Step 4 — 释放 8080 端口

```powershell
# 找到占用进程
netstat -ano | findstr ":8080"
# 杀掉进程（假设 PID 是 2360）
Stop-Process -Id 2360 -Force
```

### Step 5 — 构建 & 启动

```bash
# 先安装所有依赖模块到本地仓库（排除 search，它无 main class）
mvn clean install -pl allahpan-common,allahpan-mbg,allahpan-security,allahpan-core -DskipTests

# 启动
mvn spring-boot:run -pl allahpan-core
```

## 验证

成功启动标志：

```text
Started AllahPanApplication in 2.129 seconds (process running for 2.279)
Tomcat started on port 8080 (http) with context path '/'
The following 1 profile is active: "dev"
```

## 当前基础设施状态

| 服务 | 运行方式 | 端口 | 状态 |
|------|---------|------|------|
| MySQL | 本地 mysqld.exe | 3306 | ✅ |
| Redis | Docker (redis:7.0-alpine) | 6379 | ✅ |
| RabbitMQ | Docker (rabbitmq:3.12-management-alpine) | 5672 | ✅ |
