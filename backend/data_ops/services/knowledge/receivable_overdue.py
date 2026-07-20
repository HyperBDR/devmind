import hashlib
import json
from datetime import date

from django.db import transaction
from django.utils import timezone

from data_ops.models import (
    DomesticLedger,
    Evidence,
    KnowledgeProductionRun,
    Observation,
    ObservationEvidence,
)

PRODUCER_KEY = "receivable-overdue-risk"
PRODUCER_VERSION = "1.0"
OBSERVATION_TYPE = "receivable_overdue_risk"


def produce_receivable_overdue_observations(
    *,
    as_of: date | None = None,
) -> KnowledgeProductionRun:
    """Produce traceable observations for overdue receivables."""
    effective_date = as_of or timezone.localdate()
    run = KnowledgeProductionRun.objects.create(
        producer_key=PRODUCER_KEY,
        producer_version=PRODUCER_VERSION,
        parameters={"as_of": effective_date.isoformat()},
    )
    try:
        with transaction.atomic():
            counts = _produce(run, effective_date)
    except Exception as exc:
        run.status = KnowledgeProductionRun.Status.FAILED
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save(
            update_fields=["status", "error_message", "finished_at"],
        )
        raise

    run.status = KnowledgeProductionRun.Status.SUCCEEDED
    run.result_counts = counts
    run.finished_at = timezone.now()
    run.save(
        update_fields=["status", "result_counts", "finished_at"],
    )
    return run


def _produce(run, as_of: date) -> dict[str, int]:
    ledgers = DomesticLedger.objects.filter(
        ledger_type="收入",
        outstanding__gt=0,
        expected_payment_date__lt=as_of,
    ).order_by("id")
    counts = {"created": 0, "resolved": 0, "updated": 0}
    active_subject_keys = []

    for ledger in ledgers:
        subject_key = str(ledger.id)
        active_subject_keys.append(subject_key)
        created = _upsert_observation(
            ledger=ledger,
            run=run,
            as_of=as_of,
        )
        counts["created" if created else "updated"] += 1

    stale = Observation.objects.filter(
        producer_key=PRODUCER_KEY,
        producer_version=PRODUCER_VERSION,
        status=Observation.Status.ACTIVE,
    ).exclude(subject_key__in=active_subject_keys)
    now = timezone.now()
    counts["resolved"] = stale.update(
        status=Observation.Status.RESOLVED,
        resolved_at=now,
        last_evaluated_at=now,
        run=run,
    )
    return counts


def _upsert_observation(*, ledger, run, as_of):
    subject_key = str(ledger.id)
    days_overdue = (as_of - ledger.expected_payment_date).days
    observation, created = Observation.objects.update_or_create(
        fingerprint=_fingerprint(subject_key),
        defaults={
            "observation_type": OBSERVATION_TYPE,
            "subject_type": "domestic_ledger",
            "subject_key": subject_key,
            "statement": _statement(ledger, days_overdue),
            "structured_value": _structured_value(
                ledger,
                days_overdue,
            ),
            "severity": _severity(days_overdue),
            "confidence": "high",
            "producer_key": PRODUCER_KEY,
            "producer_version": PRODUCER_VERSION,
            "status": Observation.Status.ACTIVE,
            "window_start": as_of,
            "window_end": as_of,
            "last_evaluated_at": timezone.now(),
            "resolved_at": None,
            "run": run,
        },
    )
    snapshot = _snapshot(ledger)
    source_content_hash = ledger.source_content_hash or _snapshot_hash(
        snapshot,
    )
    evidence, _created = Evidence.objects.get_or_create(
        source_model="data_ops.DomesticLedger",
        source_object_id=subject_key,
        source_content_hash=source_content_hash,
        defaults={
            "source_record_id": ledger.source_record_id,
            "source_locator": {
                "app_token": ledger.source_app_token,
                "table_id": ledger.source_table_id,
            },
            "snapshot": snapshot,
        },
    )
    ObservationEvidence.objects.get_or_create(
        observation=observation,
        evidence=evidence,
    )
    observation.evidence_links.exclude(evidence=evidence).delete()
    return created


def _fingerprint(subject_key: str) -> str:
    value = f"{PRODUCER_KEY}|{PRODUCER_VERSION}|{subject_key}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _severity(days_overdue: int) -> str:
    if days_overdue <= 15:
        return Observation.Severity.LOW
    if days_overdue <= 30:
        return Observation.Severity.MEDIUM
    if days_overdue <= 60:
        return Observation.Severity.HIGH
    return Observation.Severity.CRITICAL


def _statement(ledger, days_overdue: int) -> str:
    identity = ledger.customer_name or ledger.project_name
    amount = _amount(ledger.outstanding)
    currency = ledger.currency or "未标明币种"
    return (
        f"客户 {identity} 有 {currency} {amount} 应收款已逾期 "
        f"{days_overdue} 天。"
    )


def _structured_value(ledger, days_overdue: int) -> dict:
    return {
        "currency": ledger.currency,
        "customer_name": ledger.customer_name,
        "days_overdue": days_overdue,
        "expected_payment_date": (ledger.expected_payment_date.isoformat()),
        "outstanding": _amount(ledger.outstanding),
        "project_name": ledger.project_name,
        "sales_person": ledger.sales_person,
    }


def _snapshot(ledger) -> dict:
    return {
        "currency": ledger.currency,
        "customer_name": ledger.customer_name,
        "expected_payment_date": (ledger.expected_payment_date.isoformat()),
        "ledger_type": ledger.ledger_type,
        "outstanding": _amount(ledger.outstanding),
        "payment_status": ledger.payment_status,
        "project_name": ledger.project_name,
        "sales_person": ledger.sales_person,
    }


def _amount(value) -> str:
    return format(value, "f")


def _snapshot_hash(snapshot: dict) -> str:
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
