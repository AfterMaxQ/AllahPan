# 001 - MBG Generator 表名冲突 & 路径问题

**日期:** 2026-06-07

## 错误日志

```
Table Configuration users matched more than one table (performance_schema..users,allahpan..users)
Column id, specified as an identity column in table users, does not exist in the table.
The specified target project directory src/main/resources does not exist
The specified target project directory src/main/java does not exist
```

## 原因

1. **表名冲突**：MySQL 的 `performance_schema` 数据库中也有一个 `users` 表，MBG 连接时扫描到了两个 `users` 表，匹配失败。

2. **相对路径错误**：`generatorConfig.xml` 中的 `targetProject="src/main/java"` 是相对于工作目录的路径。IDEA 运行 Generator 时工作目录是项目根 `F:\Java\allahpan`，而不是模块根 `allahpan-mbg`，所以找不到 `src/main/java`。

## 修复

### 1. JDBC 连接限定当前数据库

`generatorConfig.xml` 的 `<jdbcConnection>` 中添加：

```xml
<property name="nullCatalogMeansCurrent" value="true"/>
```

### 2. 修改 targetProject 路径

```xml
<!-- 之前（相对于工作目录找不到） -->
<javaModelGenerator targetProject="src/main/java" .../>

<!-- 之后（从项目根定位） -->
<javaModelGenerator targetProject="allahpan-mbg/src/main/java" .../>
```
