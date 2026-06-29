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
import javax.imageio.ImageWriteParam;
import javax.imageio.ImageWriter;
import javax.imageio.stream.ImageOutputStream;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
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
                return ImageIO.read(is);
            }
        }
        if ("DOCUMENT".equals(file.getFileType())
                && file.getContentType() != null
                && file.getContentType().contains("pdf")) {
            try (InputStream is = minioUtil.getObject(file.getStorageKey());
                 PDDocument document = Loader.loadPDF(new RandomAccessReadBuffer(is))) {
                if (document.getNumberOfPages() == 0) return null;
                PDFRenderer renderer = new PDFRenderer(document);
                return renderer.renderImageWithDPI(0, pdfThumbnailDpi);
            }
        }
        return null;
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
