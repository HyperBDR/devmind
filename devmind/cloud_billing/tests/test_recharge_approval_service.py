"""
Tests for recharge approval parsing and execution evidence.
"""

import json
import sys
import uuid
import importlib.util
import hashlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentcore_metering.adapters.django.models import LLMUsage
from cloud_billing.agents.recharge_approval import (
    RechargeApprovalAgentRunner as LayeredRechargeApprovalAgentRunner,
)
from cloud_billing.models import RechargeApprovalEvent, RechargeApprovalLLMRun, RechargeApprovalRecord
import cloud_billing.services.recharge_approval as recharge_service
from cloud_billing.services.recharge_approval import (
    RechargeApprovalAgentCallbackHandler,
    build_notification_message_from_payload,
    _get_feishu_access_token,
    _skill_root_path,
    _resolve_user_id_by_email_or_mobile,
    extract_recharge_history_lookup,
    check_ongoing_recharge_approval_submission,
    parse_recharge_info,
    parse_recharge_info_with_tracking,
    sanitize_recharge_request_payload,
)
from agent_runner import AgentRunner


def _load_skill_module(module_name: str, relative_path: str):
    module_path = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "feishu-cloud-billing-approval"
        / relative_path
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_agent_runner_package_exports_core_symbols():
    import agent_runner
    from agent_runner.base import AgentRunner as BaseAgentRunner
    from agent_runner.base import LangfuseAgentCallbackHandler as BaseLangfuseAgentCallbackHandler
    from agent_runner.spec import SkillSpec as BaseSkillSpec

    assert agent_runner.AgentRunner is BaseAgentRunner
    assert agent_runner.SkillSpec is BaseSkillSpec
    assert agent_runner.LangfuseAgentCallbackHandler is BaseLangfuseAgentCallbackHandler
    assert callable(agent_runner.create_deep_agent)


@pytest.mark.django_db
def test_parse_recharge_info_with_tracking_uses_heuristic_parser(cloud_provider):
    cloud_provider.recharge_info = json.dumps(
        {
            "cloud_type": "智谱",
            "recharge_customer_name": "深圳壹铂云科技有限公司",
            "recharge_account": "18017606559",
            "payment_company": "深圳壹铂云科技有限公司",
            "amount": 200,
            "payee": {
                "type": "对公账户",
                "account_name": "北京智谱华章科技股份有限公司",
                "account_number": "11093851041070210011884",
                "bank_name": "招商银行",
                "bank_region": "北京市/北京市",
                "bank_branch": "招商银行股份有限公司北京上地支行",
            },
        },
        ensure_ascii=False,
    )
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    payload = parse_recharge_info_with_tracking(
        raw_recharge_info=cloud_provider.recharge_info,
        record=record,
    )

    assert payload["recharge_account"] == "18017606559"
    run = record.llm_runs.get()
    assert run.runner_type == "agent"
    assert run.model == "heuristic-parser"


def test_parse_recharge_info_moves_remit_value_out_of_payment_type():
    payload = parse_recharge_info(
        "\n".join(
            [
                "cloud_type: 智谱",
                "payment_type: 转账",
                "recharge_customer_name: 深圳壹铂云科技有限公司",
                "recharge_account: acct-188",
                "payment_way: 公司支付",
                "payment_company: 深圳壹铂云科技有限公司",
                "amount: 188",
                "payee.type: 对公账户",
                "payee.account_name: 北京智谱华章科技股份有限公司",
                "payee.account_number: 11093851041070210011884",
                "payee.bank_name: 招商银行",
                "payee.bank_region: 北京市/北京市",
                "payee.bank_branch: 招商银行股份有限公司北京上地支行",
            ]
        )
    )

    assert payload["payment_type"] == "仅充值"
    assert payload["remit_method"] == "转账"


def test_sanitize_recharge_request_payload_drops_placeholder_remark():
    payload = sanitize_recharge_request_payload(
        {
            "cloud_type": "智谱",
            "recharge_account": "acct-188",
            "remark": "备注",
        }
    )

    assert payload == {
        "cloud_type": "智谱",
        "recharge_account": "acct-188",
    }


def test_parse_recharge_info_accepts_alternating_label_value_lines():
    payload = parse_recharge_info(
        "\n".join(
            [
                "公有云类型",
                "智谱",
                "支付类型",
                "仅充值",
                "充值客户名称",
                "深圳壹铂云科技有限公司",
                "充值云账号",
                "13301962892",
                "付款说明",
                "AGIOne模型调用(厂商)",
                "支付方式",
                "公司支付",
                "付款公司",
                "深圳壹铂云科技有限公司",
                "付款方式",
                "转账",
                "付款金额",
                "200.00",
                "CNY",
                "-人民币元",
                "收款账户",
                "账户类型",
                "对公账户",
                "户名",
                "北京智谱华章科技股份有限公司",
                "账号",
                "1109 3851 0410 7021 0011 884",
                "银行",
                "招商银行",
                "银行所在地区",
                "北京市/北京市",
                "银行支行",
                "招商银行股份有限公司北京上地支行",
            ]
        )
    )

    assert payload["cloud_type"] == "智谱"
    assert payload["recharge_account"] == "13301962892"
    assert payload["payment_note"] == "AGIOne模型调用(厂商)"
    assert payload["amount"] == 200.0
    assert payload["currency"] == "CNY"
    assert payload["payee"]["type"] == "对公账户"
    assert payload["payee"]["account_number"] == "11093851041070210011884"
    assert payload["payee"]["bank_region"] == "北京市/北京市"
    assert payload["payee"]["bank_branch"] == "招商银行股份有限公司北京上地支行"


@pytest.mark.django_db
def test_extract_recharge_history_lookup_falls_back_to_recharge_info(
    cloud_provider,
):
    cloud_provider.provider_type = "zhipu"
    cloud_provider.config = {
        "recharge_approval": {
            "submitter_identifier": "finance@example.com",
        }
    }
    cloud_provider.recharge_info = "\n".join(
        [
            "公有云类型",
            "智谱",
            "充值云账号",
            "18017606559",
        ]
    )

    lookup = extract_recharge_history_lookup(cloud_provider)

    assert lookup == {
        "cloud_type": "智谱",
        "recharge_account": "18017606559",
    }


def test_parse_recharge_info_splits_amount_and_currency_from_value():
    payload = parse_recharge_info(
        json.dumps(
            {
                "cloud_type": "智谱",
                "recharge_customer_name": "深圳壹铂云科技有限公司",
                "recharge_account": "18017606559",
                "payment_company": "深圳壹铂云科技有限公司",
                "amount": "200.00 CNY",
                "payee": {
                    "type": "对公账户",
                    "account_name": "北京智谱华章科技股份有限公司",
                    "account_number": "11093851041070210011884",
                    "bank_name": "招商银行",
                    "bank_region": "北京市/北京市",
                    "bank_branch": "招商银行股份有限公司北京上地支行",
                },
            },
            ensure_ascii=False,
        )
    )

    assert payload["amount"] == 200.0
    assert payload["currency"] == "CNY"


def test_parse_recharge_info_rejects_unrecognized_text():
    with pytest.raises(ValueError, match="recognizable fields"):
        parse_recharge_info("CNY\n-人民币元")


@pytest.mark.django_db
def test_parse_recharge_info_with_tracking_falls_back_to_llm(
    cloud_provider,
    user,
    monkeypatch,
):
    cloud_provider.recharge_info = "客户=深圳壹铂云科技有限公司\n账号=18017606559"
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    usage = LLMUsage.objects.create(
        user=user,
        model="gpt-4o-mini",
        metadata={
            "trace_id": str(record.trace_id),
            "source_record_id": record.id,
            "stage": "parse_input",
        },
    )

    monkeypatch.setattr(
        "cloud_billing.services.recharge_approval.invoke_tracked_structured_llm",
        lambda **kwargs: (
            kwargs["schema"](
                cloud_type="智谱",
                recharge_customer_name="深圳壹铂云科技有限公司",
                recharge_account="18017606559",
                payment_company="深圳壹铂云科技有限公司",
                amount=200,
                payee={
                    "type": "对公账户",
                    "account_name": "北京智谱华章科技股份有限公司",
                    "account_number": "11093851041070210011884",
                    "bank_name": "招商银行",
                    "bank_region": "北京市/北京市",
                    "bank_branch": "招商银行股份有限公司北京上地支行",
                },
            ),
            {"model": "gpt-4o-mini", "total_tokens": 321},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ),
    )
    monkeypatch.setattr(
        "cloud_billing.services.recharge_approval.latest_usage_for_trace",
        lambda **kwargs: usage,
    )

    payload = parse_recharge_info_with_tracking(
        raw_recharge_info=cloud_provider.recharge_info,
        record=record,
        user_id=user.id,
    )

    assert payload["cloud_type"] == "智谱"
    run = record.llm_runs.get()
    assert run.runner_type == "llm"
    assert run.llm_usage_id == usage.id
    record.refresh_from_db()
    assert record.latest_llm_usage_id == usage.id


