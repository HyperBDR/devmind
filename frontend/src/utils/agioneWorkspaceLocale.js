// Localize UI tokens only; business labels are protected before rendering.
import { escapeHTML } from '../components/agione-demo/core.mjs'

export const isEnglishLocale = value => /^en(?:[-_]|$)/i.test(String(value || ''))

const phrases = `
搜索客户名称或ID|Search customers by name or ID
选择画像客户|Choose a customer profile
前期尚未读取|Previous period not loaded
当前账期摘要|Current billing period summary
多次尝试且窗口内无成功调用。|Repeated attempts with no successful requests in this period.
当前窗口存在失败请求，需区分原因与影响。|This period includes failed requests; review the causes and impact.
本期请求量较等长前期下降。|Requests declined compared with the previous period.
搜索模型名称或ID|Search models by name or ID

当前范围趋势，可滚动查看全部序列|Usage trend for this scope; scroll to view all series
聚合明细，可滚动查看|Grouped results; scroll to view all rows
账户与消耗|Balances and credit usage
完整自然日无调用|Complete days without activity
对比等长前期|Compare with the previous period
输入输出均已知|Both input and output are reported
按输入、输出均已知的同一批请求统计；缺失用量不补 0，Token 占比不代表 Credit 扣费占比。|Based on requests with both input and output usage reported. Missing usage is not counted as zero. Token shares do not represent credit charges.
调用主体列表，可滚动查看|Callers; scroll to view all
模型调用列表，可滚动查看全部模型|Model activity; scroll to view all models
线索类型|Signal type
趋势| trend
可滚动查看全部序列|scroll to view all series
可滚动查看|scroll to view all
第|Page\x20
页 · 每页 2 位| · 2 customers per page
搜索客户|Find a customer
查看|View\x20
分析|Analyze\x20
的调用详情| request details
的客户画像| customer insights
的模型调用，ID| model activity, ID
的失败证据| failed requests
的请求量趋势| request trend
的已知 Token趋势| reported-token trend
按至少|Requires at least\x20
暂无时间序列|No time-series data
近期无调用：距所选窗口末端至少|No recent activity: at least\x20
个完整自然日；按当前客户和模型范围的已获取记录判断，不随今天推进。样本较少不认定流失。仅筛选部分请求结果或当前记录不完整时不推断无调用。| complete days before the end of the selected period. Based on retrieved customer and model records, not today's date. Limited activity is not treated as churn. Inactivity is not inferred from incomplete records or filtered outcomes.
已知用量覆盖|Reported usage coverage
另有|plus\x20
实际总量未知|the actual total is unknown
条未返回用量，实际总量未知| requests have no reported usage; the actual total is unknown
个时段仅展示已知用量，实际总量未知| intervals show reported usage only; actual totals are unknown
个时段用量缺失；虚线仅连接已知点，不代表缺失时段用量| intervals have missing usage; dashed lines connect known points without estimating missing data
当前范围无调用主体记录|No callers for this scope
首次调用|First request
按|By\x20
近日|Recent days

经营看板|Overview
经营概览|Overview
自由组合分析|Usage Analytics
组合分析工作台|Usage Analytics
客户深度画像|Customer Insights
客户画像|Customer insights
客户档案|Customer profile
财务与额度|Credits & Billing
入账 / 消耗覆盖：|Credits added / used coverage:\x20
入账客户|Customers with credits added
入账覆盖：|Credits added coverage:\x20
消耗覆盖：|Credits used coverage:\x20
入账数据未完整采集|Credits added data incomplete
消耗数据未完整采集|Credits used data incomplete
日调账暂不可用|Daily adjustments unavailable
入账日数据覆盖：|Daily credits added coverage:\x20
消耗日数据覆盖：|Daily credits used coverage:\x20
暂无完整日数据|No complete daily data
余额为最新快照；消耗按所选日期汇总，缺失不补零。|Balances are the latest snapshot; usage follows the selected dates and missing values are not treated as zero.
所选日期入账数据尚未完整采集|Credits added data for the selected dates is incomplete
日维度调账数据暂不可用|Daily adjustments are unavailable
所选日期消耗数据尚未完整采集|Usage data for the selected dates is incomplete
全量采集完成|Full coverage
更新全部财务|Refresh financial data
Operator 已授权目录财务快照（独立于调用日期、模型和客户筛选）|Financial data for authorized customers; unaffected by request dates, models, or customer filters
当前展示已采集数据，未缓存的日序列不补采、不补零。|Only available daily data is shown. Missing values are not estimated.
近期无调用：部分客户待判断|Recent activity is unknown for some customers
近期无调用：|No recent activity:
部分待判断|Some customers have not been assessed
当前记录不完整或仅按部分结果筛选|The available records are incomplete, or the outcome filter excludes some requests
其他可判断的线索继续展示。|Other signals are shown where sufficient data is available.
可用余额分层|Available balance breakdown
Credit 入账|Credits added
Credit 消耗|Credits used
调账 / 舍入|Adjustments & rounding
产生消耗客户|Customers with usage
低于阈值|Below threshold
余额为 0|Zero balance
余额为负|Negative balance
余额充足|Sufficient balance
余额正常|Normal balance
负余额客户合计欠额|Total owed
账期摘要|Billing period summary
账期消耗|Credits used this billing period
账期覆盖|Billing coverage
财务覆盖|Financial data coverage
查看客户账户 →|View customer accounts →
分析客户消耗 →|Analyze credit usage →
按客户的 USER_AVAILABLE 账户合计判断|Based on each customer's available-credit accounts
平台 Credit 快照，不等同于实际收款与收入|Platform credits are not cash receipts or recognized revenue
平台 Credit 数据，不等同于实际收款与收入|Platform credits are not cash receipts or recognized revenue
余额分层待采集|Balance distribution unavailable
当前没有可用于分层的账户余额。|No account balances are available for this breakdown.
账期摘要待采集|Billing summary unavailable
当前没有可用的账期财务快照。|No billing-period data is available.
财务快照不可用|Financial data unavailable
账期摘要不可用|Billing summary unavailable
未返回可用的已缓存账期数据。|No billing-period data was returned.
本次上游未返回财务数据|The source did not return financial data.
本次上游读取结果|Latest source response
按需直连读取|Query live source
已授权直连范围|Authorized source scope
已授权缓存汇总|Authorized cached totals
只读历史快照|Historical snapshot · read-only
已采集财务 · 非实时|Collected financial data · not live
财务更新中 · 显示上次数据|Finance updating · showing previous data
财务更新中|Finance updating
财务更新失败 · 保留上次数据|Finance update failed · previous data retained
财务更新失败|Finance update failed
正在后台采集财务数据。|Financial data is being collected in the background.
更新失败，请点击页面上方刷新数据重试。|Update failed. Use Refresh data above to retry.
没有可用的已授权财务数据。|No authorized financial data is available.
部分采集完成|Partial collection complete
来源快照待更新|Source data needs updating
上游返回数据有时效提示|The source has flagged this data as out of date
已有缓存不可用|Cached data unavailable
时间未记录|Timestamp unavailable
读取于|Retrieved
采集于|Collected
采集时间未记录|Collection time unavailable
读取中…|Loading…
正在刷新…|Refreshing…
暂无可用|Not available
暂不可用|Unavailable
缺失数据不补零。|Missing values are shown as unknown, not zero.
余额为最近采集值，非实时；账期消耗不随调用日期变化。|Balances reflect the latest available reading. Billing-period credit usage is independent of the request date range.
本次直接读取上游账户与账期；财务口径独立于调用日期。|Account balances and billing data are queried directly; the request date range does not affect billing totals.
Operator 已授权目录财务快照 · 独立于调用日期、模型和客户筛选。|Financial data for customers authorized to the operator; independent of request dates, models, and customer filters.
DevMind 按需直连同平台 Operator 已授权财务接口，不中转 Demo；不随调用筛选变化。|DevMind queries the authorized operator's financial API directly. Request filters do not affect these totals.
仅固定版本中已确认客户的已缓存财务，不代表最新独立账本全量。|Financial data covers only verified customers in this version, not the latest full ledger.
固定版本已确认范围|Verified scope for this version
只读：不触发财务采集|Read-only: does not collect financial data
只读：本次直接读取上游，不修改财务|Read-only: queries the source without changing financial records
只读：导出未开放|Export is not available in this view
只读：请使用页面刷新读取已有快照，不采集|Use Refresh to read existing data; this view does not collect data
只读：仅使用已缓存前期，不补采|Only available comparison data is used; no historical collection is started
只读：只显示本次上游返回的前期|Only comparison data returned by the current query is shown
只读：使用缓存既有规则|Uses the rules associated with this data
只读：使用已验证业务规则|Uses the validated analysis rules
只读：不触发采集|Read-only: no data collection is started
当前范围概览|Selected scope
范围详情|Scope details
请求量|Requests
请求成功率|Success rate
成功率|Success rate
请求失败率|Failure rate
失败率|Failure rate
成功请求|Successful requests
失败请求|Failed requests
调用客户|Active customers
有调用客户|Active customers
调用用户|Users
调用主体|Caller
全部调用主体|All callers
调用主体：|Caller:
已知 Token|Reported tokens
总 Token|Total tokens
输入 / 输出 Token|Input / output tokens
Token 输入 / 输出|Input / output tokens
输入 Token|Input tokens
输出 Token|Output tokens
Token 用量趋势|Token usage over time
Token 指标|Token metric
输入与输出|Input and output
已知用量|Reported usage
用量未知|Usage unknown
用量覆盖|Usage coverage
用量缺失；仅连接已知点，不代表缺失时段用量。|Usage is missing. Lines connect reported points only; they do not estimate missing usage.
当前指标暂无完整用量，请切换指标或查看用量覆盖情况。|Complete usage is unavailable for this metric. Choose another metric or review coverage.
当前指标暂无数据|No data for this metric
暂无可计算占比的用量|Not enough reported usage to calculate shares
平台未提供消耗|Usage not reported by the platform
消耗数据未获取|Usage data unavailable
已知用量 · 沿用页面筛选 · 北京时间|Reported usage · current filters · Shanghai time (UTC+8)
用量未知不代表消耗为 0|Unknown usage does not mean zero usage
时间变化|Usage over time
调用趋势|Request trend
请求变化|Request trend
主维度|Group by
第二维度|Break down by
观察指标|Metric
不拆分|None
组合条件与比较结果|Explore request usage
工作台|Analysis
聚合结果|Grouped results
聚合分组|Request group
分组详情|Group details
分组贡献|Group contribution
分组合计|Group total
完整结果见下表|See the table for all groups
导出当前聚合 ↗|Export results ↗
当前日期与筛选条件|Current date range and filters
当前范围|Current scope
当前局部范围无请求|No requests match the analysis filters
全局范围，不受工作台成员筛选影响。|Scope totals are not affected by the caller filter below.
调用主体筛选只影响下方分析结果，上方范围概览保持不变。|The caller filter applies to the analysis below, not the scope totals above.
汇总基于全部分组，不随翻页变化。|Totals include all groups, not just the current page.
分组结果展示调用事实；是否需要处理，请结合客户线索和请求证据判断。|These results describe request activity. Review customer signals and request details before taking action.
核对分组数值，点击任意一行查看详情。|Select a row to review its metrics and request details.
请求量 · 与等长前期比较|Requests · compared with the previous period
按当前筛选范围的请求数计算，仅反映调用分布。|Shares are based on requests matching the current filters.
请求占比|Request share
占比未知|Share unavailable
占比|Share
未返回的数值显示为 —。|Values not returned by the source are shown as —.
未返回的数据保留为空，不按零计算。|Missing values remain unknown; they are not counted as zero.
当前范围无时间序列|No time-series data for this scope
当前范围无模型调用记录|No model activity for this scope
当前范围无调用主体记录|No callers for this scope
当前范围无请求|No requests for this scope
当前范围无记录|No records for this scope
当前条件无请求|No requests match these filters
当前范围没有调用记录|No requests in this scope
当前日期与筛选组合下没有调用记录|No requests match this date range and these filters
这不表示接口失效，也不表示客户从未使用。可以清除客户/模型/结果条件，或调整日期。|This does not indicate an API failure or that the customer has never used the service. Clear filters or choose another date range.
清除筛选，保留日期|Clear filters, keep dates
清除筛选，查看全部结果|Clear filters and show all outcomes
当前选择|Current selection
清空选择|Clear selection
搜索名称或 ID|Search by name or ID
没有匹配项，试试其他名称或 ID|No matches. Try a different name or ID.
未选择表示全部；调用次数按当前日期与已应用的筛选条件统计。|Leave selections empty to include all. Request counts reflect the current date range and applied filters.
请求结果|Request outcome
全部结果|All outcomes
仅成功|Successful only
仅失败|Failed only
筛选范围说明|About these filters
有调用记录的客户和模型优先显示；暂无调用仅指当前统计范围。行业、应用、项目、Key与渠道暂未开放筛选。|Customers and models with activity appear first. No activity refers only to the selected scope. Industry, application, project, key, and channel filters are not available yet.
重置条件|Reset filters
应用筛选|Apply filters
取消|Cancel
全部客户|All customers
全部请求|All requests
全部信号|All signals
全部|All
其他|Other
日期|Date
客户 ID|Customer ID
客户|Customer
模型 ID|Model ID
模型|Model
组织|Organization
成员账号|User account
租户账号|Tenant account
用户|User
项目 ID|Project ID
项目|Project
所属客户|Customer
未获取客户名称|Customer name unavailable
复制|Copy
归属于谁|Customer ownership
谁发起调用|Callers
请求|Requests
结果 / 原因|Outcome / reason
结果|Outcome
操作|Actions
时间 / 客户|Time / customer
模型 / 调用主体|Model / caller
查看详情 →|View details →
查看调用证据 →|View requests →
查看客户 →|View customer →
查看记录 →|View records →
查看失败证据|View failed requests
回经营看板核实客户线索 →|Review customer signals in Overview →
← 返回经营看板事件列表|← Back to overview activity
返回经营看板|Back to Overview
成功|Success
失败|Failed
未知|Unknown
结果待确认|Outcome unknown
原因待确认|Reason unavailable
原因待分类|Unclassified reason
未知结果|Unknown outcomes
时间未知|Time unavailable
模型未归属|Model not identified
未归属|Not assigned
成员标识未提供|User ID not provided
项目标识缺失|Project ID not provided
标识缺失|Identifier missing
主体信息缺失|Caller unavailable
名称未提供|Name not provided
调用标识未提供|Caller not provided
未提供|Not provided
未录入|Not recorded
单位未标明|Unit not specified
类型未确认|Type not specified
项目调用|Project requests
成员调用|User requests
平台未提供成员标识，按项目统计。|The platform did not provide a user ID. Activity is grouped by project.
成员与项目按各自 ID 分别统计；调用主体数量不等于实际人数。|Users and projects are counted by their IDs. Caller counts are not headcounts.
按客户及成员或项目 ID 分别统计，主体数量不等于实际人数；仅包含有调用记录的主体。|Callers are grouped by customer and user or project ID. Counts are not headcounts and include only origins with activity.
向下滚动查看更多调用主体 ↓|Scroll down for more callers ↓
模型调用分布|Model usage
期间活跃模型|Active models
查看全部模型（|View all models (
上下滚动查看全部模型|Scroll to view all models
搜索 / 筛选客户|Find a customer
客户名称或 ID|Customer name or ID
无匹配客户|No matching customers
请选择当前范围中的客户；无匹配时不保留上个客户。|Choose a customer in the current scope. The previous selection is cleared when no customers match.
正在读取客户…|Loading customer…
当前客户|Selected customer
调用概况|Request activity
末次调用|Last request
活跃自然日|Active days
最近尝试|Latest attempt
平台账期|Billing period
账户余额|Account balance
账户|Account
暂无账户|No accounts available
充值概况|Top-up summary
成功订单次数|Successful orders
最近成功订单|Latest successful order
包含系统赠送，实付金额按币种统计 · 不随调用日期变化。|Includes system gifts; payments are grouped by currency and do not follow the selected dates.
最近 5 条成功订单，包含系统赠送，不随调用日期变化。不同支付币种分别统计。|Latest 5 successful orders, including system gifts. Payments are grouped by currency and do not follow the selected dates.
系统赠送|System gift
次成功订单| successful orders
该客户暂无可用财务数据，可能未在 Operator 授权目录中，或上游未返回。|No financial data is available for this customer; the Operator directory or source may not include it.
累计实付充值|Total top-up amount
成功充值次数|Successful top-ups
最近成功充值|Latest successful top-up
实付金额|Amount paid
支付时间|Payment date
订单号|Order ID
充值成功|Top-up completed
暂无成功充值记录|No successful top-ups
暂无成功线上充值记录|No successful online top-ups
充值记录尚未读取成功，请关闭后刷新账户数据。|Top-up records could not be loaded. Close this view and refresh account data.
仅统计成功线上订单 · 不随调用日期变化。|Successful online payments only · independent of request dates.
↻ 刷新账户数据|↻ Refresh account data
读取失败|Could not retrieve data
读取成功|Retrieved successfully
更新失败 · 保留上次值|Refresh failed · showing the previous value
平台快照待更新|Source data needs updating
读取成功不代表平台快照已更新；平台标记财务数据待更新时，数值仅供参考。|A successful query does not guarantee the source has refreshed its records. Treat figures flagged as out of date as provisional.
此客户财务接口未授权|You are not authorized to view this customer's financial data
平台耗时单位尚未确认，暂不展示 P95 和首 Token 耗时。|The platform's latency units have not been verified. P95 latency and time to first token are unavailable.
平台耗时单位尚未确认，暂不计算 P95。记录数为带有耗时字段的成功请求数。|P95 is unavailable until source latency units are verified. Sample counts include successful requests with a latency value.
P95 耗时|P95 latency
响应耗时暂不可用|Latency unavailable
信号|Signals
使用下降线索|Declining usage
使用下降|Declining usage
接入受阻|Integration issues
窗口内接入受阻|Integration issues in this period
失败原因|Failure analysis
技术失败偏高|Elevated technical errors
技术失败|Technical errors
增长机会|Growth opportunity
少量探索|Early exploration
近期无调用|No recent activity
窗口内稳定用量|Steady usage in this period
窗口内无请求|No requests in this period
待核实线索|Signals to review
待核实|Needs review
排查处理中|In progress
待复核|Pending verification
已完成|Completed
建议下一步|Recommended next step
诊断分类|Signal category
诊断|Review
统计说明|About these metrics
规则设置|Analysis rules
判断依据与数据边界|Methodology & limitations
前期不可用|Previous period unavailable
前期暂不可比较，暂不能判断使用下降|Declining usage cannot be assessed without comparable data
前期未齐，不能判断是否下降|Comparison data is incomplete
前期比较未完成|Comparison not ready
前期读取中…|Loading previous period…
正在准备前期比较|Preparing comparison
正在计算所选日期的调用变化|Calculating usage changes
比较完成前不生成使用下降结论|Declining usage is assessed only after the comparison is complete
正在读取对应的等长前期，完成后自动更新；本期数据可继续查看。|Loading the previous period of the same length. Current-period data remains available.
当前|Current
等长前期|Previous period
前期|Previous
本期请求|Current-period requests
前期请求|Previous-period requests
变化|Change
前期无调用基数|No baseline activity
此前无调用记录，无法计算使用下降比例。|There is no baseline activity, so a percentage decline cannot be calculated.
尚无可比较的等长前期记录。|No comparable records are available for the previous period.
前期无调用，请调整日期或筛选条件后再比较。|No baseline requests were found. Change the dates or filters to compare activity.
缺少可比较的前期记录|Comparable previous-period data is unavailable
未返回可比较的前期数据|The source did not return comparable previous-period data
没有可比较的已缓存前期|No comparable previous-period data is available
前期曲线按等长日期对齐；未返回的数据保留为空。|The previous period is aligned to the same relative dates. Missing values remain unknown.
紧邻的等长日期范围|The immediately preceding period of the same length
前期按已获取记录比较，不认定源历史无遗漏。|Comparisons use retrieved records; completeness of source history is not guaranteed.
优先核实|Review first
待判断|Not assessed
暂无法判断|Cannot assess yet
部分客户待判断|Some customers cannot be assessed
该规则暂无法判断|This rule cannot be assessed yet
当前范围未触发已配置的线索规则。|No configured signals were detected for this scope.
当前范围未发现失败请求|No failed requests in this scope
当前范围未发现接入受阻客户|No access issues detected in this scope
当前阈值下未发现调用下降客户|No customers meet the decline threshold
当前范围没有失败请求。|No failed requests in this scope.
当前范围没有受影响客户。|No affected customers in this scope.
当前范围未发现适用的受阻客户。|No customers meet the access-issue criteria.
当前阈值下未发现调用下降客户。|No customers meet the decline threshold.
未触发可判断的异常线索|No actionable signals detected
存在稳定用量线索|Steady usage observed
请结合调用证据核实|Review the underlying requests
下降客户|Customers with declining usage
下降客户与证据|Declining usage & request details
受阻客户|Customers with integration issues
受影响客户|Affected customers
受阻请求|Requests from customers with integration issues
尝试请求|Request attempts
范围内请求|Requests in scope
失败原因分布|Failure breakdown
已确认余额不足|Confirmed insufficient-credit errors
余额不足|Insufficient credits
已分类技术失败|Classified technical errors
已确认失败|Confirmed failures
技术失败已确认|Confirmed technical errors
请求失败|Failed requests
存在失败请求|Failed requests detected
请求失败表示|A failed request means
窗口内出现失败请求的客户|Customers with failed requests in this period
窗口内接入受阻的客户|Customers with access issues in this period
按本期请求结果筛选客户|Based on current-period request outcomes
查看每位客户的失败请求，进一步定位原因|Review customer requests to investigate the cause
区分余额与技术失败，核对影响与请求证据。|Separate insufficient-credit errors from technical errors, then review impact and request details.
优先查看技术失败的具体错误和受影响客户。|Review technical error details and affected customers first.
优先核对客户余额及充值状态，再复查调用是否恢复成功。|Check available credits and top-ups, then verify that requests succeed.
先查看下降客户的请求变化和失败样本，再判断是否需要跟进。|Review usage changes and failed requests before deciding whether to follow up.
先查看失败证据，核对接入配置与具体错误。|Review failed requests, connection settings, and error details.
先核对余额不足的请求，再排查其他失败原因。|Review insufficient-credit errors first, then investigate other failures.
先核对余额与接入配置，处理后复查成功调用。|Check credits and connection settings, then verify successful requests.
先核对余额与接入，再检查成功调用。|Check credits and access settings, then verify successful requests.
核实是否暂停使用、需求变化或遇到接入障碍。|Check whether usage paused, requirements changed, or access issues occurred.
核实调用下降原因及当前使用需求。|Confirm why usage declined and whether the customer's needs changed.
未发现达到阈值的下降客户|No customers meet the decline threshold
可继续查看客户的实际调用情况。|Continue reviewing customer request activity.
可调整日期或筛选条件后查看。|Try a different date range or filters.
可调整观察范围，继续查看客户的使用变化。|Adjust the scope to explore usage changes.
有新调用后，可继续查看请求结果。|Review request outcomes when new activity is available.
保留当前日期，清除筛选条件后重新查看。|Keep this date range and clear the filters.
当前分类未触发线索，可查看其他分类。|No signals in this category. Review another category.
该规则暂无法判断，请核实数据或调整筛选条件。|This rule cannot be assessed. Review data availability or adjust the filters.
请先切换至全部结果，再判断接入是否受阻|Select all outcomes before assessing access issues
仅查看成功或失败请求，会遗漏判断所需的另一部分记录。|Filtering to one outcome omits records needed for this assessment.
当前记录不完整或仅按部分结果筛选|Records are incomplete or outcome filters are applied
少量样本不足以判断|Not enough data to assess
多次尝试且窗口内无成功调用。|Repeated attempts with no successful requests in this period.
受阻条件：至少 3 次尝试，且所选期间没有成功请求。|Access-issue criteria: at least 3 attempts and no successful requests in the selected period.
按至少 3 次尝试且所选期间无成功请求的条件判断。|Requires at least 3 attempts and no successful requests in the selected period.
只根据所选期间的请求生成线索，不判断客户历史上是否曾成功调用。|Signals use requests in the selected period only; they do not describe the customer's full history.
失败率以当前范围的全部请求为分母；未知结果不归为成功或失败。|Failure rate uses all requests in scope. Unknown outcomes are classified separately.
失败率按当前范围全部请求计算；未知结果单独统计。|Failure rate uses all requests in scope. Unknown outcomes are shown separately.
分母为当前范围全部请求|Based on all requests in scope
占比以当前范围的全部失败请求为分母|Share of all failed requests in scope
当前范围中已确认失败的请求|Confirmed failed requests in scope
以上受阻客户的请求合计|Total requests from customers with access issues
受阻客户中已确认的失败|Confirmed failures from customers with access issues
达到当前下降阈值的客户|Customers meeting the decline threshold
按客户查看前期、本期和变化幅度|Compare customer requests across both periods
按相同筛选条件，比较紧邻等长前期的请求量。|Compares request volume with the preceding period of equal length using the same filters.
本期请求量较等长前期下降。|Request volume declined compared with the previous period.
请求量下降是待核实线索，需结合业务情况判断原因。|Declining usage is a signal to investigate, not a confirmed business outcome.
请求成功表示平台记录的调用结果，业务任务是否完成仍需核实；下降和无调用仅作为待核实线索。|Success reflects the platform's request outcome, not completion of a business task. Declining or absent activity requires further review.
颜色区分线索类型，不代表严重程度。同一客户多条线索合并；失败需要区分偶发、持续、余额与技术原因。|Colors identify signal types, not severity. Signals are combined per customer; investigate whether failures are isolated, persistent, credit-related, or technical.
部分失败原因待分类，请先查看请求证据。|Some failure reasons are unclassified. Review request details first.
其他可判断的线索继续展示。|Other signals with sufficient data remain available.
当前可判断的规则未触发线索；部分规则暂无法判断。|No signals were detected by assessable rules. Some rules lack sufficient data.
使用下降：与等长前期比较，默认阈值可在诊断阈值中调整。|Declining usage is compared with the previous period of equal length. The threshold is configurable.
正在获取所选日期的数据，完成后自动显示。|Loading the selected date range. Results will appear when ready.
所选日期的数据读取未完成，请使用上方重试或返回最近完整7天。|The selected date range could not be loaded. Retry above or choose the last 7 complete days.
调整日期范围，或重新获取所选日期的数据。|Change the date range or retry the query.
重新获取所选日期|Retry this date range
↻ 重新获取前期|↻ Retry comparison
计算中|Calculating
获取中…|Loading…
正在读取|Loading
尚未获取|Not retrieved
上下滚动|Scroll
上一页|Previous
下一页|Next
收起|Show less
小时|hour
自然周|calendar week
按小时|Hourly
按日|Daily
按周|Weekly
汇总粒度|Time interval
北京时间|Shanghai time (UTC+8)
汇总|Totals
最近完整7天|Last 7 complete days
活跃|Active
请求失败率|Failure rate
数据|Data
行业|Industry
应用|Application
渠道|Channel
低于|Below
覆盖|Coverage
有入账记录|Customers with credits added
成功线上充值订单|Successful online top-ups
不随调用日期变化。不同支付币种分别统计。|Independent of request dates. Payment currencies are reported separately.
租户 ID：|Tenant ID:
租户 ID|Tenant ID
调用用户|API user
调用用户 ID：|API user ID:
调用用户 ID|API user ID
项目 ID：|Project ID:
当前筛选|Current filters
完整用量|Complete usage
部分已知，虚线连接|Partially reported; dashed lines connect known points
仅一个统计点，不绘制连线|Only one point is available; no trend line is drawn
按请求量排序|Sorted by requests
按请求量统计|Based on requests
前 8 组|Top 8 groups
滚动查看更多|Scroll for more
自然日|calendar days
所选期间|Selected period
当天|Selected day
`;

