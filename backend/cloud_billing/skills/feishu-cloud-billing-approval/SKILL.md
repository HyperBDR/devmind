---
name: feishu-cloud-billing-approval
description: Use when creating Feishu cloud billing recharge approvals from provider recharge info.
---

# Feishu Cloud Billing Approval

Use the bound workflow tools only. Do not call scripts directly.

## Required Flow

1. Call `plan_recharge_approval_workflow(raw_recharge_info, submitter_identifier="", resolved_submitter_user_id=<user_id>)`.
2. Read `request_file`, `submitter_user_id` / `resolved_submitter_user_id`, and `submitter_user_label` from the plan.
3. Call `execute_recharge_approval_plan(request_file, submitter_user_id=<user_id>, submitter_user_label=...)`.
4. `submitter_identifier` is now an optional legacy email/mobile alias kept for backwards-compatible matching; the execution path itself requires a Feishu `user_id`.

The plan step writes a debug JSON file under `/tmp` named with provider, account, and record ids. It is intentionally retained.

## Request Shape

The request may be JSON or key/value text. It must resolve to:

- `cloud_type`
- `recharge_customer_name`
- `recharge_account`
- `payment_company`
- `amount`
- `currency`

## Constraints

- Do not write payee bank/account details into structured JSON fields.
- Store the payer details for `收款账户` in `remark` as multiline text instead.
- If the source text contains payee fields, preserve them only in `remark`; the generated JSON should not expose `account_name`, `account_number`, `bank_name`, `bank_region`, or `bank_branch` as structured fields.
- If the amount is written like `200.00 CNY`, split it into `amount: 200.00` and `currency: CNY`.
- If the active approval definition requires a `收款账户` widget and the API cannot populate it, stop with a clear failure instead of attempting a partial submission.
- The execution step may reconstruct payee details from `remark` or historical approvals when needed.

Optional defaults:

- `payment_type`: `仅充值`
- `payment_way`: `公司支付`
- `remit_method`: `转账`

`payment_type` is not the same field as `remit_method`: `支付类型=仅充值`, `付款方式=转账`.

## Failure Handling

If planning or execution raises, call `mark_recharge_approval_failed(error_message=...)`.

## Implementation Contract

`submit_recharge_approval.py` is the only bundled submission script. It prints one JSON object to stdout. Verbose HTTP traces are opt-in and should not be requested during normal agent execution.