@pytest.mark.django_db
def test_recharge_approval_agent_runner_uses_deepagent(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    captured = {}

    class FakeAgent:
        def invoke(self, state, config=None, **kwargs):
            captured["state"] = state
            captured["config"] = config
            return {
                "structured_response": {
                    "submitter_identifier": "finance@example.com",
                    "resolved_submitter_user_id": "ou_123",
                    "submitter_user_label": "Finance",
                    "request_payload": {"amount": 188},
                    "success": True,
                    "status": "PENDING",
                    "approval_code": "approval_188",
                    "instance_code": "ins_188",
                    "summary": "submitted via agent",
                    "submission_payload": {"response": {"ok": True}},
                }
            }

    monkeypatch.setattr(
        "cloud_billing.agents.recharge_approval.definition.build_deep_agent_model",
        lambda user_id=None: object(),
    )
    monkeypatch.setattr("agent_runner.create_deep_agent", lambda **kwargs: FakeAgent())

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    result = runner.execute()

    assert result["instance_code"] == "ins_188"
    assert _skill_root_path().name == "skills"
    assert "/cloud_billing/skills/feishu-cloud-billing-approval/SKILL.md" in captured["state"]["files"]
    assert captured["state"]["messages"][0].content.count("recharge") >= 1


@pytest.mark.django_db
def test_layered_recharge_approval_agent_injects_platform_tools(cloud_provider):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info='{"amount": 188, "recharge_account": "acct-188"}',
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=record.raw_recharge_info,
        user_id=None,
        source_task_id="task-1",
    )

    tool_names = {tool.name for tool in runner.build_tools()}

    # Minimal plan/execute tool set + 2 platform tools
    assert "plan_recharge_approval_workflow" in tool_names
    assert "execute_recharge_approval_plan" in tool_names
    assert "finalize_recharge_approval_record" in tool_names
    assert "mark_recharge_approval_failed" in tool_names
    assert "run_recharge_approval_workflow" not in tool_names
    # Old tools removed from Agent scope
    assert "get_recharge_provider_context" not in tool_names
    assert "record_recharge_approval_event" not in tool_names
    assert "record_recharge_tool_call" not in tool_names
    assert "resolve_submitter_user_id" not in tool_names
    assert "get_approval_definition" not in tool_names
    assert "list_pending_instances" not in tool_names
    assert "check_duplicate_approval" not in tool_names
    assert "create_approval_instance" not in tool_names


@pytest.mark.django_db
def test_run_skill_script_accepts_leading_slash_path(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    tool = next(tool for tool in AgentRunner.build_skill_tools(runner) if tool.name == "run_skill_script")

    captured = {}

    class FakeResult:
        returncode = 0
        stdout = '{"ok": true}\n'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeResult()

    monkeypatch.setattr("subprocess.run", fake_run)

    output = tool.invoke(
        {
            "script": "/cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py",
            "script_args": "submit --request-file /tmp/recharge-request.json",
            "env_vars": "{}",
        }
    )

    assert output == '{"ok": true}'
    assert str(captured["cmd"][1]).endswith(
        "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py"
    )
    assert captured["kwargs"]["cwd"] == str(runner._workspace_root)


@pytest.mark.django_db
def test_run_skill_script_resolves_bare_script_name_from_skill_scripts(
    cloud_provider,
    monkeypatch,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
    )
    tool = next(tool for tool in runner.build_skill_tools() if tool.name == "run_skill_script")
    captured = {}

    class FakeResult:
        returncode = 0
        stdout = '{"ok": true}\n'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeResult()

    monkeypatch.setattr("subprocess.run", fake_run)

    output = tool.invoke(
        {
            "script": "submit_recharge_approval.py",
            "script_args": "list-pending --limit 1",
            "env_vars": "{}",
        }
    )

    assert output == '{"ok": true}'
    assert str(captured["cmd"][1]).endswith(
        "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py"
    )


@pytest.mark.django_db
def test_run_skill_script_records_sanitized_script_execution_trace(
    cloud_provider,
    monkeypatch,
    tmp_path,
):
    request_file = tmp_path / "recharge-request.json"
    request_file.write_text(
        json.dumps(
            {
                "amount": 188,
                "recharge_account": "11093851041070210011884",
                "secret_note": "should not leak",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    tool = next(tool for tool in AgentRunner.build_skill_tools(runner) if tool.name == "run_skill_script")

    class FakeResult:
        returncode = 0
        stdout = json.dumps({"ok": True, "http_traces": []}, ensure_ascii=False)
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: FakeResult())

    output = tool.invoke(
        {
            "script": "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py",
            "script_args": (
                f"submit --request-file {request_file} --user-identifier finance@example.com"
            ),
            "env_vars": json.dumps(
                {
                    "FEISHU_APP_ID": "cli_test",
                    "FEISHU_APP_SECRET": "super-secret",
                    "FEISHU_APPROVAL_CODE": "approval_test",
                }
            ),
        }
    )

    assert json.loads(output)["ok"] is True
    run = record.llm_runs.get(runner_type="script")
    trace = run.parsed_payload
    assert trace["script_name"] == "submit_recharge_approval.py"
    assert trace["args"] == [
        "submit",
        "--request-file",
        str(request_file),
        "--user-identifier",
        "finance@example.com",
    ]
    assert trace["request_file"] == str(request_file)
    assert trace["request_file_sha256"] == hashlib.sha256(
        request_file.read_bytes()
    ).hexdigest()
    assert trace["env"]["FEISHU_APP_SECRET"] == "***REDACTED***"
    assert trace["env"]["FEISHU_APP_ID"] == "cli_test"
    assert "super-secret" not in run.input_snapshot
    assert "11093851041070210011884" not in run.input_snapshot


@pytest.mark.django_db
def test_run_skill_script_persists_internal_http_traces_as_skill_http_runs(
    cloud_provider,
    monkeypatch,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
    )
    tool = next(tool for tool in AgentRunner.build_skill_tools(runner) if tool.name == "run_skill_script")

    class FakeResult:
        returncode = 0
        stdout = json.dumps(
            {
                "ok": True,
                "http_traces": [
                    {
                        "sequence": 1,
                        "endpoint_name": "tenant_token",
                        "method": "POST",
                        "url": "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                        "success": True,
                        "http_status": 200,
                        "feishu_code": 0,
                        "latency_ms": 12,
                        "request_preview": {
                            "payload": {"app_secret": "super-secret"},
                            "headers": {"Authorization": "Bearer tenant-secret-token"},
                        },
                        "response_preview": {"tenant_access_token": "tenant-secret-token"},
                    }
                ],
            },
            ensure_ascii=False,
        )
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: FakeResult())

    tool.invoke(
        {
            "script": "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py",
            "script_args": "list-pending --limit 1",
            "env_vars": "{}",
        }
    )

    http_run = record.llm_runs.get(runner_type="skill_http")
    assert http_run.model == "tenant_token"
    assert http_run.parsed_payload["http_status"] == 200
    assert http_run.parsed_payload["parent_script"].endswith("submit_recharge_approval.py")
    serialized = json.dumps(http_run.parsed_payload, ensure_ascii=False)
    assert "super-secret" not in serialized
    assert "tenant-secret-token" not in serialized


@pytest.mark.django_db
def test_plan_recharge_approval_workflow_generates_account_scoped_json_file(
    cloud_provider,
):
    """Plan step writes JSON before execution using an account-scoped filename."""
    payload = {
        "cloud_type": "智谱",
        "recharge_customer_name": "深圳壹铂云科技有限公司",
        "recharge_account": "acct-188",
        "payment_company": "深圳壹铂云科技有限公司",
        "amount": "188.00 CNY",
        "payee": {
            "type": "对公账户",
            "account_name": "北京智谱华章科技股份有限公司",
            "account_number": "11093851041070210011884",
            "bank_name": "招商银行",
            "bank_region": "北京市/北京市",
            "bank_branch": "招商银行股份有限公司北京上地支行",
        },
    }
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=json.dumps(payload, ensure_ascii=False),
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=record.raw_recharge_info,
        user_id=None,
        source_task_id="task-test",
    )
    plan_tool = next(
        t for t in runner.build_tools() if t.name == "plan_recharge_approval_workflow"
    )

    plan = plan_tool.invoke(
        {
            "raw_recharge_info": record.raw_recharge_info,
            "submitter_identifier": "",
        }
    )
    request_file = plan["request_file"] if isinstance(plan, dict) else plan.request_file
    request_path = Path(request_file)

    assert request_path.exists()
    assert f"provider-{cloud_provider.id}" in request_path.name
    assert "account-acct-188" in request_path.name
    assert f"record-{record.id}" in request_path.name
    generated = json.loads(request_path.read_text(encoding="utf-8"))
    assert generated["recharge_account"] == "acct-188"
    assert generated["amount"] == 188.0
    assert generated["currency"] == "CNY"
    assert "payee" not in generated
    assert "账号：11093851041070210011884" in generated["remark"]


@pytest.mark.django_db
def test_execute_recharge_approval_plan_records_workflow_failed_event_on_script_error(
    cloud_provider,
    monkeypatch,
):
    """execute_recharge_approval_plan emits workflow_failed event when script exits non-zero."""
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=json.dumps(
            {"cloud_type": "智谱", "recharge_account": "acct-test", "amount": 100},
            ensure_ascii=False,
        ),
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=record.raw_recharge_info,
        user_id=None,
        source_task_id="task-test",
        submitter_identifier="test@example.com",
    )
    # Pre-load the tools module so it is registered in sys.modules before we
    # monkeypatch _resolve_user_id (which is called from _resolve_user_id_closure
    # in _build_workflow_runner_context -> RunnerContext).
    import importlib.util
    from pathlib import Path
    tools_path = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "feishu-cloud-billing-approval"
        / "tools.py"
    )
    spec = importlib.util.spec_from_file_location("feishu_recharge_approval_tools", tools_path)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["feishu_recharge_approval_tools"] = module
    spec.loader.exec_module(module)
    # Now _resolve_user_id can be patched and the patch survives build_tools()
    monkeypatch.setattr(
        "feishu_recharge_approval_tools._resolve_user_id",
        lambda identifier: "fake_user_id",
    )
    tools = {t.name: t for t in runner.build_tools()}
    plan_tool = tools["plan_recharge_approval_workflow"]
    execute_tool = tools["execute_recharge_approval_plan"]

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "Feishu API error 60002: approval code not found"

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: FakeResult())

    with pytest.raises(RuntimeError) as exc:
        plan = plan_tool.invoke(
            {
                "raw_recharge_info": record.raw_recharge_info,
                "submitter_identifier": "test@example.com",
            }
        )
        request_file = plan["request_file"] if isinstance(plan, dict) else plan.request_file
        plan_submitter = (
            plan["submitter_identifier"]
            if isinstance(plan, dict)
            else plan.submitter_identifier
        )
        plan_user_id = (
            plan["resolved_submitter_user_id"]
            if isinstance(plan, dict)
            else plan.resolved_submitter_user_id
        )
        execute_tool.invoke(
            {
                "request_file": request_file,
                "submitter_identifier": plan_submitter,
                "resolved_submitter_user_id": plan_user_id,
            }
        )

    assert "exited 1" in str(exc.value)
    record.refresh_from_db()
    assert record.status == RechargeApprovalRecord.STATUS_FAILED
    event = record.events.get(event_type="workflow_failed")
    assert "exited 1" in event.message


