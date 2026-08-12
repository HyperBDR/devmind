# LLM Ops 来源阶梯价格实施计划

- [x] 扩展手工录价 API 的标准 `price_items` 契约。
  - 验收：旧标量请求继续通过，合法 usage-range 通过，非法表返回字段错误。
  - 验证：Serializer 红绿测试。
  - 文件：`serializers.py`、`test_serializers.py`。

- [x] 让手工录价服务持久化并原子替换标准 flat/阶梯项。
  - 验收：完整保存三维阶梯，fingerprint/历史关闭正确，渠道同步保留边界。
  - 验证：Service 与 API 集成测试。
  - 文件：`services.py`、`test_services.py`、`test_views.py`。

- [x] 加固外部来源阶梯采集契约。
  - 验收：阿里云、Google、SiliconFlow 的区间从解析结果贯穿至
    `ModelPriceItem`；没有区间的来源保持 flat。
  - 验证：采集器和 source collector 定向测试。
  - 文件：相关 parser、`collection_services.py` 及其测试。

- [x] 实现手工录价共享阶梯编辑体验。
  - 验收：从挂售编辑器抽取共享基础阶梯组件；手工录价和挂售复用同一
    卡片、字段布局、边界联动、增删/折叠交互及响应式样式；挂售专属利润
    预览和审批能力保持在组合层。
  - 验证：前端单测、typecheck、ESLint、生产构建。
  - 文件：`ManualPriceEntryModal.vue`、`ResaleTierEditor.vue`、
    `ResaleTierCard.vue`、共享组件/工具、locale 和测试。

- [ ] 完成跨层回归与浏览器验收。
  - 验收：桌面与 320px 下对照两个入口，基础阶梯卡片的结构、样式和交互
    一致；完成录入保存后刷新，来源价格区间仍正确，网络和控制台无新错误。
  - 验证：完整定向测试与 `ego-browser` task space 记录。
  - 当前：自动化回归已通过；`ego-browser` task space 17 等待本地登录后
    继续桌面与 320px 验收。
