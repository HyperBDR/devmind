"""Safe current-request finance aggregation without account/ledger DTOs."""

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from agione_ops.native_analytics import entity, fail


def amount(value):
    """Missing or non-finite monetary observations never become zero."""
    if value is None or isinstance(value, bool) or len(str(value)) > 100:
        return None
    try:
        value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if (
        not value.is_finite()
        or not -18 <= value.as_tuple().exponent <= 18
        or abs(value) >= 10**18
    ):
        return None
    return value


def aggregate_finance(records, total, month, fetched_at, offset=0):
    """Aggregate only customer-owned USER_AVAILABLE accounts and Credit."""
    balances = defaultdict(lambda: defaultdict(Decimal))
    periods = defaultdict(lambda: defaultdict(Decimal))
    samples = defaultdict(lambda: defaultdict(set))
    positive = defaultdict(lambda: defaultdict(set))
    balance_customers, covered, accounts_seen = set(), set(), set()
    customer_balances = defaultdict(lambda: defaultdict(Decimal))
    customer_overviews = {}
    for cid, accounts, overview in records:
        if not isinstance(accounts, list) or not isinstance(overview, dict):
            fail()
        for row in accounts + [overview]:
            if not isinstance(row, dict):
                fail()
            for key in ("tenantId", "cusTenantId", "customerTenantId"):
                if key in row and entity(row[key]) != cid:
                    fail("SOURCE_CUSTOMER_MISMATCH")
        for account in accounts:
            if account.get("accountPurpose") != "USER_AVAILABLE":
                continue
            aid = entity(account.get("id"))
            if aid in accounts_seen:
                fail("SOURCE_DUPLICATE_ACCOUNT", 409)
            accounts_seen.add(aid)
            unit = account.get("currency", account.get("currencyCode"))
            if not isinstance(unit, str) or not re.fullmatch(
                r"[A-Za-z]{1,16}", unit
            ):
                fail()
            value = amount(
                account.get("balance", account.get("availableBalance"))
            )
            if value is not None:
                balances[unit][cid] += value
                customer_balances[cid][unit] += value
                balance_customers.add(cid)
                covered.add(cid)
        period = overview.get("currentCycle")
        if isinstance(period, str) and re.fullmatch(
            r"[0-9]{4}-(0[1-9]|1[0-2])", period
        ):
            customer_overviews[cid] = {"currentCycle": period}
            for source, key in (
                ("cycleTopUpCredit", "topUp"),
                ("cycleConsumedCredit", "consumed"),
                ("cycleAdjustmentCredit", "adjustment"),
                ("cycleRoundOffCredit", "roundOff"),
            ):
                value = amount(overview.get(source))
                if value is not None:
                    customer_overviews[cid][source] = str(value)
                    periods[period][key] += value
                    samples[period][key].add(cid)
                    if value > 0:
                        positive[period][key].add(cid)
                    covered.add(cid)
    distributions = []
    for unit, values in sorted(balances.items()):
        values = list(values.values())
        distributions.append(
            {
                "unit": unit,
                "threshold": "100",
                "healthyCustomers": sum(x >= 100 for x in values),
                "lowCustomers": sum(0 < x < 100 for x in values),
                "zeroCustomers": sum(x == 0 for x in values),
                "negativeCustomers": sum(x < 0 for x in values),
                "belowThresholdCustomers": sum(x < 100 for x in values),
                "negativeTotal": str(
                    -sum((x for x in values if x < 0), Decimal())
                ),
            }
        )
    summaries = []
    for period, values in sorted(periods.items()):
        summaries.append(
            {
                "period": period,
                "unit": "Credit",
                **{
                    key: str(values[key]) if samples[period][key] else None
                    for key in ("topUp", "consumed", "adjustment", "roundOff")
                },
                "consumingCustomers": len(positive[period]["consumed"]),
                "topUpCustomers": len(positive[period]["topUp"]),
                "coveredCustomers": len(samples[period]["consumed"]),
            }
        )
    next_offset = offset + len(records)
    partial = next_offset < total
    return {
        "available": bool(covered),
        "readOnly": True,
        "mode": "live",
        "independentOfFilters": True,
        "scopeLabel": "Operator 已授权目录实时财务，独立于调用筛选",
        "totalCustomers": total,
        "coveredCustomers": len(covered),
        "balanceCustomers": len(balance_customers),
        "cycleCustomers": (
            len(set().union(*(x["consumed"] for x in samples.values())))
            if samples
            else 0
        ),
        "accountCount": len(accounts_seen),
        "requestedMonth": month,
        "balanceDistributions": distributions,
        "periodSummaries": summaries,
        "balances": [
            {"unit": unit, "value": str(sum(values.values(), Decimal()))}
            for unit, values in sorted(balances.items())
        ],
        "cycles": [
            {
                "period": row["period"],
                "unit": "Credit",
                "value": row["consumed"],
            }
            for row in summaries
            if row["consumed"] is not None
        ],
        "trend": [],
        "trendTotal": None,
        "trendCustomers": 0,
        "trendReason": "本接口未读取完整日序列，不以零替代未知趋势",
        "oldestReadAt": fetched_at,
        "latestReadAt": fetched_at,
        "fetchedAt": fetched_at,
        "partial": partial,
        "nextOffset": next_offset if partial else None,
        "processedCustomers": len(records),
        "offset": offset,
        "latestObservations": True,
        "customerFinance": {
            cid: {
                "accounts": [
                    {
                        "accountPurpose": "USER_AVAILABLE",
                        "currency": unit,
                        "balance": str(value),
                    }
                    for unit, value in sorted(customer_balances[cid].items())
                ],
                "overview": customer_overviews.get(cid, {}),
            }
            for cid in sorted(set(customer_balances) | set(customer_overviews))
        },
        "coverageBasis": "live_authorized_directory",
        "reason": None if covered else "NO_USABLE_FINANCE_OBSERVATIONS",
    }


def unavailable_finance(reason):
    """Do not reinterpret missing authorization as zero money."""
    return {
        "available": False,
        "reason": reason,
        "readOnly": True,
        "mode": "live",
        "balanceDistributions": [],
        "periodSummaries": [],
        "balances": [],
        "cycles": [],
        "trend": [],
        "trendTotal": None,
    }
