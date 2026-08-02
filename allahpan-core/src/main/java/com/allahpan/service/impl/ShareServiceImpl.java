package com.allahpan.service.impl;

import com.allahpan.common.api.ResultCode;
import com.allahpan.common.exception.Asserts;
import com.allahpan.common.log.StructuredLog;
import com.allahpan.common.service.RedisService;
import com.allahpan.mbg.mapper.FileMapper;
import com.allahpan.mbg.model.File;
import com.allahpan.service.ShareService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.net.URI;
import java.util.Date;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

@Service
public class ShareServiceImpl implements ShareService {
    private static final Logger log = LoggerFactory.getLogger(ShareServiceImpl.class);
    private static final String SHARE_KEY_PREFIX = "allahpan:share:";
    private static final int MAX_EXPIRE_HOURS = 168; // 7 天

    @Autowired
    private RedisService redisService;
    @Autowired
    private FileMapper fileMapper;
    @Value("${allahpan.share.public-base-url:https://allahpan.cn}")
    private String publicBaseUrl;

    @Override
    public Map<String, Object> createShare(Long fileId, int expireHours) {
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null, "文件不存在");
        Asserts.isTrue(file.getDeleteTime() == null, "文件已删除");
        Asserts.isTrue(file.getIsFolder() != 1, "文件夹不支持分享");
        Asserts.isTrue(file.getStorageKey() != null, "文件无存储对象");
        Asserts.isTrue(expireHours > 0 && expireHours <= MAX_EXPIRE_HOURS,
                "有效期需在 1~" + MAX_EXPIRE_HOURS + " 小时之间");
        String shareBaseUrl = getPublicBaseUrl();

        // 生成唯一分享码（最多重试 10 次）
        String code = null;
        for (int i = 0; i < 10; i++) {
            String candidate = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
            if (!redisService.hasKey(SHARE_KEY_PREFIX + candidate)) {
                code = candidate;
                break;
            }
            log.warn(StructuredLog.event("share.code_collision", "attempt", i + 1));
        }
        Asserts.isTrue(code != null, "生成分享码失败，请重试");

        long expireTime = System.currentTimeMillis() + expireHours * 3600000L;
        Long userId = getCurrentUserId();

        Map<String, Object> shareData = new HashMap<>();
        shareData.put("fileId", fileId);
        shareData.put("creatorId", userId);
        shareData.put("expireTime", expireTime);

        redisService.set(SHARE_KEY_PREFIX + code, shareData, expireHours * 3600L + 3600L);

        Map<String, Object> result = new HashMap<>();
        result.put("shareCode", code);
        // shareUrl 是给用户复制的公网分享页；API 地址另行返回，避免把接口地址当成页面地址。
        result.put("shareUrl", shareBaseUrl + "/share/" + code);
        result.put("shareApiUrl", shareBaseUrl + "/api/share/" + code);
        result.put("expireTime", new Date(expireTime));
        return result;
    }

    @Override
    public Map<String, Object> getShare(String code) {
        File file = getSharedFile(code);

        String downloadUrl = "/api/share/" + code + "/download";

        Map<String, Object> result = new HashMap<>();
        result.put("fileId", file.getId());
        result.put("fileName", file.getFileName());
        result.put("fileSize", file.getFileSize());
        result.put("fileType", file.getFileType());
        result.put("downloadUrl", downloadUrl);
        result.put("createTime", file.getCreateTime());
        return result;
    }

    @Override
    public File getSharedFile(String code) {
        Object data = redisService.get(SHARE_KEY_PREFIX + code);
        Asserts.isTrue(data instanceof Map, "分享链接不存在或已过期");

        Map<?, ?> shareData = (Map<?, ?>) data;
        Number fileIdNum = (Number) shareData.get("fileId");
        Asserts.isTrue(fileIdNum != null, "分享数据异常");

        Object expireObj = shareData.get("expireTime");
        long expireTime;
        if (expireObj instanceof Number) {
            expireTime = ((Number) expireObj).longValue();
        } else {
            log.warn(StructuredLog.event("share.invalid_data", "field", "expireTime",
                    "valueType", expireObj != null ? expireObj.getClass().getSimpleName() : "null"));
            expireTime = 0;
        }
        if (System.currentTimeMillis() > expireTime) {
            redisService.del(SHARE_KEY_PREFIX + code);
            Asserts.fail("分享链接已过期");
        }

        Long fileId = fileIdNum.longValue();
        File file = fileMapper.selectByPrimaryKey(fileId);
        Asserts.isTrue(file != null && file.getDeleteTime() == null, "文件不存在或已删除");
        Asserts.isTrue(file.getIsFolder() != 1, "文件夹不支持分享下载");
        Asserts.isTrue(file.getStorageKey() != null, "文件无存储对象");
        return file;
    }

    @Override
    public void deleteShare(String code) {
        Object data = redisService.get(SHARE_KEY_PREFIX + code);
        Asserts.isTrue(data instanceof Map, "分享链接不存在");

        Map<?, ?> shareData = (Map<?, ?>) data;
        Number creatorIdNum = (Number) shareData.get("creatorId");
        Long creatorId = creatorIdNum != null ? creatorIdNum.longValue() : null;

        Asserts.isTrue(creatorId != null && creatorId.equals(getCurrentUserId()),
                "无权删除他人的分享");

        redisService.del(SHARE_KEY_PREFIX + code);
    }

    private Long getCurrentUserId() {
        var auth = org.springframework.security.core.context.SecurityContextHolder
                .getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof com.allahpan.bo.AdminUserDetails details) {
            return details.getUserId();
        }
        Asserts.fail(ResultCode.UNAUTHORIZED);
        return 0L;
    }

    /**
     * 分享链接不能根据当前请求的 Host 生成：用户可能是从 localhost 或内网入口发起分享的。
     * 这里统一使用部署配置中的公网入口，并拒绝明显的本地地址，避免再次生成不可分享的链接。
     */
    private String getPublicBaseUrl() {
        String baseUrl = publicBaseUrl == null ? "" : publicBaseUrl.trim();
        Asserts.isTrue(!baseUrl.isEmpty(), "公网分享地址未配置，请联系管理员");

        URI uri;
        try {
            uri = URI.create(baseUrl);
        } catch (IllegalArgumentException e) {
            Asserts.fail("公网分享地址配置无效，请联系管理员");
            return "";
        }

        String scheme = uri.getScheme();
        String host = uri.getHost();
        Asserts.isTrue(("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                        && host != null
                        && !isLocalHost(host)
                        && uri.getQuery() == null
                        && uri.getFragment() == null,
                "公网分享地址配置无效，请使用公网 http(s) 地址");

        int end = baseUrl.length();
        while (end > 0 && baseUrl.charAt(end - 1) == '/') {
            end--;
        }
        return baseUrl.substring(0, end);
    }

    private boolean isLocalHost(String host) {
        String normalizedHost = host.toLowerCase(Locale.ROOT);
        if (normalizedHost.startsWith("[") && normalizedHost.endsWith("]")) {
            normalizedHost = normalizedHost.substring(1, normalizedHost.length() - 1);
        }
        return "localhost".equals(normalizedHost)
                || "127.0.0.1".equals(normalizedHost)
                || "0.0.0.0".equals(normalizedHost)
                || "::1".equals(normalizedHost);
    }
}
