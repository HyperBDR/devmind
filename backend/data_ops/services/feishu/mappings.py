from __future__ import annotations

import os
from copy import deepcopy

from django.db.utils import OperationalError, ProgrammingError


BITABLE_SOURCES = {
    "domestic": {
        "name": "项目跟踪管理",
        "tables": {
            "contracts_old": {
                "model": "contract",
                "name": "合同清单2025.3之前",
                "expected_min_records": 1,
                "field_map": {
                    "合同编号": "contract_number",
                    "签约对方公司名": "customer_name",
                    "万博-签约主体": "signing_entity",
                    "合同总金额": "total_amount",
                    "万博签约人": "sales_person",
                    "合同生效日期": "signing_date",
                    "合同到期日期": "service_end",
                    "合同类型": "signing_type",
                    "合同类型二级分类": "contract_sub_type",
                    "项目归属地": "region",
                    "签约方性质": "channel_type",
                    "合同标的": "product_category",
                    "到期情况": "expiry_status",
                },
                "expected_fields": [
                    "合同编号",
                    "签约对方公司名",
                    "万博-签约主体",
                    "合同总金额",
                    "万博签约人",
                    "合同生效日期",
                    "合同到期日期",
                ],
            },
            "contracts": {
                "model": "contract",
                "name": "合同清单2025.3之后",
                "expected_min_records": 1,
                "field_map": {
                    "合同编号": "contract_number",
                    "签约对方全称": "customer_name",
                    "签约主体": "signing_entity",
                    "模式": "order_platform",
                    "万博签约人": "sales_person",
                    "地区": "region",
                    "币种": "currency",
                    "货币单位": "currency",
                    "合同总金额": "total_amount",
                    "产品大类": "product_category",
                    "合同标的类别": "product_category",
                    "合同类型": "signing_type",
                    "合同大类": "signing_type",
                    "合同生效日期": "signing_date",
                    "服务开始日": "service_start",
                    "合同到期日期": "service_end",
                    "合同归档类型": "filing_type",
                    "合同二级标识": "contract_sub_type",
                    "到期情况": "status",
                    "合同归属": "expiry_status",
                },
                "expected_fields": [
                    "合同编号",
                    "签约对方全称",
                    "签约主体",
                    "合同总金额",
                    "万博签约人",
                    "合同生效日期",
                    "合同到期日期",
                ],
            },
            "sales_records": {
                "model": "sales_record",
                "name": "海外-落地项目（License）",
                "expected_min_records": 1,
                "field_map": {
                    "项目名称": "project_name",
                    "PO#": "po_number",
                    "国家地区": "region",
                    "购买产品类型": "product_type",
                    "合计金额": "total_amount_usd",
                    "合计金额（统一汇率）": "total_amount_usd",
                    "分配时间": "allocation_date",
                    "授权管理平台到期时间": "expiry_date",
                    "订单类型": "order_type",
                    "项目进度状态": "status",
                    "项目负责人 (人员 )": "sales_person",
                },
                "expected_fields": [
                    "项目名称",
                    "PO#",
                    "国家地区",
                    "购买产品类型",
                    "合计金额",
                    "分配时间",
                    "授权管理平台到期时间",
                ],
            },
            "domestic_ledger_receipt": {
                "model": "domestic_ledger_receipt",
                "name": "销售产品&服务收入台账",
                "expected_min_records": 1,
                "field_map": {
                    "收支类型": "ledger_type",
                    "客户名称": "customer_name",
                    "项目名称": "project_name",
                    "订单编号": "order_number",
                    "合同/订单签订日期": "signing_date",
                    "销售负责人": "sales_person",
                    "万博提交人": "sales_person",
                    "万博签约主体": "signing_entity",
                    "货币单位": "currency",
                    "应收合同总金额": "total_contract_amount",
                    "单次应收金额": "single_receive_amount",
                    "开票金额": "invoice_amount",
                    "回款金额": "payment_received",
                    "回款进度": "payment_progress",
                    "回款状态": "payment_status",
                    "回款情况": "payment_situation",
                    "到账时间": "receipt_time",
                    "开票日期": "invoice_date",
                    "应回款时间": "expected_payment_date",
                    "license数量": "license_quantity",
                    "license单价": "license_unit_price",
                    "付款条款": "payment_terms",
                    "税率": "tax_rate",
                    "待回款": "outstanding",
                    "年份": "year",
                    "销售模式": "sales_mode",
                    "采购产品": "purchase_product",
                    "项目编号2025.3之后": "project_code",
                    "项目编号2025.3之前": "project_code",
                    "其它备注": "remarks",
                },
                "expected_fields": [
                    "客户名称",
                    "项目名称",
                    "万博提交人",
                    "应收合同总金额",
                    "回款金额",
                    "待回款",
                    "应回款时间",
                ],
            },
            "domestic_ledger_payment": {
                "model": "domestic_ledger_payment",
                "name": "项目采购支出台账",
                "expected_min_records": 1,
                "field_map": {
                    "收支类型": "ledger_type",
                    "付款项": "payment_item",
                    "万博付款方主体": "payment_party",
                    "收款方名称": "payee_name",
                    "付款金额": "payment_amount",
                    "货币单位": "currency",
                    "签订模式": "signing_mode",
                    "合同/订单日期": "signing_date",
                    "关联上家名": "counterparty_name",
                    "备注": "remarks",
                },
                "expected_fields": [
                    "付款项",
                    "万博付款方主体",
                    "收款方名称",
                    "付款金额",
                    "货币单位",
                    "合同/订单日期",
                ],
            },
            "project_init": {
                "model": "project_init",
                "name": "项目立项",
                "expected_min_records": 1,
                "field_map": {
                    "项目编号": "project_code",
                    "国内/国际": "domestic_international",
                    "项目客户全称": "customer_full_name",
                    "OA立项时间": "oa_initiation_date",
                    "项目名称": "project_name",
                    "项目简述": "project_description",
                    "项目销售": "sales_person",
                    "销售产品": "sales_products",
                    "预估金额": "estimated_amount",
                    "货币单位": "currency",
                    "签约方性质": "signing_party_type",
                    "最终客户名称": "enduser_customer",
                    "合同关联-2025.3之后": "contract_link",
                },
                "expected_fields": [
                    "项目编号",
                    "国内/国际",
                    "项目客户全称",
                    "OA立项时间",
                    "项目名称",
                    "项目销售",
                    "预估金额",
                ],
            },
        },
    },
    "oversea": {
        "name": "海外-落地项目汇总 Overseas Orders",
        "tables": {
            "oversea_projects": {
                "model": "oversea_project",
                "name": "海外-落地项目统计",
                "expected_min_records": 1,
                "field_map": {
                    "项目名称": "project_name",
                    "项目状态": "status",
                    "项目进度状态": "status",
                    "PO#": "po_number",
                    "国家": "country",
                    "国家地区": "country",
                    "收款通道": "payment_channel",
                    "支付渠道": "payment_channel",
                    "签约客户": "signing_customer",
                    "购买产品类型": "product_type",
                    "产品型号": "product_spec",
                    "产品规格": "product_spec",
                    "订单日期": "order_date",
                    "下单时间": "order_date",
                    "订单年份": "order_year",
                    "订单月份": "order_month",
                    "合同总金额": "total_amount",
                    "合计金额": "total_amount",
                    "币种": "currency",
                    "订单币种": "currency",
                    "统计口径USD": "stat_amount_usd",
                    "统计口径-USD收入": "stat_amount_usd",
                    "合计金额（统一汇率）": "stat_amount_usd",
                    "分配时间": "allocation_date",
                    "分配数量": "allocation_quantity",
                    "License工单号": "license_order_no",
                    "授权管理平台订单号": "license_order_no",
                    "华为云到期时间": "huawei_cloud_expiry",
                    "License到期时间": "license_expiry",
                    "授权管理平台到期时间": "license_expiry",
                    "时区": "timezone",
                    "License注册码": "license_reg_code",
                    "授权管理平台注册码": "license_reg_code",
                    "KooGallery用户名": "kg_username",
                    "KooGallery用户全称": "kg_full_name",
                    "最终客户": "end_customer",
                    "KooGallery邮箱": "kg_email",
                    "抄送邮箱": "cc_email",
                    "项目负责人": "project_owner",
                    "项目负责人 (人员 )": "project_owner",
                    "发票号": "invoice_no",
                    "付款日期": "payment_date",
                    "付款金额": "payment_amount",
                    "付款币种": "payment_currency",
                    "收款币种": "payment_currency",
                    "付款方": "payment_recipient",
                    "客户类型": "customer_type",
                    "成本归属": "cost_for",
                    "成本USD": "cost_usd",
                    "付款条款": "payment_terms",
                    "完税状态": "tax_status",
                    "Tax状态": "tax_status",
                    "税金": "tax_amount",
                    "订单类型": "order_type",
                    "验收状态": "acceptance_status",
                    "验收情况": "acceptance_status",
                    "订单状态": "order_status",
                    "订单分类": "order_category",
                    "订购类型": "order_category",
                    "客户ID": "customer_id",
                    "付款ID": "payment_id",
                    "项目子编号": "project_sub_no",
                    "备注": "remarks",
                    "税务凭证": "tax_voucher",
                },
                "expected_fields": [
                    "项目名称",
                    "项目进度状态",
                    "PO#",
                    "国家地区",
                    "签约客户",
                    "统计口径-USD收入",
                    "授权管理平台到期时间",
                    "项目负责人 (人员 )",
                ],
            },
        },
    },
    "oversea_stats": {
        "name": "海外结算",
        "tables": {
            "oversea_settlements": {
                "model": "oversea_settlement",
                "name": "海外→国内商务-订单情况",
                "expected_min_records": 1,
                "field_map": {
                    "项目名称-英文": "project_name_en",
                    "项目名-中文": "project_name_cn",
                    "地区": "region",
                    "项目类别": "project_category",
                    "项目编号": "project_code",
                    "项目进度情况": "project_progress",
                    "To do & Notes": "todo_notes",
                    "项目概述": "project_overview",
                    "最终客户": "final_customer",
                    "集成商": "integrator",
                    "华为的结算方": "huawei_settlement_party",
                    "售卖商品": "selling_products",
                    "实际收入金额": "actual_revenue",
                    "单位": "unit",
                    "海外初始报价": "overseas_initial_quote",
                    "初始报价单位": "initial_quote_unit",
                    "预估汇率": "estimated_exchange_rate",
                    "预估收入": "estimated_revenue",
                    "预估收入单位": "estimated_revenue_unit",
                    "实际收入-预估 差额": "revenue_diff",
                    "差额单位": "revenue_diff_unit",
                    "差额原因": "revenue_diff_reason",
                    "应收金额": "receivable_amount",
                    "已收金额": "received_amount",
                    "货币单位": "currency",
                    "爱数下家过单费（分摊估算）": (
                        "aisun_sub_fee_estimate"
                    ),
                    "回款日期": "payment_date",
                    "华为向过单商下单时间": "huawei_order_time",
                    "华为预计支付时间": "huawei_est_payment_time",
                    "过单商预计付款时间": (
                        "transit_merchant_est_payment_time"
                    ),
                    "Master-Overseas 关联": "master_overseas_link",
                    "爱数下家过单费 关联": "aisun_sub_fee_link",
                    "授权发放情况": "authorization_status_link",
                    "原始报价材料": "has_initial_quote_attachment",
                    "过单商合同附件": "has_contract_attachment",
                },
                "expected_fields": [
                    "项目名称-英文",
                    "项目名-中文",
                    "地区",
                    "项目编号",
                    "实际收入金额",
                    "应收金额",
                    "已收金额",
                    "货币单位",
                ],
            },
        },
    },
}


