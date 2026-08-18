from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from quotation.models import (
    DocumentAsset,
    DocumentLifecycleState,
    Quotation,
    QuotationSourceType,
)
from quotation.permissions import user_display_email

logger = logging.getLogger(__name__)


class DocumentLifecycleConflict(Exception):
    """Describe a lifecycle transition that policy does not allow."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class DocumentLifecycleImpact:
    quotation: str
    versions: str
    assets_affected: int
    remote_copies: str

    def as_dict(self) -> dict:
        return {
            "quotation": self.quotation,
            "versions": self.versions,
            "assets_affected": self.assets_affected,
            "remote_copies": self.remote_copies,
        }


def _retention_days() -> int:
    return max(
        int(getattr(settings, "QUOTATION_DOCUMENT_RETENTION_DAYS", 30)),
        1,
    )


def _locked_group(
    asset_id: str,
) -> tuple[DocumentAsset, list[DocumentAsset], Quotation | None]:
    quotation_id = DocumentAsset.objects.values_list(
        "quotation_id",
        flat=True,
    ).get(pk=asset_id)
    quotation = None
    if quotation_id is not None:
        quotation = Quotation.objects.select_for_update().get(
            pk=quotation_id,
        )
    if (
        quotation is not None
        and quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT
    ):
        assets = list(
            DocumentAsset.objects.select_for_update()
            .filter(quotation_id=quotation_id)
            .order_by("created_at", "id")
        )
        asset = next(item for item in assets if item.id == asset_id)
    else:
        asset = DocumentAsset.objects.select_for_update().get(pk=asset_id)
        assets = [asset]
    return asset, assets, quotation


@transaction.atomic
def archive_document(
    asset_id: str,
    *,
    actor,
    reason: str = "",
) -> tuple[DocumentAsset, DocumentLifecycleImpact]:
    """Archive one document lifecycle group without deleting its records."""
    asset, assets, quotation = _locked_group(asset_id)
    if asset.lifecycle_state == DocumentLifecycleState.ARCHIVED:
        quotation_state = (
            "archived"
            if quotation is not None and quotation.archived_at is not None
            else "retained"
        )
        return asset, DocumentLifecycleImpact(
            quotation=quotation_state,
            versions="retained",
            assets_affected=0,
            remote_copies="unchanged",
        )
    held = next((item for item in assets if item.legal_hold_at), None)
    if held is not None:
        raise DocumentLifecycleConflict(
            "legal_hold",
            "document is protected by legal hold",
        )
    now = timezone.now()
    actor_email = user_display_email(actor)
    purge_after = now + timedelta(days=_retention_days())
    asset_ids = [item.id for item in assets]
    DocumentAsset.objects.filter(id__in=asset_ids).update(
        lifecycle_state=DocumentLifecycleState.ARCHIVED,
        archived_at=now,
        archived_by_email=actor_email,
        archive_reason=str(reason or "")[:255],
        purge_after=purge_after,
    )
    quotation_result = "retained"
    if (
        quotation is not None
        and quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT
    ):
        quotation.archived_at = now
        quotation.archived_by_email = actor_email
        quotation.archive_reason = str(reason or "")[:255]
        quotation.save(
            update_fields=[
                "archived_at",
                "archived_by_email",
                "archive_reason",
                "updated_at",
            ]
        )
        quotation_result = "archived"
    asset.refresh_from_db()
    return asset, DocumentLifecycleImpact(
        quotation=quotation_result,
        versions="retained",
        assets_affected=len(asset_ids),
        remote_copies="owned_only_after_retention",
    )


@transaction.atomic
def restore_document(
    asset_id: str,
    *,
    actor,
) -> tuple[DocumentAsset, DocumentLifecycleImpact]:
    """Restore an archived document group before its purge deadline."""
    asset, assets, quotation = _locked_group(asset_id)
    now = timezone.now()
    if asset.lifecycle_state == DocumentLifecycleState.ACTIVE:
        return asset, DocumentLifecycleImpact(
            quotation="retained",
            versions="retained",
            assets_affected=0,
            remote_copies="unchanged",
        )
    if asset.purge_after is not None and asset.purge_after <= now:
        raise DocumentLifecycleConflict(
            "retention_expired",
            "document retention period has expired",
        )
    asset_ids = [item.id for item in assets]
    DocumentAsset.objects.filter(id__in=asset_ids).update(
        lifecycle_state=DocumentLifecycleState.ACTIVE,
        archived_at=None,
        archived_by_email="",
        archive_reason="",
        purge_after=None,
    )
    quotation_result = "retained"
    if (
        quotation is not None
        and quotation.source_type == QuotationSourceType.DOCUMENT_IMPORT
    ):
        quotation.archived_at = None
        quotation.archived_by_email = ""
        quotation.archive_reason = ""
        quotation.save(
            update_fields=[
                "archived_at",
                "archived_by_email",
                "archive_reason",
                "updated_at",
            ]
        )
        quotation_result = "restored"
    asset.refresh_from_db()
    return asset, DocumentLifecycleImpact(
        quotation=quotation_result,
        versions="retained",
        assets_affected=len(asset_ids),
        remote_copies="unchanged",
    )


def purge_archived_documents(
    *,
    dry_run: bool,
    batch_size: int,
    now=None,
) -> dict:
    """Purge a bounded batch after retention while honoring legal hold."""
    current_time = now or timezone.now()
    bounded_batch_size = max(min(int(batch_size), 500), 1)
    eligible = DocumentAsset.objects.filter(
        lifecycle_state=DocumentLifecycleState.ARCHIVED,
        purge_after__isnull=False,
        purge_after__lte=current_time,
        legal_hold_at__isnull=True,
    )
    held_quotation_ids = DocumentAsset.objects.filter(
        legal_hold_at__isnull=False,
        quotation_id__isnull=False,
    ).values("quotation_id")
    eligible = eligible.exclude(quotation_id__in=held_quotation_ids)
    eligible_count = eligible.count()
    candidate_ids = list(
        eligible.order_by("purge_after", "created_at", "id").values_list(
            "id",
            flat=True,
        )[:bounded_batch_size]
    )
    result = {
        "dry_run": dry_run,
        "eligible": eligible_count,
        "selected": len(candidate_ids),
        "purged": 0,
        "failed": 0,
    }
    if dry_run:
        return result
    for asset_id in candidate_ids:
        try:
            with transaction.atomic():
                asset = (
                    DocumentAsset.objects.select_for_update()
                    .filter(
                        pk=asset_id,
                        lifecycle_state=DocumentLifecycleState.ARCHIVED,
                        purge_after__isnull=False,
                        purge_after__lte=current_time,
                        legal_hold_at__isnull=True,
                    )
                    .first()
                )
                if asset is None:
                    continue
                if (
                    asset.quotation_id is not None
                    and DocumentAsset.objects.filter(
                        quotation_id=asset.quotation_id,
                        legal_hold_at__isnull=False,
                    ).exists()
                ):
                    continue
                asset.delete()
        except Exception:
            result["failed"] += 1
            logger.exception(
                "quotation_document_retention_purge_failed",
                extra={"document_asset_id": asset_id},
            )
        else:
            result["purged"] += 1
    return result
