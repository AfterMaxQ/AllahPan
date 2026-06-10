package com.allahpan.mbg.mapper;

import com.allahpan.mbg.model.File;
import com.allahpan.mbg.model.FileExample;
import java.util.List;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface FileMapper {
    long countByExample(FileExample example);

    int deleteByExample(FileExample example);

    int deleteByPrimaryKey(Long id);

    int insert(File row);

    int insertSelective(File row);

    List<File> selectByExampleWithBLOBs(FileExample example);

    List<File> selectByExample(FileExample example);

    File selectByPrimaryKey(Long id);

    int updateByExampleSelective(@Param("row") File row, @Param("example") FileExample example);

    int updateByExampleWithBLOBs(@Param("row") File row, @Param("example") FileExample example);

    int updateByExample(@Param("row") File row, @Param("example") FileExample example);

    int updateByPrimaryKeySelective(File row);

    int updateByPrimaryKeyWithBLOBs(File row);

    int updateByPrimaryKey(File row);
}