package com.allahpan.component;

import com.allahpan.mbg.model.File;

public interface EsIndexService {
    void index(File file);
    void delete(Long fileId);
    /** 清空 ES 索引并重建（仅索引未删除的非文件夹文件） */
    long rebuildAll();
}