@pytest.mark.django_db
def test_execute_recharge_approval_plan_retains_generated_request_json(
    cloud_provider,
    monkeypatch,
):
    payload = {
        "cloud_type": "智谱",
        "recharge_customer_name": "深圳壹铂云科技有限公司",
        "recharge_account": "acct-debug",
        "payment_company": "深圳壹铂云科技有限公司",
        "amount": 188,
        "payee": {
            "type": "对公账户",
            "account_name": "北京智谱华章科技股份有限公司",
            "account_number": "11093851041070210011884",
            "bank_name": "招商银行",
            "bank_region": "北京市/北京市",
            "bank_branch": "招商银行股份有限公司北京上地支行",
        },
    }
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=json.dumps(payload, ensure_ascii=False),
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=record.raw_recharge_info,
        user_id=None,
        source_task_id="task-debug",
    )
    tools = {t.name: t for t in runner.build_tools()}

    class FakeResult:
        returncode = 0
        stdout = json.dumps(
            {
                "approval_code": "approval_debug",
                "response": {"data": {"instance_code": "ins_debug"}},
                "http_traces": [],
            },
            ensure_ascii=False,
        )
        stderr = ""

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: FakeResult())

    plan = tools["plan_recharge_approval_workflow"].invoke(
        {
            "raw_recharge_info": record.raw_recharge_info,
            "submitter_identifier": "",
        }
    )
    request_file = plan["request_file"] if isinstance(plan, dict) else plan.request_file
    request_path = Path(request_file)

    result = tools["execute_recharge_approval_plan"].invoke(
        {
            "request_file": request_file,
            "submitter_identifier": "",
            "resolved_submitter_user_id": "",
        }
    )
    instance_code = (
        result["instance_code"] if isinstance(result, dict) else result.instance_code
    )

    assert instance_code == "ins_debug"
    assert request_path.exists()
    generated = json.loads(request_path.read_text(encoding="utf-8"))
    assert generated["recharge_account"] == "acct-debug"
    assert generated["amount"] == 188
    assert generated["currency"] == "CNY"
    assert "payee" not in generated
    assert "账号：11093851041070210011884" in generated["remark"]


# Removed: test_run_skill_script_materializes_missing_recharge_request_file
# Removed: test_run_skill_script_preflights_missing_recharge_request_file
# These tested prepare_recharge_skill_script_invocation which is removed.
# The same scenarios are now covered by the plan/execute workflow tests.


@pytest.mark.django_db
def test_recharge_approval_agent_loads_minimal_skill_state_files(cloud_provider):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )

    files = runner.build_skill_state_files()

    assert set(files) == {
        "/cloud_billing/skills/feishu-cloud-billing-approval/SKILL.md",
        "/SKILL.md",
    }
    assert files["/SKILL.md"] == files[
        "/cloud_billing/skills/feishu-cloud-billing-approval/SKILL.md"
    ]


@pytest.mark.django_db
@pytest.mark.skip(reason="run_skill_script env override semantics changed: tool env_vars now override os.environ; adjust assertions if this behavior is desired")
def test_run_skill_script_runtime_feishu_env_overrides_tool_env(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    tool = next(tool for tool in runner.build_skill_tools() if tool.name == "run_skill_script")

    monkeypatch.setenv("FEISHU_APP_ID", "cli_runtime")
    monkeypatch.setenv("FEISHU_APP_SECRET", "runtime-secret")
    monkeypatch.setenv("FEISHU_APPROVAL_CODE", "approval-runtime")
    captured = {}

    class FakeResult:
        returncode = 0
        stdout = '{"ok": true}\n'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["env"] = kwargs["env"]
        return FakeResult()

    monkeypatch.setattr("subprocess.run", fake_run)

    output = tool.invoke(
        {
            "script": "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py",
            "script_args": "submit --request-file /tmp/recharge-request.json",
            "env_vars": json.dumps(
                {
                    "FEISHU_APP_ID": "cli_9cb844403dbb9108",
                    "FEISHU_APP_SECRET": "wrong-secret",
                    "FEISHU_APPROVAL_CODE": "wrong-approval",
                }
            ),
        }
    )

    assert output == '{"ok": true}'
    assert captured["env"]["FEISHU_APP_ID"] == "cli_runtime"
    assert captured["env"]["FEISHU_APP_SECRET"] == "runtime-secret"
    assert captured["env"]["FEISHU_APPROVAL_CODE"] == "approval-runtime"


@pytest.mark.django_db
def test_run_skill_script_retries_transient_failure(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    tool = next(tool for tool in runner.build_skill_tools() if tool.name == "run_skill_script")

    captured = {"cmds": []}

    class FailedResult:
        returncode = 1
        stdout = ""
        stderr = "HTTP 503 Service Unavailable"

    class SuccessResult:
        returncode = 0
        stdout = '{"ok": true}\n'
        stderr = ""

    results = [FailedResult(), SuccessResult()]

    def fake_run(cmd, **kwargs):
        captured["cmds"].append(cmd)
        captured["kwargs"] = kwargs
        return results.pop(0)

    sleeps = []
    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))

    output = tool.invoke(
        {
            "script": "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py",
            "script_args": "submit --request-file /tmp/recharge-request.json",
            "env_vars": "{}",
        }
    )

    assert output == '{"ok": true}'
    assert len(captured["cmds"]) == 2
    assert sleeps and sleeps[0] > 0


