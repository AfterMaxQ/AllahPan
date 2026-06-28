package com.allahpan.service;

import com.allahpan.mbg.model.File;

import java.util.Map;

public interface ShareService {
    Map<String, Object> createShare(Long fileId, int expireHours);
    Map<String, Object> getShare(String code);
    File getSharedFile(String code);
    void deleteShare(String code);
}
