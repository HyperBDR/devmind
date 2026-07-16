---
name: data_ops.renewal_expiry_monitor
description: 识别合同、服务和 License 的到期与续约窗口。
tools:
  - data_ops_query_records
version: "1"
---

# 续约与到期监控

查询未来到期的合同、服务和 License，按时间窗口和影响范围分组，
输出风险等级、负责人、建议触达时间和需要补充的信息。
