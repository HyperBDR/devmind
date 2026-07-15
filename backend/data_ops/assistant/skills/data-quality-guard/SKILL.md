---
name: data_ops.data_quality_guard
description: 检查同步、字段、权限和记录数变化是否影响分析可信度。
tools:
  - data_ops_get_schema
  - data_ops_query_records
  - data_ops_aggregate
version: "1"
---

# 数据质量守卫

先检查同步任务和表状态，再判断数据是否足以支持业务结论。输出可信度、
问题表、影响范围和修复优先级。