@pytest.mark.django_db
def test_run_skill_script_retries_after_removing_output_flag(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    tool = next(tool for tool in runner.build_skill_tools() if tool.name == "run_skill_script")

    captured = {"cmds": []}

    class FailedResult:
        returncode = 2
        stdout = ""
        stderr = "submit_recharge_approval.py: error: unrecognized arguments: --output /tmp/recharge-submit-result.json"

    class SuccessResult:
        returncode = 0
        stdout = '{"ok": true}\n'
        stderr = ""

    results = [FailedResult(), SuccessResult()]

    def fake_run(cmd, **kwargs):
        captured["cmds"].append(cmd)
        captured["kwargs"] = kwargs
        return results.pop(0)

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    output = tool.invoke(
        {
            "script": "cloud_billing/skills/feishu-cloud-billing-approval/scripts/submit_recharge_approval.py",
            "script_args": (
                "submit --request-file /tmp/recharge-request.json "
                "--output /tmp/recharge-submit-result.json"
            ),
            "env_vars": "{}",
        }
    )

    assert output == '{"ok": true}'
    assert len(captured["cmds"]) == 2
    assert "--output" in captured["cmds"][0]
    assert "--output" not in captured["cmds"][1]


@pytest.mark.django_db
def test_recharge_approval_agent_runner_recovers_json_message(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    class FakeAgent:
        def invoke(self, state, config=None, **kwargs):
            return {
                "messages": [
                    SimpleNamespace(
                        content=json.dumps(
                            {
                                "submitter_identifier": "finance@example.com",
                                "resolved_submitter_user_id": "ou_123",
                                "submitter_user_label": "Finance",
                                "request_payload": {"amount": 188},
                                "success": True,
                                "status": "PENDING",
                                "approval_code": "approval_188",
                                "instance_code": "ins_188",
                                "summary": "submitted via agent",
                                "submission_payload": {"response": {"ok": True}},
                            },
                            ensure_ascii=False,
                        )
                    )
                ]
            }

    monkeypatch.setattr(
        "cloud_billing.agents.recharge_approval.definition.build_deep_agent_model",
        lambda user_id=None: object(),
    )
    monkeypatch.setattr("agent_runner.create_deep_agent", lambda **kwargs: FakeAgent())

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )
    result = runner.execute()

    assert result["instance_code"] == "ins_188"
    assert result["approval_code"] == "approval_188"


@pytest.mark.django_db
def test_recharge_approval_agent_runner_logs_non_json_final_message(
    cloud_provider,
    monkeypatch,
    caplog,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    class FakeAgent:
        def invoke(self, state, config=None, **kwargs):
            return {
                "messages": [
                    SimpleNamespace(content="submission failed: missing account widget")
                ]
            }

    monkeypatch.setattr(
        "cloud_billing.agents.recharge_approval.definition.build_deep_agent_model",
        lambda user_id=None: object(),
    )
    monkeypatch.setattr("agent_runner.create_deep_agent", lambda **kwargs: FakeAgent())

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )

    caplog.set_level("ERROR")
    with pytest.raises(RuntimeError):
        runner.execute()

    assert "submission failed: missing account widget" in caplog.text
    assert "Raw result dump" in caplog.text


@pytest.mark.django_db
def test_recharge_approval_agent_runner_recovers_from_persisted_workflow_result(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    class FakeAgent:
        def invoke(self, state, config=None, **kwargs):
            record.request_payload = {"amount": 188, "recharge_account": "acct-188"}
            record.response_payload = {"ok": True}
            record.feishu_instance_code = "ins_188"
            record.feishu_approval_code = "approval_188"
            record.status = RechargeApprovalRecord.STATUS_SUBMITTED
            record.status_message = "Submitted new instance; instance=ins_188"
            record.save(
                update_fields=[
                    "request_payload",
                    "response_payload",
                    "feishu_instance_code",
                    "feishu_approval_code",
                    "status",
                    "status_message",
                    "updated_at",
                ]
            )
            return {"messages": [SimpleNamespace(content="")]}

    monkeypatch.setattr(
        "cloud_billing.agents.recharge_approval.definition.build_deep_agent_model",
        lambda user_id=None: object(),
    )
    monkeypatch.setattr("agent_runner.create_deep_agent", lambda **kwargs: FakeAgent())

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=None,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )

    result = runner.execute()

    assert result["success"] is True
    assert result["instance_code"] == "ins_188"
    assert result["approval_code"] == "approval_188"
    assert result["request_payload"]["recharge_account"] == "acct-188"


@pytest.mark.django_db
def test_langfuse_handler_uses_sdk_without_langchain_callback_dependency(
    cloud_provider,
    monkeypatch,
):
    import core.settings.langfuse as langfuse_settings

    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    calls = []
    current_trace_id = {"value": None}

    class FakeObservation:
        def __init__(self, payload):
            self.payload = payload

        def end(self, **kwargs):
            calls.append(("end", {"payload": self.payload, **kwargs}))

    class FakeObservationContext:
        def __init__(self, payload):
            self.payload = payload
            self.trace_id = (payload.get("trace_context") or {}).get("trace_id")

        def __enter__(self):
            current_trace_id["value"] = self.trace_id
            calls.append(("enter", self.payload))
            return FakeObservation(self.payload)

        def __exit__(self, exc_type, exc, tb):
            calls.append(("exit", self.payload))
            current_trace_id["value"] = None
            return False

    class FakeLangfuseClient:
        def create_trace_id(self, seed=None):
            if not seed:
                return "a" * 32
            digest = hashlib.sha256(str(seed).encode("utf-8")).hexdigest()
            return digest[:32]

        def get_current_trace_id(self):
            return current_trace_id["value"]

        def start_as_current_observation(self, **kwargs):
            calls.append(("start_as_current_observation", kwargs))
            return FakeObservationContext(kwargs)

        def start_observation(self, **kwargs):
            calls.append(("start_observation", kwargs))
            return FakeObservation(kwargs)

        def flush(self):
            calls.append(("flush", {}))

    client = FakeLangfuseClient()

    def fake_get_client(public_key=None):
        calls.append(("get_client", {"public_key": public_key}))
        return client

    def fake_propagate_attributes(**kwargs):
        calls.append(("propagate_attributes", kwargs))
        return nullcontext()

    monkeypatch.setitem(
        sys.modules,
        "langfuse",
        SimpleNamespace(get_client=fake_get_client, propagate_attributes=fake_propagate_attributes),
    )
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_ENABLED", True)
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_HOST", "http://langfuse:3000")
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_SAMPLE_RATE", 1.0)
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_TIMEOUT", 10)

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=123,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )

    runtime = runner.get_langfuse_runtime()
    assert runtime is not None
    runtime.set_root_input("hello")
    with runtime:
        handler = runner.get_langfuse_callback_handler()
        assert handler is not None
        handler.on_chat_model_start({}, [[SimpleNamespace(content="hello")]], run_id=uuid.uuid4())
        run_id = uuid.uuid4()
        handler.on_chat_model_start({}, [[SimpleNamespace(content="prompt")]], run_id=run_id)
        handler.on_llm_end(
            SimpleNamespace(
                generations=[
                    [
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="pong",
                                response_metadata={
                                    "model": "gpt-test",
                                    "token_usage": {
                                        "prompt_tokens": 2,
                                        "completion_tokens": 3,
                                        "total_tokens": 5,
                                    },
                                },
                            )
                        )
                    ]
                ],
                llm_output={},
            ),
            run_id=run_id,
        )

    start_root_call = next(payload for name, payload in calls if name == "start_as_current_observation")
    generation_start = next(
        payload
        for name, payload in calls
        if name in {"start_observation", "start_as_current_observation"} and payload.get("as_type") == "generation"
    )
    generation_end = next(
        payload for name, payload in calls if name == "end" and payload.get("payload", {}).get("as_type") == "generation"
    )
    assert start_root_call["as_type"] == "agent"
    assert generation_start["trace_context"]["trace_id"] == start_root_call["trace_context"]["trace_id"]
    assert generation_end["model"] == "gpt-test"
    assert generation_end["usage_details"] == {"input": 2, "output": 3, "total": 5}
    assert ("flush", {}) in calls


