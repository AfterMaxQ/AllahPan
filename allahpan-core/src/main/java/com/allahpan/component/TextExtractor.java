package com.allahpan.component;

import com.allahpan.mbg.model.File;
import com.allahpan.service.LocalStorageService;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.hslf.usermodel.HSLFSlideShow;
import org.apache.poi.hslf.usermodel.HSLFSlide;
import org.apache.poi.hslf.usermodel.HSLFTextParagraph;
import org.apache.poi.hssf.extractor.ExcelExtractor;
import org.apache.poi.hssf.usermodel.HSSFWorkbook;
import org.apache.poi.hwpf.HWPFDocument;
import org.apache.poi.hwpf.extractor.WordExtractor;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFSlide;
import org.apache.poi.xslf.usermodel.XSLFShape;
import org.apache.poi.xslf.usermodel.XSLFTextShape;
import org.apache.poi.xssf.extractor.XSSFExcelExtractor;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.apache.poi.xwpf.extractor.XWPFWordExtractor;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.ByteArrayInputStream;
import java.io.InputStream;

@Component
public class TextExtractor {

    private static final Logger LOG = LoggerFactory.getLogger(TextExtractor.class);

    private final OllamaService ollamaService;

    @Autowired
    private LocalStorageService localStorageService;

    @Value("${allahpan.text.max-length:10000}")
    private int maxTextLength;

    public TextExtractor(OllamaService ollamaService) {
        this.ollamaService = ollamaService;
    }

    public String extract(File file) {
        if ("IMAGE".equals(file.getFileType())) {
            return ollamaService.ocr(file);
        }
        if ("DOCUMENT".equals(file.getFileType())) {
            String ct = file.getContentType();
            if (ct == null) {
                LOG.warn("DOCUMENT 类型但 contentType 为 null, fileId={}", file.getId());
                return null;
            }
            if (ct.startsWith("application/pdf")) {
                return extractPdfText(file);
            }
            if (ct.equals("application/vnd.openxmlformats-officedocument.wordprocessingml.document")) {
                return extractDocxText(file);
            }
            if (ct.equals("application/msword")) {
                return extractDocText(file);
            }
            if (ct.equals("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) {
                return extractXlsxText(file);
            }
            if (ct.equals("application/vnd.ms-excel")) {
                return extractXlsText(file);
            }
            if (ct.equals("application/vnd.openxmlformats-officedocument.presentationml.presentation")) {
                return extractPptxText(file);
            }
            if (ct.equals("application/vnd.ms-powerpoint")) {
                return extractPptText(file);
            }
            if (ct.startsWith("text/")) {
                return extractPlainText(file);
            }
            LOG.warn("未知的 DOCUMENT 子类型，无法提取文本: contentType={}, fileId={}", ct, file.getId());
        }
        return null;
    }

    private String extractPdfText(File file) {
        try {
            byte[] pdfBytes = readFromLocal(file);
            try (PDDocument document = Loader.loadPDF(pdfBytes)) {
                if (document.isEncrypted()) {
                    LOG.warn("PDF 已加密，跳过文本提取: fileId={}", file.getId());
                    return null;
                }
                PDFTextStripper stripper = new PDFTextStripper();
                stripper.setSortByPosition(true);
                String text = stripper.getText(document);
                return truncate(text != null ? text.strip() : null);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("PDF 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractDocxText(File file) {
        try {
            byte[] docxBytes = readFromLocal(file);
            try (XWPFDocument doc = new XWPFDocument(new ByteArrayInputStream(docxBytes));
                 XWPFWordExtractor extractor = new XWPFWordExtractor(doc)) {
                String text = extractor.getText();
                return truncate(text != null ? text.strip() : null);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("DOCX 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractDocText(File file) {
        try {
            byte[] docBytes = readFromLocal(file);
            try (HWPFDocument doc = new HWPFDocument(new ByteArrayInputStream(docBytes));
                 WordExtractor extractor = new WordExtractor(doc)) {
                String text = extractor.getText();
                return truncate(text != null ? text.strip() : null);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("DOC 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractXlsxText(File file) {
        try {
            byte[] xlsxBytes = readFromLocal(file);
            try (XSSFWorkbook wb = new XSSFWorkbook(new ByteArrayInputStream(xlsxBytes));
                 XSSFExcelExtractor extractor = new XSSFExcelExtractor(wb)) {
                extractor.setFormulasNotResults(false);
                extractor.setIncludeSheetNames(true);
                String text = extractor.getText();
                return truncate(text != null ? text.strip() : null);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("XLSX 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractXlsText(File file) {
        try {
            byte[] xlsBytes = readFromLocal(file);
            try (HSSFWorkbook wb = new HSSFWorkbook(new ByteArrayInputStream(xlsBytes));
                 ExcelExtractor extractor = new ExcelExtractor(wb)) {
                extractor.setFormulasNotResults(false);
                extractor.setIncludeSheetNames(true);
                String text = extractor.getText();
                return truncate(text != null ? text.strip() : null);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("XLS 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractPptxText(File file) {
        try {
            byte[] pptxBytes = readFromLocal(file);
            try (XMLSlideShow ppt = new XMLSlideShow(new ByteArrayInputStream(pptxBytes))) {
                StringBuilder sb = new StringBuilder();
                for (XSLFSlide slide : ppt.getSlides()) {
                    for (XSLFShape shape : slide.getShapes()) {
                        if (shape instanceof XSLFTextShape) {
                            String text = ((XSLFTextShape) shape).getText();
                            if (text != null && !text.isBlank()) {
                                sb.append(text).append("\n");
                            }
                        }
                    }
                }
                String result = sb.toString().strip();
                return truncate(result.isEmpty() ? null : result);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("PPTX 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractPptText(File file) {
        try {
            byte[] pptBytes = readFromLocal(file);
            try (HSLFSlideShow ppt = new HSLFSlideShow(new ByteArrayInputStream(pptBytes))) {
                StringBuilder sb = new StringBuilder();
                for (HSLFSlide slide : ppt.getSlides()) {
                    for (java.util.List<HSLFTextParagraph> paraGroup : slide.getTextParagraphs()) {
                        String text = HSLFTextParagraph.getRawText(paraGroup);
                        if (text != null && !text.isBlank()) {
                            sb.append(text).append("\n");
                        }
                    }
                }
                String result = sb.toString().strip();
                return truncate(result.isEmpty() ? null : result);
            }
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("PPT 文本提取失败（文件可能已损坏）: fileId={}, error={}",
                    file.getId(), e.getMessage());
            return null;
        }
    }

    private String extractPlainText(File file) {
        try {
            byte[] textBytes = readFromLocal(file);
            int len = Math.min(textBytes.length, maxTextLength + 1);
            String text = new String(textBytes, 0, len, java.nio.charset.StandardCharsets.UTF_8);
            return truncate(text != null ? text.strip() : null);
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            LOG.warn("文本文件读取失败: fileId={}, error={}", file.getId(), e.getMessage());
            return null;
        }
    }

    private byte[] readFromLocal(File file) throws Exception {
        try (InputStream is = localStorageService.read(file.getStorageKey())) {
            return is.readAllBytes();
        }
    }

    private String truncate(String text) {
        if (text == null || text.isEmpty()) return null;
        if (text.length() <= maxTextLength) return text;
        return text.substring(0, maxTextLength);
    }
}
