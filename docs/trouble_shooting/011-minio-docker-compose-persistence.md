# 011 — MinIO 未纳入 docker-compose 导致数据丢失

## 现象

`docker compose down` 或 Docker Desktop 重启后，MinIO 容器丢失，所有已上传文件的存储对象不可访问，下载返回 `NoSuchKey` 错误。

## 根因

MinIO 容器是通过手动 `docker run` 创建的，不在项目 `docker-compose.yml` 中。

```bash
# 手动创建（无持久化配置）
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

问题：
1. `docker compose down` 不会管理手动创建的容器，需单独 `docker rm -f minio`
2. 没有 volume 挂载 → 容器删除后 `/data` 目录丢失 → 所有文件对象消失
3. 新开发者克隆项目后执行 `docker compose up -d` 不会自动获得 MinIO

## 解决方案

将 MinIO 加入 `docker-compose.yml`，并挂载命名卷：

```yaml
services:
  # ... mysql, redis, rabbitmq ...

  minio:
    image: minio/minio
    container_name: minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio-data:/data
    command: server /data --console-address ":9001"
    restart: unless-stopped

volumes:
  mysql-data:
  redis-data:
  rabbitmq-data:
  minio-data:          # 新增
```

效果：
- `docker compose up -d` 一键启动全部基础设施
- `docker compose down` 后 data volume 保留，再次 `up` 时数据完整
- `docker compose down -v` 彻底清理（含 MinIO 数据）

## 注意事项

- MinIO 容器的 `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` 必须与 `application-dev.yml` 中的 `minio.accessKey`/`minio.secretKey` 一致（本项目均为 `minioadmin`/`minioadmin`）
- 首次启动后 `MinioUtil` 构造函数会自动创建 `allahpan-files` 和 `allahpan-thumbnails` 两个 bucket
- 如果宿主机已安装原生 MinIO 服务（端口 9000 冲突），需停止原生服务或修改 docker-compose 端口映射
