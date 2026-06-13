package com.allahpan.component;

import io.minio.*;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.InputStream;

@Component
public class MinioUtil {

    private static final Logger log = LoggerFactory.getLogger(MinioUtil.class);

    @Autowired
    private MinioClient minioClient;

    @Value("${minio.bucketName}")
    private String bucketName;

    @Value("${minio.thumbnailBucket}")
    private String thumbnailBucket;

    @Value("${minio.trashBucket}")
    private String trashBucket;

    @PostConstruct
    public void init() {
        for (String bucket : new String[]{bucketName, thumbnailBucket, trashBucket}) {
            try {
                boolean found = minioClient.bucketExists(
                        BucketExistsArgs.builder().bucket(bucket).build());
                if (!found) {
                    minioClient.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
                    log.info("MinIO bucket created: {}", bucket);
                }
            } catch (Exception e) {
                log.error("Failed to check/create MinIO bucket: {}", bucket, e);
                throw new RuntimeException("MinIO bucket initialization failed: " + bucket, e);
            }
        }
        log.info("MinIO storage ready: files={}, thumbnails={}, trash={}",
                bucketName, thumbnailBucket, trashBucket);
    }

    /** Upload object to files bucket */
    public void putObject(String objectKey, InputStream data, long size, String contentType)
            throws Exception {
        putObject(bucketName, objectKey, data, size, contentType);
    }

    /** Upload object to thumbnail bucket */
    public void putThumbnail(String objectKey, InputStream data, long size, String contentType)
            throws Exception {
        putObject(thumbnailBucket, objectKey, data, size, contentType);
    }

    private void putObject(String bucket, String objectKey, InputStream data, long size,
                           String contentType) throws Exception {
        minioClient.putObject(
                PutObjectArgs.builder()
                        .bucket(bucket)
                        .object(objectKey)
                        .stream(data, size, -1)
                        .contentType(contentType)
                        .build()
        );
    }

    /** Download object from files bucket */
    public InputStream getObject(String objectKey) throws Exception {
        return getObject(bucketName, objectKey);
    }

    /** Download object from thumbnail bucket */
    public InputStream getThumbnail(String objectKey) throws Exception {
        return getObject(thumbnailBucket, objectKey);
    }

    private InputStream getObject(String bucket, String objectKey) throws Exception {
        log.debug("MinIO getObject: bucket={} key='{}'", bucket, objectKey);
        try {
            return minioClient.getObject(
                    GetObjectArgs.builder()
                            .bucket(bucket)
                            .object(objectKey)
                            .build()
            );
        } catch (Exception e) {
            log.error("MinIO getObject FAILED: bucket={} key='{}' error={}",
                    bucket, objectKey, e.toString());
            throw e;
        }
    }

    /** Get object metadata */
    public StatObjectResponse statObject(String objectKey) throws Exception {
        return minioClient.statObject(
                StatObjectArgs.builder()
                        .bucket(bucketName)
                        .object(objectKey)
                        .build()
        );
    }

    /** Check if object exists in files bucket */
    public boolean objectExists(String objectKey) {
        try {
            statObject(objectKey);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    /** Delete object from files bucket */
    public void removeObject(String objectKey) throws Exception {
        removeObject(bucketName, objectKey);
    }

    /** Delete object from thumbnail bucket */
    public void removeThumbnail(String objectKey) throws Exception {
        removeObject(thumbnailBucket, objectKey);
    }

    private void removeObject(String bucket, String objectKey) throws Exception {
        minioClient.removeObject(
                RemoveObjectArgs.builder()
                        .bucket(bucket)
                        .object(objectKey)
                        .build()
        );
    }

    /** Copy object: files bucket → trash bucket */
    public void copyToTrash(String objectKey) throws Exception {
        minioClient.copyObject(
                CopyObjectArgs.builder()
                        .source(CopySource.builder()
                                .bucket(bucketName)
                                .object(objectKey)
                                .build())
                        .bucket(trashBucket)
                        .object(objectKey)
                        .build()
        );
    }

    /** Copy object: trash bucket → files bucket */
    public void restoreFromTrash(String objectKey) throws Exception {
        minioClient.copyObject(
                CopyObjectArgs.builder()
                        .source(CopySource.builder()
                                .bucket(trashBucket)
                                .object(objectKey)
                                .build())
                        .bucket(bucketName)
                        .object(objectKey)
                        .build()
        );
    }

    /** Delete object from trash bucket */
    public void removeFromTrash(String objectKey) throws Exception {
        minioClient.removeObject(
                RemoveObjectArgs.builder()
                        .bucket(trashBucket)
                        .object(objectKey)
                        .build()
        );
    }

    /** Copy object within files bucket (used for rename/move) */
    public void copyObject(String sourceKey, String destKey) throws Exception {
        minioClient.copyObject(
                CopyObjectArgs.builder()
                        .source(CopySource.builder()
                                .bucket(bucketName)
                                .object(sourceKey)
                                .build())
                        .bucket(bucketName)
                        .object(destKey)
                        .build()
        );
    }

    public String getBucketName() { return bucketName; }
    public String getThumbnailBucket() { return thumbnailBucket; }
    public String getTrashBucket() { return trashBucket; }
}
