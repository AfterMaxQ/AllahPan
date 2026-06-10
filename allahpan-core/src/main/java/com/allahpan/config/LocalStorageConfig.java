package com.allahpan.config;

import com.allahpan.service.LocalStorageService;
import com.allahpan.service.impl.LocalStorageServiceImpl;
import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class LocalStorageConfig {

    @Value("${allahpan.storage.root-path}")
    private String rootPath;

    @Value("${allahpan.storage.thumbnail-subdir:.thumbnails}")
    private String thumbnailSubdir;

    @Bean
    public LocalStorageService localStorageService() {
        LocalStorageServiceImpl service = new LocalStorageServiceImpl(rootPath, thumbnailSubdir);
        service.init();
        return service;
    }
}