DEFAULT_REQUIRED_PERMISSIONS = [
    "bitable:app",
    "bitable:app:readonly",
    "bitable:record:readonly",
    "bitable:field:readonly",
]

ACTIVE_SOURCE_KEYS = {"domestic"}

SOURCE_APP_TOKEN_ENV_NAMES = {
    "domestic": (
        "DATA_OPS_FEISHU_DOMESTIC_APP_TOKEN",
        "DATA_OPS_FEISHU_BITABLE_APP_TOKEN",
    ),
}


def iter_default_bitable_tables():
    for source_key, source in BITABLE_SOURCES.items():
        if source_key not in ACTIVE_SOURCE_KEYS:
            continue
        for table_key, table in source["tables"].items():
            yield source_key, source, table_key, table


def iter_default_collection_configs():
    for source_key, source, table_key, table in iter_default_bitable_tables():
        yield {
            "source_key": source_key,
            "table_key": table_key,
            "source_name": source.get("name", ""),
            "table_name": table.get("name", ""),
            "app_token": default_source_app_token(source_key),
            "table_id": "",
            "expected_min_records": table.get("expected_min_records"),
            "required_permissions": list(DEFAULT_REQUIRED_PERMISSIONS),
        }


def default_source_app_token(source_key: str) -> str:
    for env_name in SOURCE_APP_TOKEN_ENV_NAMES.get(source_key, ()):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return ""


