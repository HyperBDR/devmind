---
name: data_ops.pipeline_conversion_diagnosis
description: 分析立项、项目状态和预估金额，定位转化阻塞。
tools:
  - data_ops_query_records
  - data_ops_aggregate
version: "1"
---

# Pipeline 转化诊断

识别高潜、停滞和证据不足的项目。区分国内与海外 Pipeline，输出机会
分组、阻塞位置、优先级和下一步验证动作。
