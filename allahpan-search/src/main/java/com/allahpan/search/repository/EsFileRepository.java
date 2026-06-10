package com.allahpan.search.repository;

import com.allahpan.search.domain.EsFile;
import org.springframework.data.elasticsearch.repository.ElasticsearchRepository;

public interface EsFileRepository extends ElasticsearchRepository<EsFile, Long> {
}