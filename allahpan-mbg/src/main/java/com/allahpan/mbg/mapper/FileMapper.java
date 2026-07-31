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

    /**
     * 递归计算文件夹下所有文件的总大小（字节）
     */
    Long getFolderSize(Long folderId);

    /**
     * 一次查询多个文件夹的递归大小，返回的 File 仅填充 id 和 fileSize。
     */
    List<File> getFolderSizes(@Param("folderIds") List<Long> folderIds);

    /**
     * 查询指定垃圾站节点及其仍在垃圾站中的所有子孙节点。
     */
    List<File> selectTrashSubtree(@Param("rootIds") List<Long> rootIds);

    /**
     * 按主键批量物理删除。
     */
    int deleteByIds(@Param("ids") List<Long> ids);

    /**
     * 收藏列表一次 JOIN 取回轻量文件元数据，避免逐条查询和加载 origin_text。
     */
    List<File> selectFavoritesByUserId(@Param("userId") Long userId);
}