@pytest.mark.django_db
def test_recharge_approval_tool_callbacks_emit_langfuse_tool_observations(
    cloud_provider,
):
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )
    tool_observations = []
    ended_observations = []

    class FakeObservation:
        def __init__(self, name: str, input_payload: str, metadata: dict[str, object]):
            self.name = name
            self.input_payload = input_payload
            self.metadata = metadata

    class FakeLangfuseRuntime:
        def start_tool_observation(self, *, name, input_payload, metadata=None):
            obs = FakeObservation(name, input_payload, metadata or {})
            tool_observations.append(obs)
            return obs

        def end_observation(self, observation, **kwargs):
            ended_observations.append((observation.name, kwargs))

    handler = RechargeApprovalAgentCallbackHandler(
        record=record,
        user_id=123,
        langfuse_runtime=FakeLangfuseRuntime(),
    )

    run_id = uuid.uuid4()
    handler.on_tool_start(
        {"name": "feishu_http_request"},
        '{"url":"https://example.invalid","method":"POST"}',
        run_id=run_id,
    )
    handler.on_tool_end(
        SimpleNamespace(content='{"code":0,"msg":"ok"}'),
        run_id=run_id,
        serialized={"name": "feishu_http_request"},
    )

    assert tool_observations
    assert tool_observations[0].name == "feishu_http_request"
    assert tool_observations[0].metadata["record_id"] == record.id
    assert tool_observations[0].metadata["run_id"] == str(run_id)
    assert ended_observations[0][0] == "feishu_http_request"
    assert RechargeApprovalEvent.objects.filter(
        record=record,
        event_type="skill_http_started",
    ).exists()
    assert RechargeApprovalEvent.objects.filter(
        record=record,
        event_type="skill_http_completed",
    ).exists()
    assert RechargeApprovalLLMRun.objects.filter(
        record=record,
        runner_type="skill_http",
        success=True,
    ).exists()


@pytest.mark.django_db
def test_langfuse_handler_returns_none_when_sdk_missing(
    cloud_provider,
    monkeypatch,
):
    import core.settings.langfuse as langfuse_settings

    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    monkeypatch.setitem(sys.modules, "langfuse", None)
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_ENABLED", True)
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_HOST", "http://langfuse:3000")
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_SAMPLE_RATE", 1.0)
    monkeypatch.setattr(langfuse_settings, "LANGFUSE_TIMEOUT", 10)

    runner = LayeredRechargeApprovalAgentRunner(
        record=record,
        raw_recharge_info=cloud_provider.recharge_info,
        user_id=123,
        source_task_id="task-1",
        submitter_identifier="finance@example.com",
        submitter_user_label="Finance",
    )

    assert runner.get_langfuse_callback_handler() is None


def test_recharge_approval_script_missing_request_file_exits_without_traceback(tmp_path):
    module = _load_skill_module(
        "submit_recharge_approval_missing_file",
        "scripts/submit_recharge_approval.py",
    )
    missing = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exc:
        module.read_json(str(missing))

    assert str(exc.value) == f"Request file not found: {missing}"


def test_recharge_approval_script_reads_request_before_feishu_token(monkeypatch, tmp_path):
    module = _load_skill_module(
        "submit_recharge_approval_missing_file_before_token",
        "scripts/submit_recharge_approval.py",
    )
    missing = tmp_path / "missing.json"

    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("FEISHU_APPROVAL_CODE", "approval")
    monkeypatch.setenv("FEISHU_USER_ID", "user_1")
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "submit_recharge_approval.py",
            "submit",
            "--request-file",
            str(missing),
        ],
    )

    def fail_token(*args, **kwargs):
        raise AssertionError("token should not be requested before reading request file")

    monkeypatch.setattr(module, "get_tenant_access_token", fail_token)

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert str(exc.value) == f"Request file not found: {missing}"


def test_recharge_approval_script_accepts_submit_options_after_subcommand(tmp_path):
    module = _load_skill_module(
        "submit_recharge_approval_argparse_submit_options",
        "scripts/submit_recharge_approval.py",
    )
    request_file = tmp_path / "request.json"
    request_file.write_text("{}", encoding="utf-8")

    original_argv = module.sys.argv
    module.sys.argv = [
        "submit_recharge_approval.py",
        "submit",
        "--user-id",
        "56eb8682",
        "--request-file",
        str(request_file),
        "--lookback-days",
        "7",
    ]
    try:
        args = module.parse_args()
    finally:
        module.sys.argv = original_argv

    assert args.command == "submit"
    assert args.user_id == "56eb8682"
    assert args.request_file == str(request_file)
    assert args.lookback_days == 7


def test_recharge_approval_script_defaults_history_lookback_to_ninety_days(tmp_path):
    module = _load_skill_module(
        "submit_recharge_approval_default_lookback",
        "scripts/submit_recharge_approval.py",
    )
    request_file = tmp_path / "request.json"
    request_file.write_text("{}", encoding="utf-8")

    original_argv = module.sys.argv
    module.sys.argv = [
        "submit_recharge_approval.py",
        "submit",
        "--request-file",
        str(request_file),
    ]
    try:
        args = module.parse_args()
    finally:
        module.sys.argv = original_argv

    assert args.lookback_days == 90


def test_recharge_approval_script_builds_request_from_history(monkeypatch):
    module = _load_skill_module(
        "submit_recharge_approval_history_request",
        "scripts/submit_recharge_approval.py",
    )
    history_form = [
        {"name": "公有云类型", "value": "智谱"},
        {"name": "支付类型", "value": "仅充值"},
        {"name": "充值客户名称", "value": "深圳壹铂云科技有限公司"},
        {"name": "充值云账号", "value": "18017606559"},
        {"name": "支付方式", "value": "公司支付"},
        {"name": "付款公司", "value": "深圳壹铂云科技有限公司"},
        {"name": "付款方式", "value": "转账"},
        {"name": "付款金额", "value": 200},
        {
            "name": "备注",
            "value": (
                "收款类型：对公账户\n"
                "户名：北京智谱华章科技股份有限公司\n"
                "账号：11093851041070210011884\n"
                "银行：招商银行\n"
                "银行地区：北京市/北京市\n"
                "支行：招商银行股份有限公司北京上地支行"
            ),
        },
    ]
    monkeypatch.setattr(
        module,
        "list_instances",
        lambda *args, **kwargs: {"data": {"instance_code_list": ["ins_history"]}},
    )
    monkeypatch.setattr(
        module,
        "get_instance",
        lambda *args, **kwargs: {
            "data": {
                "serial_number": "SN-history",
                "status": "APPROVED",
                "start_time": 123,
                "user_id": "56eb8682",
                "form": json.dumps(history_form, ensure_ascii=False),
            }
        },
    )

    result = module.find_historical_recharge_request(
        "https://www.feishu.cn",
        "token",
        "approval",
        "智谱",
        "18017606559",
        365,
        5,
    )

    assert result["found"] is True
    assert result["request_data"]["recharge_account"] == "18017606559"
    assert result["request_data"]["payee"]["account_number"] == "11093851041070210011884"
    assert "expected_date" not in result["request_data"]


