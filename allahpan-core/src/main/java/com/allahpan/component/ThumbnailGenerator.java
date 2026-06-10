package com.allahpan.component;

import com.allahpan.mbg.model.File;
import com.allahpan.service.LocalStorageService;
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
    private LocalStorageService localStorageService;

    @Value("${allahpan.thumbnail.pdf-dpi:150}")
    private int pdfThumbnailDpi;

    private static final int THUMB_WIDTH = 300;

    public String generate(File file) {
        if ("IMAGE".equals(file.getFileType())) {
            return generateImageThumbnail(file);
        } else if ("DOCUMENT".equals(file.getFileType()) &&
                file.getContentType() != null &&
                file.getContentType().contains("pdf")) {
            return generatePdfThumbnail(file);
        }
        return null;
    }

    private String generateImageThumbnail(File file) {
        try {
            BufferedImage original;
            try (InputStream is = localStorageService.read(file.getStorageKey())) {
                original = ImageIO.read(is);
            }
            if (original == null) return null;
            return resizeAndUpload(original);
        } catch (Exception e) {
            throw new RuntimeException("生成缩略图失败", e);
        }
    }

    private String generatePdfThumbnail(File file) {
        try {
            byte[] pdfBytes;
            try (InputStream is = localStorageService.read(file.getStorageKey())) {
                pdfBytes = is.readAllBytes();
            }
            try (PDDocument document = Loader.loadPDF(pdfBytes)) {
                if (document.getNumberOfPages() == 0) {
                    return null;
                }
                PDFRenderer renderer = new PDFRenderer(document);
                float scale = pdfThumbnailDpi / 72.0f;
                BufferedImage pageImage = renderer.renderImage(0, scale);
                if (pageImage == null) return null;
                return resizeAndUpload(pageImage);
            }
        } catch (Exception e) {
            throw new RuntimeException("生成PDF缩略图失败", e);
        }
    }

    private String resizeAndUpload(BufferedImage image) throws Exception {
        int thumbHeight = (int) (image.getHeight() * (THUMB_WIDTH / (double) image.getWidth()));
        BufferedImage thumb = new BufferedImage(THUMB_WIDTH, thumbHeight, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = thumb.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,
                RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g.drawImage(image, 0, 0, THUMB_WIDTH, thumbHeight, null);
        g.dispose();

        String thumbnailKey = UUID.randomUUID() + ".jpg";
        java.nio.file.Path thumbPath = localStorageService.resolveThumbnail(thumbnailKey);
        ImageIO.write(thumb, "jpg", thumbPath.toFile());
        return thumbnailKey;
    }
}
