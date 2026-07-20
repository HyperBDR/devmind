import hashlib
import json
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from data_ops.models import (
    Contract,
    Evidence,
    KnowledgeProductionRun,
    Observation,
    ObservationEvidence,
)

PRODUCER_KEY = "contract-renewal-risk"
PRODUCER_VERSION = "1.0"
OBSERVATION_TYPE = "contract_renewal_risk"
HORIZON_DAYS = 30


def produce_contract_renewal_observations(
    *,
    as_of: date | None = None,
) -> KnowledgeProductionRun:
    """Produce traceable observations for contracts nearing expiry."""
    effective_date = as_of or timezone.localdate()
    run = KnowledgeProductionRun.objects.create(
        producer_key=PRODUCER_KEY,
        producer_version=PRODUCER_VERSION,
        parameters={
            "as_of": effective_date.isoformat(),
            "horizon_days": HORIZON_DAYS,
        },
    )
    try:
        with transaction.atomic():
            counts = _produce(run, effective_date, HORIZON_DAYS)
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


def _produce(run, as_of: date, horizon_days: int) -> dict[str, int]:
    window_end = as_of + timedelta(days=horizon_days)
    contracts = Contract.objects.filter(
        service_end__gte=as_of,
        service_end__lte=window_end,
    ).order_by("id")
    counts = {"created": 0, "resolved": 0, "updated": 0}
    active_subject_keys = []

    for contract in contracts:
        subject_key = str(contract.id)
        active_subject_keys.append(subject_key)
        created = _upsert_observation(
            contract=contract,
            run=run,
            as_of=as_of,
            window_end=window_end,
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


def _upsert_observation(*, contract, run, as_of, window_end):
    subject_key = str(contract.id)
    days_until_expiry = (contract.service_end - as_of).days
    fingerprint = _fingerprint(subject_key)
    observation, created = Observation.objects.update_or_create(
        fingerprint=fingerprint,
        defaults={
            "observation_type": OBSERVATION_TYPE,
            "subject_type": "contract",
            "subject_key": subject_key,
            "statement": _statement(contract, days_until_expiry),
            "structured_value": {
                "contract_number": contract.contract_number,
                "customer_name": contract.customer_name,
                "days_until_expiry": days_until_expiry,
                "service_end": contract.service_end.isoformat(),
            },
            "severity": _severity(days_until_expiry),
            "confidence": "high",
            "producer_key": PRODUCER_KEY,
            "producer_version": PRODUCER_VERSION,
            "status": Observation.Status.ACTIVE,
            "window_start": as_of,
            "window_end": window_end,
            "last_evaluated_at": timezone.now(),
            "resolved_at": None,
            "run": run,
        },
    )
    snapshot = _snapshot(contract)
    source_content_hash = contract.source_content_hash or _snapshot_hash(
        snapshot,
    )
    evidence, _created = Evidence.objects.get_or_create(
        source_model="data_ops.Contract",
        source_object_id=subject_key,
        source_content_hash=source_content_hash,
        defaults={
            "source_record_id": contract.source_record_id,
            "source_locator": {
                "app_token": contract.source_app_token,
                "table_id": contract.source_table_id,
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


def _severity(days_until_expiry: int) -> str:
    if days_until_expiry <= 7:
        return Observation.Severity.HIGH
    return Observation.Severity.MEDIUM


def _statement(contract, days_until_expiry: int) -> str:
    identity = contract.contract_number or contract.customer_name
    return f"合同 {identity} 将在 {days_until_expiry} 天后到期。"


def _snapshot(contract) -> dict:
    return {
        "contract_number": contract.contract_number,
        "customer_name": contract.customer_name,
        "service_end": contract.service_end.isoformat(),
        "status": contract.status,
        "expiry_status": contract.expiry_status,
    }


def _snapshot_hash(snapshot: dict) -> str:
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