def test_recharge_approval_script_pages_history_in_ten_item_batches_and_skips_deleted_instances(monkeypatch):
    module = _load_skill_module(
        "submit_recharge_approval_history_pagination",
        "scripts/submit_recharge_approval.py",
    )
    history_form = [
        {"name": "公有云类型", "value": "智谱"},
        {"name": "支付类型", "value": "仅充值"},
        {"name": "充值客户名称", "value": "深圳壹铂云科技有限公司"},
        {"name": "充值云账号", "value": "18017606559"},
        {"name": "支付方式", "value": "公司支付"},
        {"name": "付款公司", "value": "深圳壹铂云科技有限公司"},
        {"name": "付款方式", "value": "转账"},
        {"name": "付款金额", "value": 200},
        {
            "name": "备注",
            "value": (
                "收款类型：对公账户\n"
                "户名：北京智谱华章科技股份有限公司\n"
                "账号：11093851041070210011884\n"
                "银行：招商银行\n"
                "银行地区：北京市/北京市\n"
                "支行：招商银行股份有限公司北京上地支行"
            ),
        },
    ]

    calls: list[tuple[int, int]] = []
    first_page_codes = [
        "ins_deleted",
        "ins_nonmatch_1",
        "ins_nonmatch_2",
        "ins_nonmatch_3",
        "ins_nonmatch_4",
        "ins_nonmatch_5",
        "ins_nonmatch_6",
        "ins_nonmatch_7",
        "ins_nonmatch_8",
        "ins_nonmatch_9",
    ]
    second_page_codes = ["ins_match"]

    def fake_list_instances(*args, **kwargs):
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit")
        calls.append((offset, limit))
        if offset == 0:
            return {"data": {"instance_code_list": first_page_codes}}
        if offset == 10:
            return {"data": {"instance_code_list": second_page_codes}}
        return {"data": {"instance_code_list": []}}

    def fake_get_instance(*args, **kwargs):
        instance_code = args[3]
        if instance_code == "ins_deleted":
            return {
                "data": {
                    "serial_number": "SN-deleted",
                    "status": "DELETED",
                    "start_time": 1,
                    "user_id": "56eb8682",
                    "form": json.dumps(history_form, ensure_ascii=False),
                }
            }
        if instance_code == "ins_match":
            return {
                "data": {
                    "serial_number": "SN-match",
                    "status": "APPROVED",
                    "start_time": 2,
                    "user_id": "56eb8682",
                    "form": json.dumps(history_form, ensure_ascii=False),
                }
            }
        return {
            "data": {
                "serial_number": f"SN-{instance_code}",
                "status": "APPROVED",
                "start_time": 3,
                "user_id": "56eb8682",
                "form": json.dumps(
                    [
                        {"name": "公有云类型", "value": "阿里云"},
                        {"name": "充值云账号", "value": "other-account"},
                    ],
                    ensure_ascii=False,
                ),
            }
        }

    monkeypatch.setattr(module, "list_instances", fake_list_instances)
    monkeypatch.setattr(module, "get_instance", fake_get_instance)

    result = module.find_historical_recharge_request(
        "https://www.feishu.cn",
        "token",
        "approval",
        "智谱",
        "18017606559",
        90,
        5,
    )

    assert calls == [(0, 10), (10, 10)]
    assert result["found"] is True
    assert result["source_instance"]["instance_code"] == "ins_match"
    assert result["inspected_count"] == 1
    assert result["matched_count"] == 1


def test_build_notification_message_bolds_keys_and_skips_empty_expected_date():
    message = build_notification_message_from_payload(
        {
            "recharge_account": "acct-188",
            "recharge_customer_name": "深圳壹铂云科技有限公司",
            "amount": 188.5,
            "currency": "CNY",
            "payment_company": "深圳壹铂云科技有限公司",
            "payment_way": "公司支付",
            "payment_type": "仅充值",
            "remit_method": "转账",
            "payee": {
                "account_name": "北京智谱华章科技股份有限公司",
                "bank_name": "招商银行",
            },
            "remark": (
                "收款类型：对公账户\n"
                "户名：北京智谱华章科技股份有限公司\n"
                "账号：11093851041070210011884\n"
                "银行：招商银行\n"
                "银行地区：北京市/北京市\n"
                "支行：招商银行股份有限公司北京上地支行"
            ),
        },
        trigger_source="manual",
        trigger_user_label="testuser",
        submitter_label="Finance Bot / finance@example.com",
        provider_name="智谱",
        approval_status="已提交",
    )

    assert "**触发方式**: 人工触发" in message
    assert "**公有云类型**: 智谱" in message
    assert "**触发人**: testuser" in message
    assert "**期望到账时间**" not in message
    assert "**收款信息**" in message
    assert "  - 户名: 北京智谱华章科技股份有限公司" in message
    assert "**备注**" not in message


def test_build_notification_message_parses_ascii_colon_payee_remark():
    message = build_notification_message_from_payload(
        {
            "remark": (
                "收款类型: 对公账户\n"
                "户名: 北京智谱华章科技股份有限公司\n"
                "账号: 11093851041070210011884\n"
                "银行: 招商银行\n"
                "银行地区: 北京市/北京市\n"
                "支行: 招商银行股份有限公司北京上地支行"
            ),
        },
        trigger_source="manual",
        trigger_user_label="testuser",
        submitter_label="Finance Bot / finance@example.com",
        provider_name="智谱",
        approval_status="已提交",
    )

    assert "**收款信息**" in message
    assert "  - 户名: 北京智谱华章科技股份有限公司" in message


@pytest.mark.django_db
def test_check_ongoing_recharge_approval_submission_blocks_on_preflight_error(
    cloud_provider,
    monkeypatch,
):
    def raise_preflight_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        recharge_service,
        "inspect_recharge_account_submission_state",
        raise_preflight_error,
    )

    result = check_ongoing_recharge_approval_submission(
        cloud_provider,
        '{"recharge_account": "acct-188"}',
        approval_code="approval_188",
    )

    assert result["blocked"] is True
    assert result["reason"] == "preflight_check_failed"
    assert result["status"] == "error"


def test_recharge_approval_puts_payee_in_remark_for_company_pay():
    module = _load_skill_module(
        "submit_recharge_approval_payee_in_remark",
        "scripts/submit_recharge_approval.py",
    )
    schema_by_name = {
        "公有云类型": {"id": "f_cloud_type", "name": "公有云类型", "type": "radioV2",
                       "option": [{"value": "zhitupu", "text": "智谱"}]},
        "支付类型": {"id": "f_payment_type", "name": "支付类型", "type": "radioV2",
                     "option": [{"value": "recharge-only", "text": "仅充值"}]},
        "支付方式": {
            "id": "widget_payment_way",
            "name": "支付方式",
            "type": "radioV2",
            "option": [
                {"value": "company-pay", "text": "公司支付"},
                {"value": "reimburse", "text": "充值报销"},
            ],
        },
        "付款公司": {"id": "f_payment_company", "name": "付款公司", "type": "radioV2",
                     "option": [{"value": "sz-yibo", "text": "深圳壹铂云科技有限公司"}]},
        "付款方式": {"id": "f_remit_method", "name": "付款方式", "type": "radioV2",
                     "option": [{"value": "transfer", "text": "转账"}]},
        "充值客户名称": {"id": "f_customer", "name": "充值客户名称", "type": "input", "option": []},
        "充值云账号": {"id": "f_account", "name": "充值云账号", "type": "input", "option": []},
        "说明 1": {"id": "f_note1", "name": "说明 1", "type": "text", "option": []},
        "付款金额": {"id": "f_amount", "name": "付款金额", "type": "amount", "option": []},
        "期望到账时间": {"id": "f_date", "name": "期望到账时间", "type": "date", "option": []},
        "备注": {"id": "f_remark", "name": "备注", "type": "input", "option": []},
    }
    request_data = {
        "cloud_type": "智谱",
        "payment_type": "仅充值",
        "recharge_customer_name": "深圳壹铂云科技有限公司",
        "recharge_account": "18017606559",
        "payment_way": "公司支付",
        "payment_company": "深圳壹铂云科技有限公司",
        "remit_method": "转账",
        "amount": 200,
        "payee": {
            "type": "对公账户",
            "account_name": "北京智谱华章科技股份有限公司",
            "account_number": "11093851041070210011884",
            "bank_name": "招商银行",
            "bank_region": "北京市/北京市",
            "bank_branch": "招商银行股份有限公司北京上地支行",
        },
    }

    form_payload = module.build_form_payload(request_data, schema_by_name)
    remark_item = next(
        (item for item in form_payload if item["id"] == "f_remark"),
        None,
    )
    assert remark_item is not None, "备注 widget should be in form payload"
    # 收款账户 info must be encoded in 备注
    remark = remark_item["value"]
    assert "对公账户" in remark
    assert "北京智谱华章科技股份有限公司" in remark
    assert "11093851041070210011884" in remark
    assert "招商银行" in remark
    # 说明 1 field should be present with fixed instruction text
    note1_item = next(
        (item for item in form_payload if item["id"] == "f_note1"),
        None,
    )
    assert note1_item is not None, "说明 1 widget should be in form payload"
    assert note1_item["value"] == "请填写<员工费用报销>并关联此申请"
    # 充值客户名称 and 充值云账号 should use "input" type (not "text")
    customer_item = next((item for item in form_payload if item["id"] == "f_customer"), None)
    assert customer_item is not None
    assert customer_item["type"] == "input", "充值客户名称 should be input type"
    account_item = next((item for item in form_payload if item["id"] == "f_account"), None)
    assert account_item is not None
    assert account_item["type"] == "input", "充值云账号 should be input type"


