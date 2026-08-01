package com.allahpan.search;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import com.allahpan.common.exception.GlobalExceptionHandler;
import com.allahpan.common.log.RequestLogFilter;
import org.springframework.context.annotation.Import;

@SpringBootApplication
@Import({RequestLogFilter.class, GlobalExceptionHandler.class})
public class SearchApplication {
    public static void main(String[] args) {
        SpringApplication.run(SearchApplication.class, args);
    }
}