def resolve_default_table(source_key: str, table_key: str) -> tuple | None:
    if source_key not in ACTIVE_SOURCE_KEYS:
        return None
    source = BITABLE_SOURCES.get(source_key)
    if not source:
        return None
    table = source.get("tables", {}).get(table_key)
    if not table:
        return None
    return source_key, source, table_key, table


def iter_bitable_tables(
    *,
    include_disabled: bool = False,
    source_filter: str | None = None,
    table_filter: str | None = None,
):
    configs, loaded = _load_config_map()
    for source_key, source, table_key, table in iter_default_bitable_tables():
        if source_filter and source_key != source_filter:
            continue
        if table_filter and table_key != table_filter:
            continue

        config = configs.get((source_key, table_key))
        if (
            loaded
            and config
            and not config.is_enabled
            and not include_disabled
        ):
            continue

        resolved_source = deepcopy(source)
        resolved_table = deepcopy(table)
        resolved_source["app_token"] = default_source_app_token(source_key)
        resolved_table["table_id"] = ""
        if config:
            resolved_source["app_token"] = config.app_token
            resolved_source["name"] = config.source_name or source.get(
                "name",
                "",
            )
            resolved_table["table_id"] = config.table_id
            resolved_table["name"] = config.table_name or table.get(
                "name",
                "",
            )
            resolved_table["expected_min_records"] = (
                config.expected_min_records
            )
            resolved_table["required_permissions"] = (
                config.required_permissions
            )
        yield source_key, resolved_source, table_key, resolved_table


def _load_config_map() -> tuple[dict, bool]:
    try:
        from data_ops.models import FeishuBitableCollectionConfig

        configs = FeishuBitableCollectionConfig.objects.all()
        return {
            (config.source_key, config.table_key): config
            for config in configs
        }, True
    except (OperationalError, ProgrammingError):
        return {}, False