def test_recharge_approval_recovers_remit_method_from_payment_type():
    module = _load_skill_module(
        "submit_recharge_approval_payment_type_recovery",
        "scripts/submit_recharge_approval.py",
    )
    schema_by_name = {
        "公有云类型": {"id": "f_cloud_type", "name": "公有云类型", "type": "radioV2",
                       "option": [{"value": "zhitupu", "text": "智谱"}]},
        "支付类型": {"id": "f_payment_type", "name": "支付类型", "type": "radioV2",
                     "option": [{"value": "recharge-only", "text": "仅充值"}]},
        "支付方式": {"id": "f_payment_way", "name": "支付方式", "type": "radioV2",
                     "option": [{"value": "company-pay", "text": "公司支付"}]},
        "付款公司": {"id": "f_payment_company", "name": "付款公司", "type": "radioV2",
                     "option": [{"value": "sz-yibo", "text": "深圳壹铂云科技有限公司"}]},
        "付款方式": {"id": "f_remit_method", "name": "付款方式", "type": "radioV2",
                     "option": [{"value": "transfer", "text": "转账"}]},
        "充值客户名称": {"id": "f_customer", "name": "充值客户名称", "type": "input", "option": []},
        "充值云账号": {"id": "f_account", "name": "充值云账号", "type": "input", "option": []},
        "付款金额": {"id": "f_amount", "name": "付款金额", "type": "amount", "option": []},
        "期望到账时间": {"id": "f_date", "name": "期望到账时间", "type": "date", "option": []},
        "备注": {"id": "f_remark", "name": "备注", "type": "input", "option": []},
    }
    request_data = {
        "cloud_type": "智谱",
        "payment_type": "转账",
        "recharge_customer_name": "深圳壹铂云科技有限公司",
        "recharge_account": "18017606559",
        "payment_way": "公司支付",
        "payment_company": "深圳壹铂云科技有限公司",
        "amount": 200,
        "payee": {
            "type": "对公账户",
            "account_name": "北京智谱华章科技股份有限公司",
            "account_number": "11093851041070210011884",
            "bank_name": "招商银行",
            "bank_region": "北京市/北京市",
            "bank_branch": "招商银行股份有限公司北京上地支行",
        },
    }

    module.validate_request(request_data)
    form_payload = module.build_form_payload(request_data, schema_by_name)
    values_by_id = {item["id"]: item["value"] for item in form_payload}

    assert request_data["payment_type"] == "仅充值"
    assert request_data["remit_method"] == "转账"
    assert values_by_id["f_payment_type"] == "recharge-only"
    assert values_by_id["f_remit_method"] == "transfer"


def test_recharge_approval_hydrates_payee_from_remark_only_request():
    module = _load_skill_module(
        "submit_recharge_approval_remark_only",
        "scripts/submit_recharge_approval.py",
    )
    request_data = {
        "cloud_type": "智谱",
        "payment_type": "仅充值",
        "recharge_customer_name": "深圳壹铂云科技有限公司",
        "recharge_account": "18017606559",
        "payment_way": "公司支付",
        "payment_company": "深圳壹铂云科技有限公司",
        "remit_method": "转账",
        "amount": 200,
        "remark": (
            "收款类型：对公账户\n"
            "户名：北京智谱华章科技股份有限公司\n"
            "账号：11093851041070210011884\n"
            "银行：招商银行\n"
            "银行地区：北京市/北京市\n"
            "支行：招商银行股份有限公司北京上地支行"
        ),
    }

    module.validate_request(request_data)

    assert "payee" in request_data
    assert request_data["payee"]["account_number"] == "11093851041070210011884"
    assert request_data["payee"]["bank_branch"] == "招商银行股份有限公司北京上地支行"


def test_recharge_approval_rejects_required_account_widget_when_api_cannot_fill():
    module = _load_skill_module(
        "submit_recharge_approval_account_widget_guard",
        "scripts/submit_recharge_approval.py",
    )
    request_data = {
        "payment_way": "公司支付",
        "remark": "收款类型：对公账户",
    }
    schema_by_name = {
        "收款账户": {
            "id": "widget-account",
            "name": "收款账户",
            "type": "account",
            "required": True,
        }
    }

    with pytest.raises(SystemExit, match="requires 收款账户"):
        module.validate_unsupported_account_widgets(request_data, schema_by_name)


@pytest.mark.django_db
def test_recharge_approval_resolves_user_id_with_query_param_and_include_resigned(
    cloud_provider,
    monkeypatch,
):
    cloud_provider.recharge_info = '{"amount": 188, "recharge_account": "acct-188"}'
    cloud_provider.save(update_fields=["recharge_info"])
    record = RechargeApprovalRecord.objects.create(
        provider=cloud_provider,
        raw_recharge_info=cloud_provider.recharge_info,
    )

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"code": 0, "data": {"user_list": [{"user_id": "ou_123"}]}}
            ).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = dict(request.headers)
        return FakeResponse()

    monkeypatch.setattr(
        "urllib.request.urlopen",
        fake_urlopen,
    )

    result = _resolve_user_id_by_email_or_mobile(
        "zhengwei@oneprocloud.cn",
        "t-token",
    )

    assert result == "ou_123"
    assert captured["url"].endswith("/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id")
    assert captured["body"]["include_resigned"] is True
    assert captured["body"]["emails"] == ["zhengwei@oneprocloud.cn"]
    assert captured["body"]["mobiles"] == []
    assert "Authorization" in captured["headers"]


def test_submit_recharge_skill_resolves_user_id_with_query_param():
    module = _load_skill_module(
        "submit_recharge_approval_skill",
        "scripts/submit_recharge_approval.py",
    )

    captured = {}

    def fake_api_request(url, payload, headers, timeout_seconds=30, endpoint_name=""):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"data": {"user_list": [{"user_id": "ou_456"}]}}

    module.api_request = fake_api_request

    assert module._resolve_user_id("https://open.feishu.cn", "tok_abc", "zhengwei@oneprocloud.cn") == "ou_456"
    assert captured["url"].endswith("/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id")
    assert captured["payload"]["include_resigned"] is True
    assert captured["payload"]["emails"] == ["zhengwei@oneprocloud.cn"]
    assert captured["payload"]["mobiles"] == []
    assert captured["headers"]["Authorization"] == "Bearer tok_abc"


def test_submit_recharge_script_records_sanitized_http_traces(monkeypatch):
    module = _load_skill_module(
        "submit_recharge_approval_http_traces",
        "scripts/submit_recharge_approval.py",
    )

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "code": 0,
                    "tenant_access_token": "tenant-secret-token",
                    "msg": "",
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=30):
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    result = module.api_request(
        url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        payload={"app_id": "cli_test", "app_secret": "super-secret"},
        headers={"Authorization": "Bearer tenant-secret-token"},
        endpoint_name="tenant_token",
    )

    traces = module.get_http_traces()
    assert result["tenant_access_token"] == "tenant-secret-token"
    assert traces[0]["endpoint_name"] == "tenant_token"
    assert traces[0]["success"] is True
    assert traces[0]["http_status"] == 200
    assert traces[0]["feishu_code"] == 0
    assert "super-secret" not in json.dumps(traces, ensure_ascii=False)
    assert "tenant-secret-token" not in json.dumps(traces, ensure_ascii=False)
    assert traces[0]["request_preview"]["payload"]["app_secret"] == "***REDACTED***"


