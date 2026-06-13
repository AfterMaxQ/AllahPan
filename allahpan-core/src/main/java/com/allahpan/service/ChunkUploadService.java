package com.allahpan.service;

import java.util.Map;

public interface ChunkUploadService {

    /**
     * 初始化或恢复上传会话
     * @return {uploadId, uploadedChunks, status}
     */
    Map<String, Object> init(String fileName, long fileSize, String fileMd5,
                             String contentType, Long parentId, int chunkSize, int totalChunks);

    /**
     * 上传单个分片
     * @param uploadId  上传会话 ID
     * @param chunkIndex 分片序号 (0-based)
     * @param chunkBytes 分片数据
     */
    void uploadChunk(String uploadId, int chunkIndex, byte[] chunkBytes);

    /**
     * 合并分片并完成上传：合并 → MinIO → MD5 秒传检测 → DB → RabbitMQ
     * @return 文件元数据（与现有上传接口返回格式一致）
     */
    Map<String, Object> complete(String uploadId);

    /**
     * 查询上传会话状态
     * @return {uploadId, fileName, totalChunks, uploadedCount, uploadedChunks, status}
     */
    Map<String, Object> getStatus(String uploadId);
}
