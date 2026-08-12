# LLM Ops 来源阶梯价格规格

## 目标

让 LLM Ops 的来源价格统一支持固定单价和请求级 Token 阶梯价：

- 运营人员可以在“手动录入模型价格”中选择固定单价或阶梯价格，并维护
  Input、Output、Cache 三个 Token 维度的共享连续区间。
- 阿里云、Google、SiliconFlow 等官方或供应商采集器返回的 Token 区间
  必须保留为标准化阶梯项，不得在快照、当前价、渠道同步或挂售链路中
  折叠成固定单价。
- 图片、音频和视频规格价继续使用现有 fixed/flat 价格项，不在本次范围内
  引入用量阶梯。

## 假设与兼容边界

1. 阶梯指标沿用现有契约：单次请求的输入 Token 数；区间为左闭右开
   `[tier_start, tier_end)`，最后一档可以无上界。
2. 阶梯采用 matched-tier 计价，不实现累计用量 volume/graduated 计价。
3. 手工录价 API 保留现有标量字段；新增可选 `price_items`。旧调用方不需
   修改，后端会把旧字段转换为 flat 标准项。
4. 同一次手工录入不能混合标量字段与 `price_items`，避免两套价格互相
   覆盖。
5. 外部采集器只保存来源实际给出的区间，不推断或虚构来源未声明的阶梯。

## API 契约

`POST /api/v1/llm-ops/manual-price-import/` 的每个 `rows[]` 新增：

```json
{
  "model_code": "qwen-plus",
  "model_name": "Qwen Plus",
  "currency": "CNY",
  "price_items": [
    {
      "dimension": "text_input",
      "billing_unit": "per_1m_tokens",
      "unit_price": "0.8",
      "tier_type": "usage_range",
      "tier_start": "0",
      "tier_end": "128000",
      "spec": {
        "tier_metric": "request_input_tokens",
        "tier_charge_mode": "matched_tier",
        "aggregation_period": "request"
      }
    }
  ]
}
```

边界校验：

- `dimension` 仅允许 `ModelPriceItem.DIMENSION_CHOICES`。
- `billing_unit` 仅允许 `ModelPriceItem.BILLING_UNIT_CHOICES`。
- `tier_type` 当前允许 `flat`、`usage_range`；`volume` 继续拒绝。
- `unit_price` 和边界必须非负。
- flat 项不得设置边界；usage-range 项必须满足共享价格表契约。
- 后端以 `dimension + variant spec` 分组执行
  `validate_price_table_groups`，拒绝缺口、重叠、重复区间和不连续尾档。
- API 错误继续使用 DRF 字段错误格式，并包含共享契约的机器错误码。

## 采集与持久化

外部平台沿用现有标准目录中的 `price_rows[].values`：

- `input_token_range` 对应 Input 和 Cache 的阶梯边界。
- `output_token_range` 对应 Output 的阶梯边界。
- `deployment_scope`、`region`、`market` 等保留在 `spec`，用于区分独立
  价格变体。
- `sync_model_price_items` 在写入前校验完整价格表，然后以包含阶梯边界和
  `spec` 的 fingerprint 进行版本替换。

阿里云、Google、SiliconFlow 已有区间解析能力，本次需要用端到端测试把
“解析 → 标准目录 → 快照 → ModelPriceItem → 渠道同步”固定为契约。
其他采集器若后续产出相同区间字段，将自动获得相同行为。

## 前端交互

手工录价弹窗的 Token 价格区域提供“固定单价 / 阶梯价格”切换：

- 固定单价保持现有字段和交互。
- 阶梯价格必须与挂售工作台下方的编辑样式和操作保持统一：复用同一套
  阶梯卡片、展开/折叠、阶梯编号、Token 区间、Input/Output/Cache 三列、
  新增/删除按钮、错误态、焦点态和移动端布局，不另做一套相似样式。
- 一个区间同时录入 Input、Output、Cache，空价格代表该维度不产生该档
  价格项。
- 第一档固定从 0 开始；修改某档结束值时，下一档开始值同步更新。
- 可以新增和删除区间；最后一档结束为空表示 `∞`。
- 保存前在客户端执行价格、边界、连续性校验；服务端仍为最终校验边界。
- 桌面和 320px 移动端均可操作，所有按钮和输入框具备可访问标签。

