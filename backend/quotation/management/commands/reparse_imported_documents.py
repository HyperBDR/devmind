import signal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from quotation.models import (
    DocumentAsset,
    DocumentParseResult,
    DocumentParseStatus,
    Quotation,
    QuotationSourceType,
)
from quotation.services.document_parsing.flexible_parser import (
    complete_document_parse,
)
from quotation.services.document_parsing.service import (
    parse_and_create_quotation,
)
from quotation.services.storage import resolve_document_path


def _raise_timeout(signum, frame):
    raise TimeoutError("document parsing exceeded time limit")


class Command(BaseCommand):
    help = "Split merged imports and automatically reparse imported documents"

    def add_arguments(self, parser):
        parser.add_argument("--owner-email", required=True)
        parser.add_argument("--split-merged", action="store_true")
        parser.add_argument("--shard-count", type=int, default=1)
        parser.add_argument("--shard-index", type=int, default=0)
        parser.add_argument("--file-timeout", type=int, default=30)
        parser.add_argument("--cleanup-orphans", action="store_true")
        parser.add_argument("--cleanup-duplicate-assets", action="store_true")
        parser.add_argument("--upgrade-metadata", action="store_true")

    @staticmethod
    def _is_metadata_fallback(result):
        if result is None or result.parser_version != "2.0.0":
            return False
        return any(
            warning.get("code") == "metadata_fallback"
            for warning in result.validation_warnings_json
            if isinstance(warning, dict)
        )

    def _reset_metadata_fallback(self, asset, owner_email):
        result = (
            asset.parse_results.filter(
                status=DocumentParseStatus.CONFIRMED,
                quotation_id=asset.quotation_id,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        if not self._is_metadata_fallback(result):
            return False

        quotation_id = asset.quotation_id
        with transaction.atomic():
            result.quotation = None
            result.status = DocumentParseStatus.FAILED
            result.confirmed_at = None
            result.error_message = "Metadata fallback scheduled for upgrade"
            result.save(
                update_fields=[
                    "quotation",
                    "status",
                    "confirmed_at",
                    "error_message",
                    "updated_at",
                ]
            )
            asset.quotation = None
            asset.save(update_fields=["quotation"])
            quotation = Quotation.objects.filter(
                id=quotation_id,
                source_type=QuotationSourceType.DOCUMENT_IMPORT,
                created_by_email__iexact=owner_email,
            ).first()
            if quotation and not quotation.documents.exists():
                quotation.delete()
        return True

    def _metadata_fallback(self, asset, actor):
        result = (
            DocumentParseResult.objects.filter(asset=asset)
            .order_by("-created_at", "-id")
            .first()
        )
        if result is None:
            raise ValueError("parse result was not initialized before timeout")
        parsed = complete_document_parse(
            asset,
            resolve_document_path(asset.storage_key),
            None,
            extract_content=False,
        )
        result.status = DocumentParseStatus.READY
        result.normalized_json = parsed.quotation.model_dump(mode="json")
        result.source_totals_json = parsed.source_totals
        result.field_confidence_json = parsed.field_confidence
        result.validation_errors_json = []
        result.validation_warnings_json = [
            {
                "field": "document",
                "code": "metadata_fallback",
                "detail": "Content extraction timed out; metadata was used",
            }
        ]
        result.confidence = parsed.confidence
        result.error_message = ""
        result.save()
        return parse_and_create_quotation(asset, actor=actor)

    def handle(self, *args, **options):
        owner_email = options["owner_email"].strip().lower()
        user_model = get_user_model()
        actor = user_model.objects.filter(email__iexact=owner_email).first()
        split_count = 0
        cleanup_count = 0
        duplicate_cleanup_count = 0
        if options["cleanup_orphans"]:
            foreign_assets = DocumentAsset.objects.filter(
                quotation__source_type=QuotationSourceType.DOCUMENT_IMPORT,
                quotation__created_by_email__iexact=owner_email,
            ).exclude(created_by_email__iexact=owner_email)
            for asset in foreign_assets:
                asset.parse_results.filter(
                    quotation_id=asset.quotation_id
                ).update(
                    quotation=None,
                    status=DocumentParseStatus.SUPERSEDED,
                )
                asset.quotation = None
                asset.save(update_fields=["quotation"])
            orphan_ids = list(
                Quotation.objects.filter(
                    source_type=QuotationSourceType.DOCUMENT_IMPORT,
                    created_by_email__iexact=owner_email,
                )
                .annotate(document_count=Count("documents"))
                .filter(document_count=0)
                .values_list("id", flat=True)
            )
            cleanup_count = len(orphan_ids)
            Quotation.objects.filter(id__in=orphan_ids).delete()
        if options["cleanup_duplicate_assets"]:
            duplicate_assets = list(
                DocumentAsset.objects.filter(
                    source="feishu",
                    created_by_email__iexact=owner_email,
                    feishu_file_token__isnull=False,
                ).exclude(feishu_file_token="")
            )
            grouped = {}
            for asset in duplicate_assets:
                grouped.setdefault(asset.feishu_file_token, []).append(asset)
            for group in grouped.values():
                keeper = max(
                    group,
                    key=lambda item: (
                        bool(item.quotation_id),
                        item.created_at,
                        item.id,
                    ),
                )
                for asset in group:
                    if asset.id == keeper.id or not asset.quotation_id:
                        continue
                    quotation_id = asset.quotation_id
                    with transaction.atomic():
                        asset.parse_results.filter(
                            quotation_id=quotation_id
                        ).update(
                            quotation=None,
                            status=DocumentParseStatus.SUPERSEDED,
                        )
                        asset.quotation = None
                        asset.save(update_fields=["quotation"])
                        quotation = Quotation.objects.filter(
                            id=quotation_id,
                            source_type=(
                                QuotationSourceType.DOCUMENT_IMPORT
                            ),
                            created_by_email__iexact=owner_email,
                        ).first()
                        if quotation and not quotation.documents.exists():
                            quotation.delete()
                    duplicate_cleanup_count += 1
        if options["split_merged"]:
            quotations = Quotation.objects.filter(
                source_type=QuotationSourceType.DOCUMENT_IMPORT,
                created_by_email__iexact=owner_email,
            )
            for quotation in quotations:
                assets = list(
                    quotation.documents.filter(source="feishu").order_by(
                        "created_at", "id"
                    )
                )
                for asset in assets[1:]:
                    asset.parse_results.filter(quotation=quotation).update(
                        quotation=None,
                        status=DocumentParseStatus.SUPERSEDED,
                    )
                    asset.quotation = None
                    asset.save(update_fields=["quotation"])
                    split_count += 1

        candidates = list(
            DocumentAsset.objects.filter(
                source="feishu",
                created_by_email__iexact=owner_email,
            )
            .prefetch_related("parse_results")
            .order_by("feishu_file_token", "-created_at", "-id")
        )
        selected = {}
        for asset in candidates:
            if asset.file_name.lower().startswith("~$"):
                continue
            token = asset.feishu_file_token or asset.id
            current = selected.get(token)
            if current is None or (
                asset.quotation_id and not current.quotation_id
            ):
                selected[token] = asset

        shard_count = max(options["shard_count"], 1)
        shard_index = options["shard_index"]
        assets = sorted(selected.values(), key=lambda item: item.id)
        assets = [
            asset
            for index, asset in enumerate(assets)
            if index % shard_count == shard_index
        ]

        created = 0
        reused = 0
        failed = 0
        not_quotations = 0
        upgraded = 0
        for asset in assets:
            self.stdout.write(f"PARSING {asset.file_name}")
            upgrading = False
            try:
                if options["upgrade_metadata"]:
                    upgrading = self._reset_metadata_fallback(
                        asset,
                        owner_email,
                    )
                    if upgrading:
                        upgraded += 1
                signal.signal(signal.SIGALRM, _raise_timeout)
                signal.alarm(max(options["file_timeout"], 1))
                result, was_reused = parse_and_create_quotation(
                    asset,
                    actor=actor,
                )
            except TimeoutError:
                signal.alarm(0)
                self.stderr.write(f"FALLBACK {asset.file_name}: timeout")
                result, was_reused = self._metadata_fallback(asset, actor)
            except Exception as exc:
                self.stderr.write(f"FAILED {asset.file_name}: {exc}")
                if not upgrading:
                    failed += 1
                    continue
                try:
                    self.stderr.write(
                        f"FALLBACK {asset.file_name}: upgrade failed"
                    )
                    result, was_reused = self._metadata_fallback(
                        asset,
                        actor,
                    )
                except Exception as fallback_exc:
                    failed += 1
                    self.stderr.write(
                        f"FAILED {asset.file_name}: {fallback_exc}"
                    )
                    continue
            finally:
                signal.alarm(0)
            if result.quotation_id:
                if was_reused:
                    reused += 1
                else:
                    created += 1
            elif result.status == DocumentParseStatus.NOT_QUOTATION:
                not_quotations += 1
            else:
                failed += 1
                detail = result.error_message or result.status
                self.stderr.write(
                    f"FAILED {asset.file_name}: {detail}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                " ".join(
                    [
                        f"split={split_count}",
                        f"cleaned={cleanup_count}",
                        f"duplicates={duplicate_cleanup_count}",
                        f"created={created}",
                        f"reused={reused}",
                        f"upgraded={upgraded}",
                        f"not_quotations={not_quotations}",
                        f"failed={failed}",
                    ]
                )
            )
        )