const translations = phrases.trim().split('\n').map(line => {
  const at = line.indexOf('|')
  return [line.slice(0, at), line.slice(at + 1)]
}).sort((a, b) => b[0].length - a[0].length)

const units = [
  ['次请求', ' requests'], ['条请求', ' requests'], ['位客户', ' customers'],
  ['个客户', ' customers'], ['个模型', ' models'], ['个分组', ' groups'],
  ['条线索', ' signals'], ['条耗时记录', ' latency samples'],
  ['条用量已知', ' requests with reported usage'], ['个已知样本', ' reported samples'],
  ['条调用标识', ' callers'], ['次成功充值', ' successful top-ups'],
  ['次成功', ' successful'], ['次失败', ' failed'],
  ['次', ''], ['条', ''], ['位', ''], ['组', ' groups'],
  ['天', ' days'], ['日', 'day'], ['周', 'week'], ['共', 'Total '],
]

export function workspaceText(value, locale = 'zh-CN') {
  if (!isEnglishLocale(locale) || typeof value !== 'string') return value
  let result = value.replace(/第\s*([0-9,]+)\s*\/\s*([0-9,]+)\s*页\s*·\s*每页\s*([0-9,]+)\s*位/g, 'Page $1 of $2 · $3 customers per page')
  for (const [from, to] of [...translations, ...units].sort((a,b)=>b[0].length-a[0].length)) result = result.split(from).join(to)
  return result.replace(/(\d)\s{2,}(requests|customers|models)/g,'$1 $2').replace(/(\d+)\s*\/\s*(\d+)\s+(reported samples|requests|customers)/g,'$1 / $2 $3').replace(/(Collected|Retrieved)\s+Timestamp unavailable/g,'Last fetched: unavailable').replace(/ModelRequest share/g,'Model request share').replace(/(Total tokens|Input tokens|Output tokens)(Daily|Hourly|Weekly) trend/g,(_,metric,grain)=>`${grain} ${metric.toLowerCase()} trend`).replace(/DailyTotals/g,'Daily totals').replace(/(\uE101)([A-Za-z])/g, '$1 $2').replace(/\b1 customers\b/g,'1 customer').replace(/\b1 requests\b/g,'1 request').replace(/\b1 models\b/g,'1 model').replace(/（/g, ' (').replace(/）/g, ')')
    .replace(/，/g, ', ').replace(/。/g, '.').replace(/；/g, '; ')
    .replace(/：/g, ': ').replace(/、/g, ', ')
}