### 组件复用边界

- 将现有 `ResaleTierEditor` 中无业务属性的阶梯区间编辑部分抽为共享组件，
  并继续复用 `ResaleTierCard` 与共享草稿转换/边界联动工具。
- 手工录价直接组合共享区间编辑组件。
- 挂售编辑继续组合同一个共享区间编辑组件，并在其下保留挂售专属的客户
  预览、利润预览、审批快照比较和上游边界锁定。
- 抽取完成后，两个入口的基础卡片 DOM、Tailwind class、交互事件和响应式
  断点来自同一实现，避免仅复制视觉样式造成后续分叉。

## 项目结构

- `backend/llm_ops/serializers.py`：手工标准价格项输入契约。
- `backend/llm_ops/services.py`：兼容标量转换、价格表校验与持久化。
- `backend/llm_ops/collection_services.py`、`price_collectors/parsers/`：
  外部来源区间归一化和持久化保障。
- `frontend/src/components/llm-ops/ManualPriceEntryModal.vue`：录价模式。
- `frontend/src/components/llm-ops/`：从 `ResaleTierEditor` 抽取无挂售业务
  属性的共享阶梯编辑组件，并复用 `ResaleTierCard`。
- `frontend/src/utils/`：复用阶梯卡片、连续边界与标准价格项转换逻辑。
- 后端测试位于 `backend/llm_ops/tests/`；前端单测与组件/工具相邻。

## 代码规范

后端沿用现有 79 字符行宽、英文 docstring/注释和三段式绝对导入。输入
在 Serializer 边界校验，服务层只消费经过校验的标准项。例如：

```python
validate_price_table_groups(price_items)
payloads = build_manual_price_item_payloads(
    source=source,
    model=model,
    rows=price_items,
)
```

前端沿用 Vue 3 `<script setup>`、现有 LLM Ops 设计 token 与 i18n，不增加
新的 UI 依赖。

## 测试策略与命令

- Serializer 单测：兼容旧 flat 输入；接受合法阶梯；拒绝混合、缺口、
  重叠、非法边界和 volume。
- Service/API 集成测试：一次录入完整保存三维阶梯，旧 current 项被安全
  关闭，下游渠道同步保留边界。
- 采集器测试：至少覆盖阿里云、Google、SiliconFlow 的区间解析与持久化。
- 前端单测：草稿转换、连续边界、提交 payload 与校验。
- 浏览器验收：使用 `ego-browser` 对照手工录价与挂售编辑两个入口，检查
  卡片结构、间距、颜色、展开/折叠、增删区间、边界联动、保存、刷新后
  来源价格展示，以及 320px 布局。

```shell
pytest backend/llm_ops/tests/test_serializers.py \
  backend/llm_ops/tests/test_services.py \
  backend/llm_ops/tests/test_source_collectors.py \
  backend/llm_ops/tests/test_official_collector.py
cd frontend && npm run test:unit
cd frontend && npm run typecheck
cd frontend && npm run build
```

## 边界

- 始终执行：向后兼容旧请求；复用共享价格表校验；第三方响应按不可信输入
  处理；变更后运行定向测试和构建。
- 需要另行确认：新增累计 volume/graduated 计价；增加数据库字段或迁移；
  修改正式外部平台账号或价格数据。
- 禁止：把阶梯投影成一个最低/最高固定价；凭页面文案猜测未声明区间；
  修改或删除已有 Playwright 项目文件。

## 验收标准

1. 手工录价可以保存、读取并展示 Input、Output、Cache 的连续阶梯价格。
2. 旧固定单价 UI/API 行为保持兼容。
3. 非法阶梯在前端和 API 均被拒绝，数据库不产生部分写入。
4. 阿里云等来源返回的阶梯区间在标准目录、快照、当前价格项、渠道价格项
   和挂售成本链路保持一致。
5. 手工录价与挂售编辑复用同一个基础阶梯编辑实现；除挂售专属的预览、
   审批和边界锁定外，两个入口的样式、字段布局和交互行为一致。
6. 定向后端测试、前端单测、typecheck、构建和 ego-browser 验收通过。

## 开放问题

无阻塞问题。本规格默认“阿里云等平台”指所有能从可信来源解析出明确
Token 区间的平台；不会为没有区间证据的平台制造阶梯。
