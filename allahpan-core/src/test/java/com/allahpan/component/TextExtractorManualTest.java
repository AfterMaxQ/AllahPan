package com.allahpan.component;

import com.allahpan.mbg.model.File;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 手动验证文字提取功能：PDF、PPTX、TXT
 * 不依赖 Spring Boot 容器，直接实例化 TextExtractor + mock MinioUtil
 */
public class TextExtractorManualTest {

    private static TextExtractor extractor;
    private static Path testDir;

    @BeforeAll
    static void setUp() {
        extractor = new TextExtractor(null);
        testDir = Paths.get(System.getProperty("user.home"), "AllahPan", "test-extract");
        try {
            Files.createDirectories(testDir);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        try {
            // 注入 maxTextLength（模拟 @Value 注解）
            var maxLenField = TextExtractor.class.getDeclaredField("maxTextLength");
            maxLenField.setAccessible(true);
            maxLenField.set(extractor, 10000);

            // 注入 mock MinioUtil（从本地文件读取以模拟 MinIO getObject）
            var field = TextExtractor.class.getDeclaredField("minioUtil");
            field.setAccessible(true);
            field.set(extractor, new com.allahpan.component.MinioUtil() {
                @Override public InputStream getObject(String objectKey) throws Exception {
                    return Files.newInputStream(testDir.resolve(objectKey));
                }
            });
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    void testExtractPdf() throws Exception {
        String text = extractDesktopFile(
            "C:\\Users\\ray\\Desktop\\20231003206 雷穗辉 实验2-1.pdf",
            "application/pdf");
        System.out.println("=== PDF 提取结果 (共 " + (text != null ? text.length() : 0) + " 字, 前500字) ===");
        System.out.println(truncate(text));
        assertNotNull(text, "PDF 文字不应为空");
        assertFalse(text.isBlank(), "PDF 文字不应为空白");
    }

    @Test
    void testExtractPptx() throws Exception {
        String text = extractDesktopFile(
            "C:\\Users\\ray\\Desktop\\5.2023版Java面试教程\\06-消息中间件篇\\PPT\\06-消息中间件篇.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation");
        System.out.println("=== PPTX 提取结果 (共 " + (text != null ? text.length() : 0) + " 字, 前500字) ===");
        System.out.println(truncate(text));
        assertNotNull(text, "PPTX 文字不应为空");
        assertFalse(text.isBlank(), "PPTX 文字不应为空白");
    }

    @Test
    void testExtractTxt() throws Exception {
        String text = extractDesktopFile(
            "C:\\Users\\ray\\Desktop\\项目推荐.txt",
            "text/plain");
        System.out.println("=== TXT 提取结果 (共 " + (text != null ? text.length() : 0) + " 字) ===");
        System.out.println(text);
        assertNotNull(text, "TXT 文字不应为空");
        assertFalse(text.isBlank(), "TXT 文字不应为空白");
    }

    private String extractDesktopFile(String srcPath, String contentType) throws Exception {
        Path src = Paths.get(srcPath);
        Path dest = testDir.resolve(src.getFileName().toString());
        Files.copy(src, dest, StandardCopyOption.REPLACE_EXISTING);

        File file = new File();
        file.setId(999L);
        file.setFileName(src.getFileName().toString());
        file.setStorageKey(src.getFileName().toString());
        file.setContentType(contentType);
        file.setFileType("DOCUMENT");
        file.setFileSize(Files.size(src));

        return extractor.extract(file);
    }

    private static String truncate(String text) {
        if (text == null) return "NULL";
        if (text.length() <= 500) return text;
        return text.substring(0, 500) + "\n... (共 " + text.length() + " 字)";
    }
}
