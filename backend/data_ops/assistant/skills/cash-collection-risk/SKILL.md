---
name: data_ops.cash_collection_risk
description: 识别高金额、临近到期和负责人明确的回款风险。
tools:
  - data_ops_query_records
  - data_ops_aggregate
version: "1"
---

# 回款风险诊断

按币种分别统计待回款，禁止混合币种。定位高金额客户、合同、项目和
负责人，并按影响金额、到期紧迫度和责任明确程度给出跟进优先级。
