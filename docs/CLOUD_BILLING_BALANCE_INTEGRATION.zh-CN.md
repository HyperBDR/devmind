# 云账单余额接入问题整理

本文档记录云账单模块接入各云平台余额采集时遇到的主要问题、当前处理方式，以及后续排查建议。

## 目标

当前云账单模块已经支持在以下链路展示余额信息：

- `BillingData.balance` 存储采集到的平台余额
- 云账单统计页展示平台余额
- 告警规则支持余额阈值
- 告警通知支持余额相关内容
- 采集任务通过 `balance_debug` 输出排查信息

## 当前平台支持情况

### 已支持

- 阿里云
- 腾讯云
- 华为云中国区
- 华为云国际站
- Azure
- 火山引擎

### 有条件支持

- AWS 全球区
  说明：
  当前实现为 best-effort，依赖 AWS 全球区可访问的余额相关接口，结果受账号体系和接口权限限制。

### 暂不支持

- AWS 中国区
  说明：
  当前未找到可稳定用于“中国区账号余额”采集的官方统一余额接口。

## 各平台接入问题记录

### 阿里云

#### 问题 1：余额为空

原因：

- 阿里云 `QueryAccountBalance` 返回结构在不同 SDK 映射下可能是对象属性，也可能是字典结构
- 早期实现只按单一字段结构取值，导致未命中真实返回

处理：

- 同时兼容 SDK 对象属性、`to_map()` 结果和 `body.data` 结构
- 增加余额原始响应日志和任务日志调试信息

#### 问题 2：余额返回为 `0` 或 `None`

原因：

- 业务要求取“现金余额”
- 早期实现优先读取 `AvailableAmount`
- 实际应该优先读取 `AvailableCashAmount`

处理：

- 调整字段优先级为：
  `AvailableCashAmount` -> `AvailableAmount`

#### 问题 3：余额解析失败

原因：

- 阿里云返回金额字符串可能包含千分位逗号，例如 `2,895.93`
- 直接转 `float` 会失败

处理：

- 解析前先移除千分位逗号

### 腾讯云

#### 问题：余额单位是分，不是元

原因：

- 腾讯云 `DescribeAccountBalance` 返回的余额字段实际为“分”
- 早期实现直接按元写入 `balance`

影响：

- 页面和告警里的余额会被放大 100 倍

处理：

- 统一按“分转元”处理
- 在 `balance_debug` 中保留：
  - 原始值 `available_balance_raw`
  - 换算后值 `available_balance`
  - 单位说明 `unit = yuan_from_cent`

### AWS

#### AWS 中国区获取不到余额的原因

当前结论：

- AWS 中国区暂不支持余额采集

原因说明：

- 现有 AWS best-effort 方案依赖 AWS 全球区可访问的余额相关接口
- AWS 中国区账号体系与全球区账号体系隔离
- 中国区凭证不能直接用于全球区余额接口
- 实际调用时会出现类似：
  `UnrecognizedClientException: The security token included in the request is invalid.`

这类错误的根因不是简单的 IAM 权限不足，而是：

- 中国区凭证与全球区接口不兼容
- 或者说当前选用的余额查询接口并不适用于 AWS 中国区

当前处理方式：

- AWS 中国区同步时不尝试余额采集
- `balance` 保持为空的后端语义
- 前端展示为 `0`，并标记“暂不支持”
- `balance_debug.status = unsupported_partition`

后续建议：

- 如果 AWS 中国区后续有新的官方余额接口，再评估接入
- 在此之前不要把中国区的 `0` 解释为真实余额

### 华为云国际站

#### 问题：看起来“获取不到余额”，但实际是余额口径误解

当前结论：

- 华为云国际站支持通过官方接口查询账号余额
- 对应接口为：
  `GET /v2/accounts/customer-accounts/balances`
- SDK 调用为：
  `show_customer_account_balances`

官方说明：

- 该接口用于查询客户账号余额
- 返回中会包含多个 `account_balances`

早期现象：

- 接口返回里可能同时出现：
  - `account_type = 1`
  - `account_type = 2`
- 常见场景是：
  - `account_type = 1` 的金额为 `0`
  - `account_type = 2` 的金额大于 `0`

根因：

- `account_type = 1` 表示余额账户 `Balance`
- `account_type = 2` 表示信用账户 `Credit`
- `Credit` 金额不是现金余额，也不是可直接等价替代的账户余额

因此会出现：

- 用户看到接口里有金额
- 但系统最终采集到的 `balance` 为 `0`

这不是接口不可用，而是“余额口径”需要明确区分：

- 我们当前采集的是账户余额 `Balance`
- 没有把信用额度 `Credit` 混入 `balance`

当前处理方式：

- 继续使用官方余额接口
- 余额取 `account_type = 1`
- 不把 `account_type = 2` 作为 `balance`
- 在 `balance_debug` 中保留所有账户类型，便于排查

已补充的排查信息：

- `measure_id`
- `debt_amount`
- 每个账户项的：
  - `account_type`
  - `amount`
  - `converted_amount`
  - `designated_amount`
  - `credit_amount`

后续建议：

- 如果业务需要同时展示“余额”和“信用额度”，建议新增独立字段，例如：
  - `balance`
  - `credit_limit`
- 不建议直接把 `account_type = 2` 覆盖到 `balance`

### Azure

#### 问题：不能仅凭 `subscription_id` 稳定拿到余额

原因：

- Azure 余额查询通常依赖 `billing_account_id`
- 不同账号体系下，余额接口落点更接近 Billing Account，而不是 Subscription

当前处理方式：

- 优先查询 Billing 的 `availableBalance/default`
- 失败时回退查询 Consumption `balances`
- 支持可选配置 `AZURE_BILLING_ACCOUNT_ID`
- 自动发现不到账单账户时，可手动填写

### 火山引擎

#### 问题：早期只支持账单，不支持余额

原因：

- 原实现仅接入 `ListBill`
- 未额外调用火山引擎费用中心余额接口

当前处理方式：

- 新增 `QueryBalanceAcct`
- 当前余额优先使用 `AvailableBalance`
- 同时记录：
  - `CashBalance`
  - `ArrearsBalance`

## 统一排查建议

当某个平台余额异常时，优先查看采集任务日志中的：

- `ALIBABA balance debug (...)`
- `AWS balance debug (...)`
- `AZURE balance debug (...)`
- `HUAWEI balance debug (...)`
- `HUAWEI-INTL balance debug (...)`
- `TENCENTCLOUD balance debug (...)`
- `VOLCENGINE balance debug (...)`

重点关注：

- `status`
- 原始余额字段
- 解析后余额字段
- 单位字段或 `measure_id`
- 错误码和错误信息

## 当前产品层约定

- 余额字段 `balance` 代表“平台当前余额”口径
- 当官方没有稳定余额接口时，不应伪造真实余额
- 对明确暂不支持的平台，前端可以展示 `0`，但必须附带“暂不支持”标记
- 对存在多个余额相关账户类型的平台，不应混用“余额”和“信用额度”

## 建议的后续优化

- 为“余额”和“信用额度”建立明确区分，避免混淆
- 在前端详情面板中增加 `balance_debug` 的可视化开关，仅用于排查
- 为每个平台补充“余额字段口径说明”
- 补充一份英文版接入说明，便于后续对接国际站平台