// Business strings become opaque tokens before any UI text is translated.
export function protectWorkspaceData(value, protectBusiness = true) {
  const values = []
  const businessKeys = /^(?:name|label|groupLabel|organizationName|customerName|callerName|modelName|metaModelName|projectName|userName|displayName|industry|application|channel)$/
  const copy = (item, key = '', owner = {}) => {
    const semanticLabel = key === 'label' && !owner.id && (!owner.seriesKey || ['ALL','all','total'].includes(owner.seriesKey)) &&
      !owner.customerTenantId && !owner.modelId && !owner.userId &&
      !owner.groupKey?.customerTenantId && !owner.groupKey?.modelId &&
      !owner.groupKey?.userId
    if (protectBusiness && typeof item === 'string' && businessKeys.test(key) && !semanticLabel && item) {
      const marker = `\uE100${values.length}\uE101`
      values.push(item)
      return marker
    }
    if (Array.isArray(item)) return item.map(child => copy(child))
    if (item && typeof item === 'object') return Object.fromEntries(
      Object.entries(item).map(([name, child]) => [name, copy(child, name, item)])
    )
    return item
  }
  return {
    value: copy(value),
    restore: html => String(html).replace(/\uE100(\d+)\uE101/g,
      (_, index) => escapeHTML(values[Number(index)] ?? ''))
  }
}

// Scan complete HTML tags (including quoted > characters), never data-* values.
export function localizeWorkspaceHtml(html, locale = 'zh-CN') {
  if (!isEnglishLocale(locale)) return html
  let result = '', start = 0, index = 0
  while (index < html.length) {
    if (html[index] !== '<') { index++; continue }
    result += workspaceText(html.slice(start, index), locale)
    const from = index++
    let quote = ''
    while (index < html.length) {
      const char = html[index++]
      if (quote) { if (char === quote) quote = '' }
      else if (char === '"' || char === "'") quote = char
      else if (char === '>') break
    }
    const tag = html.slice(from, index).replace(
      /(\s)(title|aria-label|placeholder|alt|data-label|data-help)=("[^"]*"|'[^']*')/g,
      (_, space, name, quoted) => {
        const translated = workspaceText(quoted.slice(1, -1), locale)
        const safe = quoted[0] === '"' ? translated.replace(/"/g, '&quot;') : translated.replace(/'/g, '&#39;')
        return `${space}${name}=${quoted[0]}${safe}${quoted[0]}`
      }
    )
    result += tag
    start = index
  }
  return result + workspaceText(html.slice(start), locale)
}
