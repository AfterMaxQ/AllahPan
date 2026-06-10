package com.allahpan.component;

import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import com.allahpan.service.LocalStorageService;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

@Component
public class FileSystemWatcher {

    private static final Logger log = LoggerFactory.getLogger(FileSystemWatcher.class);

    @Autowired
    private LocalStorageService localStorageService;
    @Autowired
    private FileMapper fileMapper;
    @Autowired(required = false)
    private FileProcessSender fileProcessSender;

    @Value("${allahpan.watch.debounce-ms:1000}")
    private long debounceMs;

    private WatchService watchService;
    private final Map<WatchKey, Path> keyToPath = new ConcurrentHashMap<>();
    private final Set<String> pendingPaths = ConcurrentHashMap.newKeySet();
    private final List<SseEmitter> emitters = new CopyOnWriteArrayList<>();
    private final ScheduledExecutorService debounceExecutor = Executors.newSingleThreadScheduledExecutor();
    private volatile boolean running = true;

    @jakarta.annotation.PostConstruct
    public void start() {
        try {
            watchService = FileSystems.getDefault().newWatchService();
            Path root = localStorageService.getRootDir();
            if (Files.exists(root)) {
                registerAll(root);
            } else {
                Files.createDirectories(root);
                registerAll(root);
            }
            // 启动事件处理线程
            Thread eventThread = new Thread(this::eventLoop, "fs-watcher");
            eventThread.setDaemon(true);
            eventThread.start();
            // 初始全量同步
            debounceExecutor.schedule(this::fullSync, 3, TimeUnit.SECONDS);
            log.info("FileSystemWatcher 已启动, root={}", root);
        } catch (Exception e) {
            log.error("FileSystemWatcher 启动失败", e);
        }
    }

    @PreDestroy
    public void stop() {
        running = false;
        debounceExecutor.shutdown();
        try {
            if (watchService != null) watchService.close();
        } catch (IOException e) {
            log.warn("关闭 WatchService 失败", e);
        }
        // 关闭所有 SSE 连接
        for (SseEmitter emitter : emitters) {
            try { emitter.complete(); } catch (Exception ignored) {}
        }
        emitters.clear();
    }

    // ==================== 目录注册 ====================

