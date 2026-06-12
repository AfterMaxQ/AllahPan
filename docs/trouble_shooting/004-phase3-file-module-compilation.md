# 004 - Phase 3 文件模块编译错误修复

**日期：** 2026-06-08

## 现象

```text
COMPILATION ERROR:
  FileController.java — 找不到符号 FileProcessSender
  FileServiceImpl.java — int无法转换为Byte
  FileServiceImpl.java — 方法不会覆盖或实现超类型的方法
  FileServiceImpl.java — 找不到符号 log
```

## 原因分析

Phase 3 文件模块部分完成，多个 Java 文件之间存在接口/实现不一致：

1. **`FileProcessSender` 不存在** — `FileController` 提前注入了 Phase 4 才需要的类，但尚未创建。实际上 Controller 中未调用该方法
2. **`getDirectoryTree` 只在 `FileServiceImpl` 中实现，未声明在 `FileService` 接口** — `FileController` 通过接口调用，编译失败
3. **`FileService` 接口重复声明** `permanentlyDelete` / `permanentDelete`
4. **`FileServiceImpl`** — `andIsFolderEqualTo(0)` 期望 `Byte` 但传入 `int`；缺少 `Logger` 声明

## 修复

### 1. 创建 FileProcessSender stub

```java
// allahpan-core/.../component/FileProcessSender.java
@Component
public class FileProcessSender {
    public void send(Long fileId) {
        // Phase 4: RabbitMQ 实现
    }
}
```

### 2. FileService 接口修正

- 新增 `List<File> getDirectoryTree(Long folderId)`
- 删除重复的 `permanentlyDelete`，保留 `permanentDelete`

### 3. FileServiceImpl 修正

- `andIsFolderEqualTo(0)` → `andIsFolderEqualTo((byte) 0)`
- 新增 `private static final Logger log = LoggerFactory.getLogger(...)`
- 删除不在接口中的 `permanentlyDelete` 空方法

## 验证

编译通过后，Phase 3 文件 API 全部可用：

```bash
# 登录
curl -X POST localhost:8088/api/auth/send-code -H "Content-Type: application/json" -d '{"phone":"13800138000"}'
# → 控制台查看验证码

curl -X POST localhost:8088/api/auth/login-by-code -H "Content-Type: application/json" -d '{"phone":"13800138000","code":"975081"}'
# → 获取 token

# 预上传
curl -X POST localhost:8088/api/file/pre-upload -H "Authorization: Bearer $TOKEN" \
  -d '{"md5":"d41...","fileName":"test.png","parentId":0}'
# → {"code":200,"data":{"instant":false,"storageKey":"1/2026/06/xxx.png","preSignedUrl":"http://..."}}

# 确认上传
curl -X POST localhost:8088/api/file/confirm-upload -H "Authorization: Bearer $TOKEN" \
  -d '{"storageKey":"...","fileName":"test.png","parentId":0,"md5":"...","fileSize":1024,"contentType":"image/png"}'
# → {"code":200,"data":{"id":1,"fileType":"IMAGE","processStatus":0}}

# 创建文件夹
curl -X POST localhost:8088/api/file/create-folder -H "Authorization: Bearer $TOKEN" \
  -d '{"folderName":"my_images","parentId":0}'
# → {"code":200,"data":{"id":2,"isFolder":1}}

# 文件列表
curl localhost:8088/api/file/list?parentId=0 -H "Authorization: Bearer $TOKEN"
# → 返回文件和文件夹列表

# 删除（软删除）
curl -X DELETE localhost:8088/api/file/1 -H "Authorization: Bearer $TOKEN"

# 垃圾站
curl localhost:8088/api/file/trash -H "Authorization: Bearer $TOKEN"
```
