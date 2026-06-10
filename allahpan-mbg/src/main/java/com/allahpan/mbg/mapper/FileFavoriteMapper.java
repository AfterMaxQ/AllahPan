package com.allahpan.mbg.mapper;

import com.allahpan.mbg.model.FileFavorite;
import com.allahpan.mbg.model.FileFavoriteExample;
import java.util.List;
import org.apache.ibatis.annotations.Param;

public interface FileFavoriteMapper {
    long countByExample(FileFavoriteExample example);

    int deleteByExample(FileFavoriteExample example);

    int deleteByPrimaryKey(Long id);

    int insert(FileFavorite row);

    int insertSelective(FileFavorite row);

    List<FileFavorite> selectByExample(FileFavoriteExample example);

    FileFavorite selectByPrimaryKey(Long id);

    int updateByExampleSelective(@Param("row") FileFavorite row, @Param("example") FileFavoriteExample example);

    int updateByExample(@Param("row") FileFavorite row, @Param("example") FileFavoriteExample example);

    int updateByPrimaryKeySelective(FileFavorite row);

    int updateByPrimaryKey(FileFavorite row);
}