package com.allahpan.search.service;

import java.util.Map;

public interface EsFileService {
    void index(Map<String, Object> fileData);
    void delete(Long fileId);
    Map<String, Object> search(String keyword, String fileType, int pageNum, int pageSize);
    /** 删除索引中的所有文档 */
    long deleteAll();
    long count();
}
