package com.allahpan.component;

import com.allahpan.mbg.model.File;
import com.allahpan.component.MinioUtil;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.*;
import java.util.UUID;

@Component
public class ThumbnailGenerator {

    @Autowired
    private MinioUtil minioUtil;

    @Value("${allahpan.thumbnail.pdf-dpi:150}")
    private int pdfThumbnailDpi;

    private static final int THUMB_WIDTH = 300;

    public String generate(File file) throws Exception {
        if ("IMAGE".equals(file.getFileType())) {
            return generateImageThumbnail(file);
        } else if ("DOCUMENT".equals(file.getFileType()) &&
                file.getContentType() != null &&
                file.getContentType().contains("pdf")) {
            return generatePdfThumbnail(file);
        }
        return null;
    }

    private String generateImageThumbnail(File file) throws Exception {
        InputStream is = minioUtil.getObject(file.getStorageKey());
        BufferedImage original = ImageIO.read(is);
        is.close();
        if (original == null) return null;
        return resizeAndUpload(original);
    }

    private String generatePdfThumbnail(File file) throws Exception {
        InputStream is = minioUtil.getObject(file.getStorageKey());
        byte[] pdfBytes = is.readAllBytes();
        is.close();
        try (PDDocument document = Loader.loadPDF(pdfBytes)) {
            if (document.getNumberOfPages() == 0) {
                return null;
            }
            PDFRenderer renderer = new PDFRenderer(document);
            BufferedImage image = renderer.renderImageWithDPI(0, pdfThumbnailDpi);
            if (image == null) return null;
            return resizeAndUpload(image);
        }
    }

    private String resizeAndUpload(BufferedImage original) throws Exception {
        int width = THUMB_WIDTH;
        int height = original.getHeight() * width / original.getWidth();
        BufferedImage thumb = new BufferedImage(width, height, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = thumb.createGraphics();
        g.drawImage(original.getScaledInstance(width, height, java.awt.Image.SCALE_SMOOTH), 0, 0, null);
        g.dispose();

        String thumbnailKey = UUID.randomUUID().toString() + ".jpg";

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        ImageIO.write(thumb, "jpg", baos);
        byte[] bytes = baos.toByteArray();

        try (InputStream uploadStream = new ByteArrayInputStream(bytes)) {
            minioUtil.putThumbnail(thumbnailKey, uploadStream, bytes.length, "image/jpeg");
        }

        return thumbnailKey;
    }
}
