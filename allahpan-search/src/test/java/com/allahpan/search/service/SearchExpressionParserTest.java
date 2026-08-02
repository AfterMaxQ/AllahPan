package com.allahpan.search.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class SearchExpressionParserTest {
    private final SearchExpressionParser parser = new SearchExpressionParser(new ObjectMapper());

    @Test
    void parsesNestedAndOrExpression() {
        String expression = """
                {
                  "type": "group",
                  "logic": "AND",
                  "children": [
                    {"type": "condition", "field": "fileSize", "operator": "gte", "value": 0},
                    {"type": "group", "logic": "OR", "children": [
                      {"type": "condition", "field": "fileType", "operator": "in", "value": ["DOCUMENT", "IMAGE"]},
                      {"type": "condition", "field": "fileName", "operator": "contains", "value": "合同"}
                    ]}
                  ]
                }
                """;

        assertNotNull(parser.parse(expression));
    }

    @Test
    void parsesDateRangeAndFileNameOperators() {
        String expression = """
                {
                  "logic": "AND",
                  "children": [
                    {"field": "createTime", "operator": "between", "value": ["2026-01-01 00:00:00", "2026-12-31 23:59:59"]},
                    {"field": "fileName", "operator": "starts_with", "value": "report"}
                  ]
                }
                """;

        assertDoesNotThrow(() -> parser.parse(expression));
    }

    @Test
    void rejectsUnknownFieldAndInvalidRange() {
        String unknownField = """
                {"logic":"AND","children":[{"field":"uploaderId","operator":"equals","value":1}]}
                """;
        String invalidRange = """
                {"logic":"AND","children":[{"field":"fileSize","operator":"between","value":[100,10]}]}
                """;

        assertThrows(IllegalArgumentException.class, () -> parser.parse(unknownField));
        assertThrows(IllegalArgumentException.class, () -> parser.parse(invalidRange));
    }
}
