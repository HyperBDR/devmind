# Data Ops 多币种口径

## 当前原则

Data Ops 从飞书多维表格采集金额时，数据库保存源表中的原始货币口径。
例如一条合同金额为 USD，则 `amount` 字段保存 USD 金额，`currency`
字段保存 `USD`。系统不在采集阶段做汇率换算。

## 展示规则

- 金额展示必须携带币种。
- 多币种聚合必须返回 `*_by_currency` 列表，例如：
  `[{ "currency": "CNY", "amount": 100 }, { "currency": "USD", "amount": 20 }]`。
- 前端展示多币种列表，不把不同币种直接相加。
- 如果只有单一币种，可以同步返回兼容字段 `*_amount`；如果存在多个币种，
  兼容字段应为 `null`，调用方应使用 `*_by_currency`。
- Pipeline 项目展示优先使用源表实际付款金额和付款币种；没有付款金额时，
  再使用合同总金额、预估金额。`统计口径USD` 只作为源表已有兜底字段。

## 聚合规则

- 合同、回款、待回款、支出、Pipeline 预估金额都按 `currency` 分桶。
- 月度趋势按 `month + currency` 分桶。
- 海外结算的应收和已收金额按 `currency` 分桶。
- `统计口径USD`、`cost_usd` 等字段只表示源表已有的 USD 统计字段，
  不能当作全局换算后的统一币种。

## 未来汇率聚合

后续如果需要统一汇率聚合，应新增独立服务，例如：

```python
convert_amount(amount, source_currency, target_currency, rate_date)
```

汇率聚合应在原币种数据之上派生，不能覆盖当前数据库中的原始金额和币种。
统一币种结果应使用独立字段或独立 API 返回，例如 `amount_converted`、
`target_currency`、`exchange_rate`、`rate_date`。

## 兼容字段（`*_amount`）与多币种分桶（`*_by_currency`）

`get_summary()` / `get_executive_overview()` 等接口同时返回两套字段：

- `total_contract_amount`、`monthly_signed_amount` 等兼容字段：
  只有当 `*_by_currency` 只有一个币种且金额非零时才返回具体数值；
  多个币种时统一为 `null`，提醒调用方使用 `*_by_currency`。
- `total_contract_amount_by_currency` 等分桶列表：始终返回
  `[{ "currency": "CNY", "amount": ... }, ...]`，长度为零即表示无数据。

Pipeline 摘要（`get_pipeline_summary_data`）当前通过新增的
`domestic_amount_by_currency` / `oversea_amount_by_currency` 字段返回
按币种分桶的结果，不再依赖单一口径；原有的 `domestic_amount`、
`oversea_amount_usd` 仅作为源表的兼容性快照保留。
