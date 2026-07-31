package com.allahpan.search.domain;

import java.util.Date;

import org.springframework.data.annotation.Id;
import org.springframework.data.elasticsearch.annotations.Document;
import org.springframework.data.elasticsearch.annotations.Field;
import org.springframework.data.elasticsearch.annotations.FieldType;
import org.springframework.data.elasticsearch.annotations.InnerField;
import org.springframework.data.elasticsearch.annotations.MultiField;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import org.springframework.data.elasticsearch.annotations.Setting;

@Document(indexName = EsFile.INDEX_NAME)
@Setting(shards = 1, replicas = 0)
@JsonIgnoreProperties(ignoreUnknown = true)
public class EsFile {
    public static final String INDEX_NAME = "allahpan_files_v2";

    @Id
    private Long fileId;

    @Field(type = FieldType.Text, analyzer = "ik_max_word")
    private String fileName;

    @Field(type = FieldType.Keyword)
    private String fileType;

    @MultiField(
            mainField = @Field(type = FieldType.Text, analyzer = "ik_max_word",
                    searchAnalyzer = "ik_smart"),
            otherFields = @InnerField(suffix = "char", type = FieldType.Text,
                    analyzer = "standard"))
    private String originText;

    @Field(type = FieldType.Text, analyzer = "ik_max_word")
    private String filePath;

    private Long uploaderId;

    @Field(type = FieldType.Keyword)
    private String uploaderName;

    private Long fileSize;
    private Boolean isFolder;

    @Field(type = FieldType.Date)
    private Date createTime;

    // getters / setters
    public Long getFileId() { return fileId; }
    public void setFileId(Long fileId) { this.fileId = fileId; }
    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }
    public String getFileType() { return fileType; }
    public void setFileType(String fileType) { this.fileType = fileType; }
    public String getOriginText() { return originText; }
    public void setOriginText(String originText) { this.originText = originText; }
    public String getFilePath() { return filePath; }
    public void setFilePath(String filePath) { this.filePath = filePath; }
    public Long getUploaderId() { return uploaderId; }
    public void setUploaderId(Long uploaderId) { this.uploaderId = uploaderId; }
    public String getUploaderName() { return uploaderName; }
    public void setUploaderName(String uploaderName) { this.uploaderName = uploaderName; }
    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }
    public Boolean getIsFolder() { return isFolder; }
    public void setIsFolder(Boolean folder) { isFolder = folder; }
    public Date getCreateTime() { return createTime; }
    public void setCreateTime(Date createTime) { this.createTime = createTime; }
}