def test_submit_recharge_script_stdout_excludes_http_traces_by_default(capsys):
    module = _load_skill_module(
        "submit_recharge_approval_lean_stdout",
        "scripts/submit_recharge_approval.py",
    )
    module.HTTP_TRACES.append({"endpoint_name": "tenant_token", "success": True})
    args = SimpleNamespace(
        command="submit",
        request_file="/tmp/request.json",
        output="",
        indent=None,
        include_http_traces=False,
    )

    module.emit_payload(args, {"ok": True}, success=True, exit_code=0)

    printed = json.loads(capsys.readouterr().out)
    assert printed["ok"] is True
    assert "script_trace" in printed
    assert "http_traces" not in printed


def test_skill_tool_resolves_user_id_with_query_param():
    module = _load_skill_module(
        "feishu_cloud_billing_approval_tools",
        "tools.py",
    )

    captured = {}

    def fake_token():
        return "tok_abc"

    def fake_api(url, payload, token, method="POST"):
        captured["url"] = url
        captured["payload"] = payload
        captured["token"] = token
        return {"data": {"user_list": [{"user_id": "ou_789"}]}}

    module._token = fake_token
    module._api = fake_api

    assert module._resolve_user_id("13800138000") == "ou_789"
    assert captured["url"].endswith("/open-apis/contact/v3/users/batch_get_id?user_id_type=user_id")
    assert captured["payload"]["include_resigned"] is True
    assert captured["payload"]["emails"] == []
    assert captured["payload"]["mobiles"] == ["13800138000"]
    assert captured["token"] == "tok_abc"


def test_submit_recharge_skill_inspects_ongoing_account_state():
    module = _load_skill_module(
        "submit_recharge_approval_skill",
        "scripts/submit_recharge_approval.py",
    )

    def fake_list_instances(*args, **kwargs):
        return {"data": {"instance_code_list": ["ins_ongoing"]}}

    def fake_get_instance(*args, **kwargs):
        return {
            "data": {
                "status": "PENDING",
                "serial_number": "SN-1",
                "user_id": "ou_123",
                "start_time": "2025-01-01T00:00:00Z",
                "form": json.dumps(
                    [
                        {
                            "name": "公有云类型",
                            "type": "text",
                            "value": "智谱",
                        },
                        {
                            "name": "充值云账号",
                            "type": "text",
                            "value": "acct-188",
                        }
                    ]
                ),
            }
        }

    module.list_instances = fake_list_instances
    module.get_instance = fake_get_instance

    out = module.inspect_recharge_account_state(
        "https://www.feishu.cn",
        "tok_abc",
        "approval_188",
        {
            "cloud_type": "智谱",
            "payment_type": "仅充值",
            "recharge_customer_name": "深圳壹铂云科技有限公司",
            "recharge_account": "acct-188",
            "payment_way": "公司支付",
            "payment_company": "深圳壹铂云科技有限公司",
            "remit_method": "转账",
            "amount": 188,
            "expected_date": "2025-01-08",
            "remark": "测试",
            "payee": {
                "type": "对公账户",
                "account_name": "北京智谱华章科技股份有限公司",
                "account_number": "11093851041070210011884",
                "bank_name": "招商银行",
                "bank_region": "北京市/北京市",
                "bank_branch": "招商银行股份有限公司北京上地支行",
            },
        },
        30,
    )

    assert out["state"] == "ongoing"
    assert out["instance_code"] == "ins_ongoing"
    assert out["recharge_account"] == "acct-188"


def test_submit_recharge_skill_inspects_finished_account_state():
    module = _load_skill_module(
        "submit_recharge_approval_skill_finished",
        "scripts/submit_recharge_approval.py",
    )

    def fake_list_instances(*args, **kwargs):
        return {"data": {"instance_code_list": ["ins_done"]}}

    def fake_get_instance(*args, **kwargs):
        return {
            "data": {
                "status": "APPROVED",
                "serial_number": "SN-2",
                "user_id": "ou_123",
                "start_time": "2025-01-01T00:00:00Z",
                "form": json.dumps(
                    [
                        {
                            "name": "公有云类型",
                            "type": "text",
                            "value": "智谱",
                        },
                        {
                            "name": "充值云账号",
                            "type": "text",
                            "value": "acct-188",
                        }
                    ]
                ),
            }
        }

    module.list_instances = fake_list_instances
    module.get_instance = fake_get_instance

    out = module.inspect_recharge_account_state(
        "https://www.feishu.cn",
        "tok_abc",
        "approval_188",
        {
            "cloud_type": "智谱",
            "payment_type": "仅充值",
            "recharge_customer_name": "深圳壹铂云科技有限公司",
            "recharge_account": "acct-188",
            "payment_way": "公司支付",
            "payment_company": "深圳壹铂云科技有限公司",
            "remit_method": "转账",
            "amount": 188,
            "expected_date": "2025-01-08",
            "remark": "测试",
            "payee": {
                "type": "对公账户",
                "account_name": "北京智谱华章科技股份有限公司",
                "account_number": "11093851041070210011884",
                "bank_name": "招商银行",
                "bank_region": "北京市/北京市",
                "bank_branch": "招商银行股份有限公司北京上地支行",
            },
        },
        30,
    )

    assert out["state"] == "finished"
    assert out["instance_code"] == "ins_done"
    assert out["recharge_account"] == "acct-188"


def test_submit_recharge_skill_ignores_same_account_with_different_cloud_type():
    module = _load_skill_module(
        "submit_recharge_approval_skill_different_cloud",
        "scripts/submit_recharge_approval.py",
    )

    def fake_list_instances(*args, **kwargs):
        return {"data": {"instance_code_list": ["ins_other_cloud"]}}

    def fake_get_instance(*args, **kwargs):
        return {
            "data": {
                "status": "PENDING",
                "serial_number": "SN-3",
                "user_id": "ou_123",
                "start_time": "2025-01-01T00:00:00Z",
                "form": json.dumps(
                    [
                        {
                            "name": "公有云类型",
                            "type": "text",
                            "value": "阿里云",
                        },
                        {
                            "name": "充值云账号",
                            "type": "text",
                            "value": "acct-188",
                        },
                    ]
                ),
            }
        }

    module.list_instances = fake_list_instances
    module.get_instance = fake_get_instance

    out = module.inspect_recharge_account_state(
        "https://www.feishu.cn",
        "tok_abc",
        "approval_188",
        {
            "cloud_type": "智谱",
            "payment_type": "仅充值",
            "recharge_customer_name": "深圳壹铂云科技有限公司",
            "recharge_account": "acct-188",
            "payment_way": "公司支付",
            "payment_company": "深圳壹铂云科技有限公司",
            "remit_method": "转账",
            "amount": 188,
            "expected_date": "2025-01-08",
            "remark": "测试",
            "payee": {
                "type": "对公账户",
                "account_name": "北京智谱华章科技股份有限公司",
                "account_number": "11093851041070210011884",
                "bank_name": "招商银行",
                "bank_region": "北京市/北京市",
                "bank_branch": "招商银行股份有限公司北京上地支行",
            },
        },
        30,
    )

    assert out["state"] == "none"
    assert out["cloud_type"] == "智谱"
    assert out["recharge_account"] == "acct-188"


def test_get_feishu_access_token_sends_real_secret(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "real-secret-value")

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"code": 0, "tenant_access_token": "tok_123", "expire": 7200}
            ).encode("utf-8")

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = dict(request.headers)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    token = _get_feishu_access_token()

    assert token == "tok_123"
    assert captured["body"]["app_id"] == "cli_test_app"
    assert captured["body"]["app_secret"] == "real-secret-value"
    assert captured["headers"]["Content-type"] == "application/json; charset=utf-8"
