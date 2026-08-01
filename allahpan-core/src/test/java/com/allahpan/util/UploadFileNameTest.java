package com.allahpan.util;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class UploadFileNameTest {
    @Test
    void keepsPlainFileName() {
        assertEquals("合同外材料询价.xlsx", UploadFileName.baseName("合同外材料询价.xlsx"));
    }

    @Test
    void stripsDirectoryUploadRelativePath() {
        assertEquals(
                "合同外材料询价.xlsx",
                UploadFileName.baseName("预算 2026.7.31大观分公司一期完善地面污水收集项目/合同外材料询价.xlsx")
        );
    }

    @Test
    void stripsWindowsStyleClientPath() {
        assertEquals("预算.xlsx", UploadFileName.baseName("C:\\fakepath\\预算.xlsx"));
    }

    @Test
    void preservesNullForExistingValidation() {
        assertNull(UploadFileName.baseName(null));
    }
}
