package com.allahpan.component;

import com.allahpan.mbg.model.File;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.io.RandomAccessReadBuffer;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.imageio.IIOImage;
import javax.imageio.ImageIO;
import javax.imageio.ImageReadParam;
import javax.imageio.ImageReader;
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.ImageOutputStream;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Iterator;
import java.util.UUID;

@Component
public class ThumbnailGenerator {

    @Autowired
    private MinioUtil minioUtil;

    @Value("${allahpan.thumbnail.list-width:320}")
    private int listWidth;
    @Value("${allahpan.thumbnail.preview-width:1280}")
    private int previewWidth;
    @Value("${allahpan.thumbnail.jpeg-quality:0.88}")
    private float jpegQuality;
    @Value("${allahpan.thumbnail.pdf-dpi:150}")
    private int pdfThumbnailDpi;
    @Value("${allahpan.thumbnail.max-image-pixels:100000000}")
    private long maxImagePixels;

    public record ThumbnailResult(String listKey, String previewKey) {}

    /** 生成列表缩略图 + 预览高清图 */
    public ThumbnailResult generate(File file) throws Exception {
        BufferedImage source = loadSourceImage(file);
        if (source == null) return null;
        String listKey = resizeAndUpload(source, listWidth);
        String previewKey = resizeAndUpload(source, previewWidth);
        return new ThumbnailResult(listKey, previewKey);
    }

    /** 仅补生成预览图（历史数据迁移用） */
    public String generatePreviewOnly(File file) throws Exception {
        BufferedImage source = loadSourceImage(file);
        if (source == null) return null;
        return resizeAndUpload(source, previewWidth);
    }

    private BufferedImage loadSourceImage(File file) throws Exception {
        if ("IMAGE".equals(file.getFileType())) {
            try (InputStream is = minioUtil.getObject(file.getStorageKey())) {
                return readImageSafely(is);
            }
        }
        if ("DOCUMENT".equals(file.getFileType())
                && file.getContentType() != null
                && file.getContentType().contains("pdf")) {
            Path tempFile = Files.createTempFile("allahpan-thumb-", ".pdf");
            try {
                try (InputStream is = minioUtil.getObject(file.getStorageKey())) {
                    Files.copy(is, tempFile, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                }
                try (PDDocument document = Loader.loadPDF(tempFile.toFile())) {
                    if (document.getNumberOfPages() == 0) return null;
                    PDFRenderer renderer = new PDFRenderer(document);
                    return renderer.renderImageWithDPI(0, pdfThumbnailDpi);
                }
            } finally {
                Files.deleteIfExists(tempFile);
            }
        }
        return null;
    }

    private BufferedImage readImageSafely(InputStream input) throws IOException {
        try (ImageInputStream imageInput = ImageIO.createImageInputStream(input)) {
            if (imageInput == null) return null;
            Iterator<ImageReader> readers = ImageIO.getImageReaders(imageInput);
            if (!readers.hasNext()) return null;
            ImageReader reader = readers.next();
            try {
                reader.setInput(imageInput, true, true);
                int width = reader.getWidth(0);
                int height = reader.getHeight(0);
                long pixels = (long) width * height;
                if (width <= 0 || height <= 0 || pixels > maxImagePixels) {
                    throw new IOException("图片尺寸过大: " + width + "x" + height);
                }

                // 解码阶段直接降采样，避免先创建原尺寸 BufferedImage 再缩小。
                int maxDecodeWidth = Math.max(previewWidth, listWidth);
                int maxDecodeHeight = maxDecodeWidth * 4;
                int sample = Math.max(1, Math.max(
                        width / Math.max(maxDecodeWidth, 1),
                        height / Math.max(maxDecodeHeight, 1)));
                ImageReadParam param = reader.getDefaultReadParam();
                if (sample > 1) {
                    param.setSourceSubsampling(sample, sample, 0, 0);
                }
                return reader.read(0, param);
            } finally {
                reader.dispose();
            }
        }
    }

    private String resizeAndUpload(BufferedImage original, int maxWidth) throws Exception {
        BufferedImage scaled = scaleToWidth(original, maxWidth);
        String key = UUID.randomUUID() + ".jpg";
        byte[] bytes = toJpegBytes(scaled);
        try (InputStream uploadStream = new ByteArrayInputStream(bytes)) {
            minioUtil.putThumbnail(key, uploadStream, bytes.length, "image/jpeg");
        }
        return key;
    }

    private BufferedImage scaleToWidth(BufferedImage original, int maxWidth) {
        int srcW = original.getWidth();
        int srcH = original.getHeight();
        int targetW = Math.min(maxWidth, srcW);
        int targetH = srcH * targetW / srcW;
        if (targetW <= 0 || targetH <= 0) targetW = targetH = 1;

        BufferedImage thumb = new BufferedImage(targetW, targetH, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = thumb.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g.drawImage(original, 0, 0, targetW, targetH, null);
        g.dispose();
        return thumb;
    }

    private byte[] toJpegBytes(BufferedImage image) throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        Iterator<ImageWriter> writers = ImageIO.getImageWritersByFormatName("jpg");
        if (!writers.hasNext()) {
            ImageIO.write(image, "jpg", baos);
            return baos.toByteArray();
        }
        ImageWriter writer = writers.next();
        ImageWriteParam param = writer.getDefaultWriteParam();
        if (param.canWriteCompressed()) {
            param.setCompressionMode(ImageWriteParam.MODE_EXPLICIT);
            param.setCompressionQuality(jpegQuality);
        }
        try (ImageOutputStream ios = ImageIO.createImageOutputStream(baos)) {
            writer.setOutput(ios);
            writer.write(null, new IIOImage(image, null, null), param);
        } finally {
            writer.dispose();
        }
        return baos.toByteArray();
    }
}
