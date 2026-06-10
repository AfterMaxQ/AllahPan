package com.allahpan.service;

import java.util.Map;

public interface ShareService {
    Map<String, Object> createShare(Long fileId, int expireHours);
    Map<String, Object> getShare(String code);
    void deleteShare(String code);
}