    private void registerAll(Path dir) throws IOException {
        Files.walkFileTree(dir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path d, BasicFileAttributes attrs) throws IOException {
                // 跳过缩略图目录和隐藏目录
                String dirName = d.getFileName().toString();
                if (dirName.equals(".thumbnails") || dirName.startsWith(".")) {
                    return FileVisitResult.SKIP_SUBTREE;
                }
                register(d);
                return FileVisitResult.CONTINUE;
            }
        });
    }

    private void register(Path dir) throws IOException {
        WatchKey key = dir.register(watchService,
                StandardWatchEventKinds.ENTRY_CREATE,
                StandardWatchEventKinds.ENTRY_DELETE,
                StandardWatchEventKinds.ENTRY_MODIFY);
        keyToPath.put(key, dir);
    }

    // ==================== 事件处理 ====================

    private void eventLoop() {
        while (running) {
            try {
                WatchKey key = watchService.poll(2, TimeUnit.SECONDS);
                if (key == null) continue;

                Path dir = keyToPath.get(key);
                if (dir == null) {
                    key.cancel();
                    continue;
                }

                for (WatchEvent<?> event : key.pollEvents()) {
                    WatchEvent.Kind<?> kind = event.kind();
                    if (kind == StandardWatchEventKinds.OVERFLOW) {
                        log.warn("WatchService 溢出，触发全量同步");
                        debounceExecutor.schedule(this::fullSync, debounceMs, TimeUnit.MILLISECONDS);
                        continue;
                    }

                    @SuppressWarnings("unchecked")
                    WatchEvent<Path> ev = (WatchEvent<Path>) event;
                    Path name = ev.context();
                    if (name == null) continue;
                    Path fullPath = dir.resolve(name);

                    // 跳过缩略图目录和临时文件
                    String fileName = name.toString();
                    if (fileName.startsWith(".") || fileName.endsWith(".tmp") || fileName.endsWith("~")) {
                        continue;
                    }

                    // 标记待处理路径
                    pendingPaths.add(fullPath.toString());

                    // 新目录需要注册 watch
                    if (kind == StandardWatchEventKinds.ENTRY_CREATE && Files.isDirectory(fullPath)) {
                        try { registerAll(fullPath); } catch (Exception e) {
                            log.warn("注册新目录 watch 失败: {}", fullPath, e);
                        }
                    }
                }

                key.reset();

                // 调度延迟同步
                if (!pendingPaths.isEmpty()) {
                    debounceExecutor.schedule(this::reconcilePending, debounceMs, TimeUnit.MILLISECONDS);
                }

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                log.error("FileSystemWatcher 事件处理异常", e);
            }
        }
    }

    // ==================== 同步逻辑 ====================

    private void reconcilePending() {
        Set<String> paths = new HashSet<>(pendingPaths);
        pendingPaths.clear();

        for (String path : paths) {
            try {
                reconcilePath(Path.of(path));
            } catch (Exception e) {
                log.warn("同步路径失败: {}", path, e);
            }
        }
    }

    private void reconcilePath(Path absolutePath) {
        Path root = localStorageService.getRootDir();
        if (!absolutePath.startsWith(root)) return;

        // 计算相对路径
        Path relative = root.relativize(absolutePath);
        String storageKey = relative.toString().replace('\\', '/');

        boolean exists = Files.exists(absolutePath);

        if (exists) {
            // 文件/文件夹存在于磁盘 → 确保 DB 有记录
            if (Files.isDirectory(absolutePath)) {
                ensureFolderInDb(absolutePath, storageKey);
            } else {
                ensureFileInDb(absolutePath, storageKey);
            }
        } else {
            // 文件/文件夹已从磁盘删除 → 软删除 DB 记录
            removeFromDb(storageKey);
        }
    }

    private void ensureFolderInDb(Path absolutePath, String storageKey) {
        // 查找已有的 DB 记录
        FileExample example = new FileExample();
        example.createCriteria().andStorageKeyEqualTo(storageKey).andDeleteTimeIsNull();
        var existing = fileMapper.selectByExample(example);
        if (!existing.isEmpty()) return; // 已存在

        // 创建新的文件夹记录
        String folderName = absolutePath.getFileName().toString();
        Long parentId = findParentId(absolutePath);

        File folder = new File();
        folder.setUploaderId(1L);
        folder.setParentId(parentId);
        folder.setFileName(folderName);
        folder.setStorageKey(storageKey);
        folder.setIsFolder((byte) 1);
        folder.setFileType("FOLDER");
        folder.setProcessStatus((byte) 3);
        folder.setCreateTime(new Date());
        folder.setFilePath(buildPath(folderName, parentId));
        fileMapper.insert(folder);
        log.info("检测到新文件夹: {} (parentId={})", storageKey, parentId);
        notifyAll("file-created", Map.of("fileId", folder.getId(), "parentId", parentId));
    }

    private void ensureFileInDb(Path absolutePath, String storageKey) {
        FileExample example = new FileExample();
        example.createCriteria().andStorageKeyEqualTo(storageKey).andDeleteTimeIsNull();
        var existing = fileMapper.selectByExample(example);
        if (!existing.isEmpty()) return; // 已存在

        // 二次去重：用 parentId + fileName 兜底检查
        String fileName = absolutePath.getFileName().toString();
        Long parentId = findParentId(absolutePath);
        FileExample nameEx = new FileExample();
        nameEx.createCriteria()
                .andParentIdEqualTo(parentId)
                .andFileNameEqualTo(fileName)
                .andDeleteTimeIsNull();
        if (!fileMapper.selectByExample(nameEx).isEmpty()) {
            log.debug("文件已在 DB 中，跳过: {}", storageKey);
            return;
        }

        try {
            long fileSize = Files.size(absolutePath);

            // 计算 MD5（后台线程，不阻塞事件处理）
            String md5 = "";
            try {
                md5 = calculateMd5(absolutePath);
            } catch (Exception e) {
                log.warn("计算 MD5 失败: {}", absolutePath, e);
            }

            // 检测 MD5 秒传（先在已有记录中查）
            if (!md5.isEmpty()) {
                FileExample md5Ex = new FileExample();
                md5Ex.createCriteria().andMd5EqualTo(md5).andIsFolderEqualTo((byte) 0).andDeleteTimeIsNull();
                var md5List = fileMapper.selectByExample(md5Ex);
                if (!md5List.isEmpty()) {
                    File existingMd5 = md5List.get(0);
                    File dup = new File();
                    dup.setUploaderId(1L);
                    dup.setParentId(parentId);
                    dup.setFileName(fileName);
                    dup.setStorageKey(existingMd5.getStorageKey());
                    dup.setFileSize(existingMd5.getFileSize());
                    dup.setContentType(existingMd5.getContentType());
                    dup.setMd5(md5);
                    dup.setFileType(existingMd5.getFileType());
                    dup.setThumbnailKey(existingMd5.getThumbnailKey());
                    dup.setIsFolder((byte) 0);
                    dup.setProcessStatus((byte) 3);
                    dup.setCreateTime(new Date());
                    dup.setFilePath(buildPath(fileName, parentId));
                    fileMapper.insert(dup);
                    log.info("秒传（文件系统事件）: {} → {}", absolutePath, existingMd5.getStorageKey());
                    notifyAll("file-created", Map.of("fileId", dup.getId(), "parentId", parentId));
                    return;
                }
            }

            // 创建 DB 记录（storageKey = 本地相对路径）
            String contentType = Files.probeContentType(absolutePath);
            if (contentType == null) contentType = "application/octet-stream";
            String fileType = detectFileType(contentType);

            File record = new File();
            record.setUploaderId(1L);
            record.setParentId(parentId);
            record.setFileName(fileName);
            record.setStorageKey(storageKey);
            record.setFileSize(fileSize);
            record.setContentType(contentType);
            record.setMd5(md5);
            record.setFileType(fileType);
            record.setIsFolder((byte) 0);
            record.setProcessStatus((byte) 0);
            record.setCreateTime(new Date());
            record.setFilePath(buildPath(fileName, parentId));
            fileMapper.insert(record);
            log.info("检测到新文件: {} ({} bytes)", storageKey, fileSize);
            notifyAll("file-created", Map.of("fileId", record.getId(), "parentId", parentId));

            // 触发异步处理管线
            if (fileProcessSender != null && !"FOLDER".equals(fileType)) {
                try {
                    fileProcessSender.sendProcess(
                            new com.allahpan.domain.FileProcessMessage(record.getId(),
                                    com.allahpan.domain.FileProcessMessage.Stage.UPLOADED));
                } catch (Exception e) {
                    log.warn("触发处理管线失败: fileId={}", record.getId(), e);
                }
            }
        } catch (Exception e) {
            log.warn("添加文件 DB 记录失败: {}", storageKey, e);
        }
    }

    private void removeFromDb(String storageKey) {
        FileExample example = new FileExample();
        example.createCriteria().andStorageKeyEqualTo(storageKey).andDeleteTimeIsNull();
        var list = fileMapper.selectByExample(example);
        for (File f : list) {
            fileMapper.deleteByPrimaryKey(f.getId());
            log.info("文件已从磁盘删除，硬删除 DB 记录: {} (id={})", storageKey, f.getId());
            notifyAll("file-deleted", Map.of("fileId", f.getId(), "parentId", f.getParentId()));
        }
    }

    // ==================== 全量同步 ====================

    @Scheduled(fixedRateString = "${allahpan.watch.reconcile-interval-minutes:5}", timeUnit = TimeUnit.MINUTES)
    public void fullSync() {
        try {
            log.debug("开始全量同步...");
            Path root = localStorageService.getRootDir();
            if (!Files.exists(root)) return;

            // 收集磁盘上的所有相对路径
            Set<String> diskPaths = new HashSet<>();
            Files.walkFileTree(root, new SimpleFileVisitor<>() {
                @Override
                public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                    String name = dir.getFileName().toString();
                    if (name.equals(".thumbnails") || name.startsWith(".")) {
                        return FileVisitResult.SKIP_SUBTREE;
                    }
                    if (!dir.equals(root)) {
                        diskPaths.add(root.relativize(dir).toString().replace('\\', '/'));
                    }
                    return FileVisitResult.CONTINUE;
                }
                @Override
                public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                    String name = file.getFileName().toString();
                    if (!name.startsWith(".") && !name.endsWith(".tmp") && !name.endsWith("~")) {
                        diskPaths.add(root.relativize(file).toString().replace('\\', '/'));
                    }
                    return FileVisitResult.CONTINUE;
                }
            });

            // 收集 DB 中的所有未删除记录
            FileExample example = new FileExample();
            example.createCriteria().andDeleteTimeIsNull();
            var dbRecords = fileMapper.selectByExample(example);
            Set<String> dbPaths = new HashSet<>();
            Map<String, File> dbMap = new HashMap<>();
            for (File f : dbRecords) {
                if (f.getStorageKey() != null) {
                    dbPaths.add(f.getStorageKey());
                    dbMap.put(f.getStorageKey(), f);
                }
            }

            // 磁盘有但 DB 没有 → 创建
            for (String path : diskPaths) {
                if (!dbPaths.contains(path)) {
                    Path abs = localStorageService.resolve(path);
                    try {
                        if (Files.isDirectory(abs)) {
                            ensureFolderInDb(abs, path);
                        } else {
                            ensureFileInDb(abs, path);
                        }
                    } catch (Exception e) {
                        log.warn("全量同步创建失败: {}", path, e);
                    }
                }
            }

            // DB 有但磁盘没有 → 硬删除（文件已消失，无法移至 .trash/）
            for (String path : dbPaths) {
                if (!diskPaths.contains(path)) {
                    File f = dbMap.get(path);
                    if (f != null && f.getDeleteTime() == null) {
                        fileMapper.deleteByPrimaryKey(f.getId());
                        log.info("全量同步：文件已从磁盘消失，硬删除: {} (id={})", path, f.getId());
                        notifyAll("file-deleted", Map.of("fileId", f.getId(), "parentId", f.getParentId()));
                    }
                }
            }

            int created = diskPaths.size() - dbPaths.size();
            if (created != 0) {
                log.info("全量同步完成: 磁盘{}条, DB{}条", diskPaths.size(), dbPaths.size());
            }
            notifyAll("sync-complete", Map.of());
        } catch (Exception e) {
            log.error("全量同步失败", e);
        }
    }

    // ==================== SSE ====================

    public SseEmitter subscribe() {
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L); // 30 分钟超时
        emitters.add(emitter);

        emitter.onCompletion(() -> emitters.remove(emitter));
        emitter.onTimeout(() -> emitters.remove(emitter));
        emitter.onError(e -> emitters.remove(emitter));

        // 发送初始连接确认
        try {
            emitter.send(SseEmitter.event().name("connected").data("ok"));
        } catch (IOException e) {
            emitters.remove(emitter);
        }

        return emitter;
    }

    public void notifyAll(String eventType, Map<String, Object> data) {
        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name(eventType)
                        .data(data));
            } catch (IOException e) {
                emitters.remove(emitter);
            }
        }
    }

    // ==================== 工具方法 ====================

    private Long findParentId(Path absolutePath) {
        Path parent = absolutePath.getParent();
        if (parent == null || parent.equals(localStorageService.getRootDir())) {
            return 0L;
        }
        String parentKey = localStorageService.getRootDir().relativize(parent).toString().replace('\\', '/');
        FileExample example = new FileExample();
        example.createCriteria().andStorageKeyEqualTo(parentKey).andDeleteTimeIsNull().andIsFolderEqualTo((byte) 1);
        var list = fileMapper.selectByExample(example);
        return list.isEmpty() ? 0L : list.get(0).getId();
    }

    private String buildPath(String fileName, Long parentId) {
        StringBuilder path = new StringBuilder("/" + fileName);
        Long pid = parentId;
        while (pid != null && pid > 0) {
            File parent = fileMapper.selectByPrimaryKey(pid);
            if (parent == null) break;
            path.insert(0, "/" + parent.getFileName());
            pid = parent.getParentId();
        }
        return path.toString();
    }

    private String calculateMd5(Path filePath) {
        try {
            MessageDigest md = MessageDigest.getInstance("MD5");
            byte[] data = Files.readAllBytes(filePath);
            byte[] digest = md.digest(data);
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }

    private String detectFileType(String contentType) {
        if (contentType == null) return "OTHER";
        if (contentType.startsWith("image/")) return "IMAGE";
        if (contentType.startsWith("video/")) return "VIDEO";
        if (contentType.startsWith("application/pdf")) return "DOCUMENT";
        if (contentType.startsWith("text/")) return "DOCUMENT";
        return "OTHER";
    }
}
