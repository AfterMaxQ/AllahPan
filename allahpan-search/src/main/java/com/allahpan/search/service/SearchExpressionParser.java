package com.allahpan.search.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import co.elastic.clients.elasticsearch._types.FieldValue;
import co.elastic.clients.elasticsearch._types.query_dsl.Query;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Converts the user-facing, whitelisted expression tree into Elasticsearch queries.
 *
 * <p>The browser never sends Elasticsearch DSL directly. This parser deliberately
 * supports a small, bounded vocabulary so custom expressions cannot access arbitrary
 * fields or execute scripts.</p>
 */
@Component
public class SearchExpressionParser {
    private static final int MAX_JSON_LENGTH = 16_000;
    private static final int MAX_DEPTH = 4;
    private static final int MAX_NODES = 32;
    private static final int MAX_VALUE_LENGTH = 512;

    private static final Set<String> FILE_TYPES = Set.of("IMAGE", "VIDEO", "DOCUMENT", "OTHER");

    private final ObjectMapper objectMapper;

    public SearchExpressionParser(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public Query parse(String expression) {
        if (expression == null || expression.isBlank()) return null;
        if (expression.length() > MAX_JSON_LENGTH) {
            throw invalid("高级筛选条件过长");
        }

        final JsonNode root;
        try {
            root = objectMapper.readTree(expression);
        } catch (Exception e) {
            throw invalid("高级筛选条件格式无效");
        }
        if (root == null || !root.isObject()) {
            throw invalid("高级筛选条件必须是对象");
        }

        Counter counter = new Counter();
        Query query = parseGroup(root, 0, counter);
        if (query == null) throw invalid("高级筛选条件不能为空");
        return query;
    }

    private Query parseGroup(JsonNode node, int depth, Counter counter) {
        if (depth > MAX_DEPTH) throw invalid("高级筛选分组层级不能超过 " + MAX_DEPTH + " 层");
        countNode(counter);

        String logic = text(node, "logic").toUpperCase(Locale.ROOT);
        if (!"AND".equals(logic) && !"OR".equals(logic)) {
            throw invalid("高级筛选只支持 AND 或 OR 分组");
        }
        JsonNode children = node.get("children");
        if (children == null || !children.isArray() || children.isEmpty()) {
            throw invalid("高级筛选分组不能为空");
        }

        List<Query> queries = new ArrayList<>();
        for (JsonNode child : children) {
            if (child == null || !child.isObject()) throw invalid("高级筛选条件格式无效");
            boolean group = "group".equalsIgnoreCase(child.path("type").asText())
                    || child.has("children");
            Query query = group
                    ? parseGroup(child, depth + 1, counter)
                    : parseCondition(child, counter);
            if (query != null) queries.add(query);
        }
        if (queries.isEmpty()) throw invalid("高级筛选分组不能为空");

        return Query.of(q -> q.bool(b -> {
            if ("OR".equals(logic)) {
                b.should(queries).minimumShouldMatch("1");
            } else {
                b.filter(queries);
            }
            return b;
        }));
    }

    private Query parseCondition(JsonNode node, Counter counter) {
        countNode(counter);
        String field = text(node, "field");
        String operator = text(node, "operator").toLowerCase(Locale.ROOT);
        JsonNode value = node.get("value");
        if (value == null || value.isNull()) throw invalid("高级筛选条件缺少值");

        Query positive = switch (field) {
            case "fileName" -> parseFileName(operator, value);
            case "fileType" -> parseFileType(operator, value);
            case "fileSize" -> parseNumberRange("fileSize", operator, value);
            case "createTime" -> parseDateRange("createTime", operator, value);
            case "filePath" -> parseText(operator, "filePath", value);
            case "originText" -> parseText(operator, "originText", value);
            default -> throw invalid("不支持的高级筛选字段: " + field);
        };

        if (isNegative(operator)) {
            return Query.of(q -> q.bool(b -> b.mustNot(positive)));
        }
        return positive;
    }

    private Query parseFileName(String operator, JsonNode value) {
        String text = scalarText(value);
        String field = "fileName.raw";
        return switch (operator) {
            case "equals", "not_equals" -> Query.of(q -> q.term(t -> t
                    .field(field).value(text).caseInsensitive(true)));
            case "contains", "not_contains" -> wildcard(field, "*" + escapeWildcard(text) + "*");
            case "starts_with" -> wildcard(field, escapeWildcard(text) + "*");
            case "ends_with" -> wildcard(field, "*" + escapeWildcard(text));
            default -> throw invalid("文件名不支持操作符: " + operator);
        };
    }

    private Query parseFileType(String operator, JsonNode value) {
        return switch (operator) {
            case "equals", "not_equals" -> {
                String type = normalizedFileType(scalarText(value));
                yield Query.of(q -> q.term(t -> t.field("fileType").value(type)));
            }
            case "in", "not_in" -> {
                List<String> types = arrayOrCommaSeparated(value).stream()
                        .map(this::normalizedFileType).toList();
                if (types.isEmpty()) throw invalid("文件类型列表不能为空");
                List<FieldValue> terms = types.stream().map(FieldValue::of).toList();
                yield Query.of(q -> q.terms(t -> t.field("fileType")
                        .terms(v -> v.value(terms))));
            }
            default -> throw invalid("文件类型不支持操作符: " + operator);
        };
    }

    private Query parseText(String operator, String field, JsonNode value) {
        if (!"contains".equals(operator) && !"not_contains".equals(operator)) {
            throw invalid(field + " 只支持包含或不包含");
        }
        String text = scalarText(value);
        return Query.of(q -> q.matchPhrase(m -> m.field(field).query(text)));
    }

    private Query parseNumberRange(String field, String operator, JsonNode value) {
        if (!Set.of("gt", "gte", "lt", "lte", "between").contains(operator)) {
            throw invalid("文件大小不支持操作符: " + operator);
        }
        if ("between".equals(operator)) {
            List<Double> values = numericPair(value);
            return Query.of(q -> q.range(r -> r.number(n -> n.field(field)
                    .gte(values.get(0)).lte(values.get(1)))));
        }
        double number = numericValue(value);
        return Query.of(q -> q.range(r -> r.number(n -> {
            n.field(field);
            switch (operator) {
                case "gt" -> n.gt(number);
                case "gte" -> n.gte(number);
                case "lt" -> n.lt(number);
                case "lte" -> n.lte(number);
                default -> throw invalid("不支持的范围操作符");
            }
            return n;
        })));
    }

    private Query parseDateRange(String field, String operator, JsonNode value) {
        if (!Set.of("before", "after", "between").contains(operator)) {
            throw invalid("创建时间不支持操作符: " + operator);
        }
        if ("between".equals(operator)) {
            List<String> values = datePair(value);
            return Query.of(q -> q.range(r -> r.date(d -> d.field(field)
                    .gte(values.get(0)).lte(values.get(1)))));
        }
        String date = normalizeDate(scalarText(value));
        return Query.of(q -> q.range(r -> r.date(d -> {
            d.field(field);
            if ("before".equals(operator)) d.lt(date);
            else d.gte(date);
            return d;
        })));
    }

    private Query wildcard(String field, String value) {
        return Query.of(q -> q.wildcard(w -> w.field(field)
                .value(value).caseInsensitive(true)));
    }

    private boolean isNegative(String operator) {
        return operator.startsWith("not_");
    }

    private List<String> arrayOrCommaSeparated(JsonNode value) {
        List<String> result = new ArrayList<>();
        if (value.isArray()) {
            for (JsonNode item : value) result.add(scalarText(item));
        } else {
            for (String item : scalarText(value).split(",")) {
                if (!item.isBlank()) result.add(item.trim());
            }
        }
        return result;
    }

    private List<Double> numericPair(JsonNode value) {
        if (!value.isArray() || value.size() != 2) throw invalid("范围条件需要两个数字");
        double min = numericValue(value.get(0));
        double max = numericValue(value.get(1));
        if (min > max) throw invalid("范围条件的最小值不能大于最大值");
        return List.of(min, max);
    }

    private List<String> datePair(JsonNode value) {
        if (!value.isArray() || value.size() != 2) throw invalid("时间范围需要两个时间");
        String start = normalizeDate(scalarText(value.get(0)));
        String end = normalizeDate(scalarText(value.get(1)));
        if (start.compareTo(end) > 0) throw invalid("时间范围的开始时间不能晚于结束时间");
        return List.of(start, end);
    }

    private double numericValue(JsonNode value) {
        String text = scalarText(value);
        try {
            double number = Double.parseDouble(text);
            if (!Double.isFinite(number) || number < 0) throw new NumberFormatException();
            return number;
        } catch (NumberFormatException e) {
            throw invalid("文件大小必须是非负数字");
        }
    }

    private String normalizedFileType(String value) {
        String type = value.trim().toUpperCase(Locale.ROOT);
        if (!FILE_TYPES.contains(type)) throw invalid("不支持的文件类型: " + value);
        return type;
    }

    private String normalizeDate(String value) {
        String text = value.trim();
        try {
            return Instant.parse(text).toString();
        } catch (DateTimeParseException ignored) {
            try {
                return OffsetDateTime.parse(text).toInstant().toString();
            } catch (DateTimeParseException ignoredAgain) {
                try {
                    return LocalDateTime.parse(text, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
                            .atZone(ZoneId.systemDefault()).toInstant().toString();
                } catch (DateTimeParseException e) {
                    throw invalid("时间格式无效，请使用 YYYY-MM-DD HH:mm:ss");
                }
            }
        }
    }

    private String scalarText(JsonNode node) {
        if (node == null || node.isContainerNode()) throw invalid("高级筛选值必须是文本或数字");
        String value = node.asText().trim();
        if (value.isEmpty()) throw invalid("高级筛选值不能为空");
        if (value.length() > MAX_VALUE_LENGTH) throw invalid("高级筛选值过长");
        return value;
    }

    private String text(JsonNode node, String name) {
        JsonNode value = node.get(name);
        if (value == null || !value.isValueNode()) throw invalid("高级筛选缺少 " + name);
        return scalarText(value);
    }

    private void countNode(Counter counter) {
        if (++counter.count > MAX_NODES) throw invalid("高级筛选条件不能超过 " + MAX_NODES + " 项");
    }

    private String escapeWildcard(String value) {
        return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?");
    }

    private IllegalArgumentException invalid(String message) {
        return new IllegalArgumentException(message);
    }

    private static final class Counter {
        private int count;
    }
}
