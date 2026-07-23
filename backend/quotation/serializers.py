from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
import re
from urllib.parse import quote, urlparse

from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from quotation.models import (
    AuditEvent,
    DocumentAsset,
    Quotation,
    QuotationItem,
    QuotationVersion,
    ReplicaSyncStatus,
    SecurityAlert,
    UserQuotationCatalog,
)
from quotation.security_alerts import can_manage_security_alerts
from quotation.services.storage_control import remote_document_reference


class CatalogObjectListField(serializers.ListField):
    child = serializers.DictField()


class UserQuotationCatalogWriteSerializer(serializers.Serializer):
    version = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=120,
    )
    products = CatalogObjectListField(required=False, default=list)
    services = CatalogObjectListField(required=False, default=list)
    discounts = CatalogObjectListField(required=False, default=list)
    product_lines = CatalogObjectListField(required=False, default=list)
    payment_terms = CatalogObjectListField(required=False, default=list)


class UserQuotationCatalogSerializer(serializers.ModelSerializer):
    version = serializers.CharField(source="catalog_version")

    class Meta:
        model = UserQuotationCatalog
        fields = [
            "version",
            "initialized",
            "products",
            "services",
            "discounts",
            "product_lines",
            "payment_terms",
            "updated_at",
        ]


def build_feishu_file_url(file_token: str | None) -> str | None:
    token = (file_token or "").strip()
    if not token:
        return None
    base_url = settings.FEISHU_WEB_BASE_URL.rstrip("/")
    return f"{base_url}/file/{quote(token, safe='')}"


def trusted_feishu_file_url(asset: DocumentAsset) -> str | None:
    """Return a trusted Feishu web URL for one document asset."""
    if settings.QUOTATION_FEISHU_DIRECT_LINK_MODE == "disabled":
        return None
    reference = remote_document_reference(asset)
    token = reference.token
    if not token:
        return None
    candidate = reference.url
    if candidate:
        parsed = urlparse(candidate)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        trusted_host = hostname in {"feishu.cn", "larksuite.com"} or any(
            hostname.endswith(suffix)
            for suffix in (".feishu.cn", ".larksuite.com")
        )
        path_segments = {
            segment for segment in parsed.path.split("/") if segment
        }
        if (
            parsed.scheme == "https"
            and trusted_host
            and token in path_segments
        ):
            return candidate
    return build_feishu_file_url(token)


class QuotationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItem
        fields = [
            "id",
            "line_no",
            "type",
            "item_id",
            "name",
            "description",
            "qty",
            "list_price",
            "discount_percent",
            "net_unit_price",
            "extended_price",
        ]
        read_only_fields = ["id"]


class QuotationItemWriteSerializer(serializers.Serializer):
    line_no = serializers.IntegerField(min_value=1)
    type = serializers.CharField()
    item_id = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    name = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    qty = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("1"),
        default=Decimal("1"),
    )
    list_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        default=Decimal("0"),
    )
    discount_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        default=Decimal("0"),
    )
    net_unit_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        required=False,
    )
    extended_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        required=False,
    )

    def validate(self, attrs):
        list_price = attrs.get("list_price", Decimal("0"))
        discount = attrs.get("discount_percent", Decimal("0"))
        qty = attrs.get("qty", Decimal("1"))
        net_unit_price = (
            list_price * (Decimal("1") - discount / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        attrs["net_unit_price"] = net_unit_price
        attrs["extended_price"] = (net_unit_price * qty).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return attrs


class QuotationVersionSerializer(serializers.ModelSerializer):
    snapshot = serializers.JSONField(source="snapshot_json", read_only=True)

    class Meta:
        model = QuotationVersion
        fields = [
            "id",
            "version_no",
            "status",
            "notes",
            "operator_email",
            "created_at",
            "snapshot",
        ]
        read_only_fields = fields


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, read_only=True)
    versions = QuotationVersionSerializer(many=True, read_only=True)
    issuer_signature = serializers.CharField(allow_blank=True, required=False)
    remarks_disclaimer = serializers.CharField(
        allow_blank=True, required=False
    )
    feishu_file_token = serializers.SerializerMethodField()
    feishu_url = serializers.SerializerMethodField()
    feishu_path = serializers.SerializerMethodField()
    feishu_uploaded_at = serializers.SerializerMethodField()
    feishu_excel_file_token = serializers.SerializerMethodField()
    feishu_excel_url = serializers.SerializerMethodField()
    feishu_excel_path = serializers.SerializerMethodField()
    feishu_excel_uploaded_at = serializers.SerializerMethodField()
    feishu_pdf_file_token = serializers.SerializerMethodField()
    feishu_pdf_url = serializers.SerializerMethodField()
    feishu_pdf_path = serializers.SerializerMethodField()
    feishu_pdf_uploaded_at = serializers.SerializerMethodField()
    feishu_document_id = serializers.SerializerMethodField()
    feishu_excel_document_id = serializers.SerializerMethodField()
    feishu_pdf_document_id = serializers.SerializerMethodField()

    def _latest_feishu_upload(
        self, obj: Quotation, doc_type: str | None = None
    ) -> DocumentAsset | None:
        cache_key = f"_latest_feishu_upload_for_serializer_{doc_type or 'any'}"
        if hasattr(obj, cache_key):
            return getattr(obj, cache_key)

        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get(
            "documents"
        )
        if prefetched is not None:
            uploads = [
                document
                for document in prefetched
                if document.source == "feishu_upload"
                and remote_document_reference(document).token
            ]
            if doc_type:
                uploads = [
                    document
                    for document in uploads
                    if document.doc_type == doc_type
                ]
            latest = max(
                uploads, key=lambda document: document.created_at, default=None
            )
        else:
            qs = obj.documents.filter(source="feishu_upload")
            if doc_type:
                qs = qs.filter(doc_type=doc_type)
            remote_reference_filter = (
                Q(feishu_file_token__isnull=False)
                & ~Q(feishu_file_token="")
            ) | (
                Q(replicas__sync_status=ReplicaSyncStatus.SYNCED)
                & Q(replicas__revoked_at__isnull=True)
                & ~Q(replicas__remote_file_token="")
            )
            latest = (
                qs.filter(remote_reference_filter)
                .distinct()
                .order_by("-created_at")
                .first()
            )

        setattr(obj, cache_key, latest)
        return latest

    def _feishu_asset_data(self, obj: Quotation, doc_type: str) -> dict:
        latest = self._latest_feishu_upload(obj, doc_type)
        if not latest:
            return {}
        return {
            "document_id": latest.id,
            "path": latest.file_name,
            "uploaded_at": latest.created_at,
        }

    def get_feishu_file_token(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        if not latest or not trusted_feishu_file_url(latest):
            return None
        return remote_document_reference(latest).token

    def get_feishu_url(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        return trusted_feishu_file_url(latest) if latest else None

    def get_feishu_document_id(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        return latest.id if latest else None

    def get_feishu_path(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        return latest.file_name if latest else None

    def get_feishu_uploaded_at(self, obj: Quotation):
        latest = self._latest_feishu_upload(obj)
        return latest.created_at if latest else None

    def get_feishu_excel_file_token(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj, "excel")
        if not latest or not trusted_feishu_file_url(latest):
            return None
        return remote_document_reference(latest).token

    def get_feishu_excel_url(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj, "excel")
        return trusted_feishu_file_url(latest) if latest else None

    def get_feishu_excel_document_id(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "excel").get("document_id")

    def get_feishu_excel_path(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "excel").get("path")

    def get_feishu_excel_uploaded_at(self, obj: Quotation):
        return self._feishu_asset_data(obj, "excel").get("uploaded_at")

    def get_feishu_pdf_file_token(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj, "pdf")
        if not latest or not trusted_feishu_file_url(latest):
            return None
        return remote_document_reference(latest).token

    def get_feishu_pdf_url(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj, "pdf")
        return trusted_feishu_file_url(latest) if latest else None

    def get_feishu_pdf_document_id(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "pdf").get("document_id")

    def get_feishu_pdf_path(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "pdf").get("path")

    def get_feishu_pdf_uploaded_at(self, obj: Quotation):
        return self._feishu_asset_data(obj, "pdf").get("uploaded_at")

    class Meta:
        model = Quotation
        fields = [
            "id",
            "quote_no",
            "status",
            "version_current",
            "product_line",
            "project_name",
            "currency",
            "payment_term_option",
            "payment_terms",
            "quote_date",
            "expire_date",
            "tax_label",
            "vat_rate",
            "vat_amount",
            "software_subtotal",
            "others_subtotal",
            "subtotal_before_vat",
            "grand_total",
            "remarks_disclaimer",
            "issuer_company_name",
            "issuer_contact_name",
            "issuer_contact_email",
            "issuer_contact_title",
            "issuer_signature",
            "client_company",
            "contact_person",
            "email",
            "billing_company",
            "billing_contact",
            "billing_email",
            "created_by_email",
            "feishu_file_token",
            "feishu_url",
            "feishu_document_id",
            "feishu_path",
            "feishu_uploaded_at",
            "feishu_excel_file_token",
            "feishu_excel_url",
            "feishu_excel_document_id",
            "feishu_excel_path",
            "feishu_excel_uploaded_at",
            "feishu_pdf_file_token",
            "feishu_pdf_url",
            "feishu_pdf_document_id",
            "feishu_pdf_path",
            "feishu_pdf_uploaded_at",
            "created_at",
            "updated_at",
            "items",
            "versions",
        ]


class QuotationCreateSerializer(serializers.Serializer):
    quote_no = serializers.CharField()
    product_line = serializers.CharField(required=False, default="BDR")
    project_name = serializers.CharField()
    currency = serializers.CharField(required=False, default="USD")
    payment_term_option = serializers.CharField(required=False, default="CIA")
    payment_terms = serializers.CharField()
    quote_date = serializers.DateField()
    expire_date = serializers.DateField()
    tax_label = serializers.CharField(required=False, default="VAT")
    vat_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        default=Decimal("0"),
    )
    remarks_disclaimer = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    issuer_company_name = serializers.CharField(
        required=False, default="OnePro Cloud Limited"
    )
    issuer_contact_name = serializers.CharField()
    issuer_contact_email = serializers.CharField()
    issuer_contact_title = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    issuer_signature = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    client_company = serializers.CharField()
    contact_person = serializers.CharField()
    email = serializers.CharField()
    billing_company = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    billing_contact = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    billing_email = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    created_by_email = serializers.CharField(required=False, allow_null=True)
    items = QuotationItemWriteSerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs["expire_date"] < attrs["quote_date"]:
            raise serializers.ValidationError(
                {"expire_date": "Expiry date cannot be before quote date."}
            )
        return attrs


class QuotationUpdateSerializer(serializers.Serializer):
    quote_no = serializers.CharField(required=False)
    project_name = serializers.CharField(required=False)
    product_line = serializers.CharField(required=False)
    currency = serializers.CharField(required=False)
    payment_term_option = serializers.CharField(required=False)
    payment_terms = serializers.CharField(required=False)
    quote_date = serializers.DateField(required=False)
    expire_date = serializers.DateField(required=False)
    tax_label = serializers.CharField(required=False)
    vat_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
    )
    remarks_disclaimer = serializers.CharField(
        required=False, allow_blank=True
    )
    issuer_company_name = serializers.CharField(required=False)
    issuer_contact_name = serializers.CharField(required=False)
    issuer_contact_email = serializers.CharField(required=False)
    issuer_contact_title = serializers.CharField(
        required=False, allow_blank=True
    )
    issuer_signature = serializers.CharField(required=False, allow_blank=True)
    client_company = serializers.CharField(required=False)
    contact_person = serializers.CharField(required=False)
    email = serializers.CharField(required=False)
    billing_company = serializers.CharField(required=False, allow_blank=True)
    billing_contact = serializers.CharField(required=False, allow_blank=True)
    billing_email = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=[
            "draft",
            "generated",
            "uploaded",
            "sent",
            "accepted",
            "rejected",
            "expired",
            "cancelled",
        ],
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    skip_version = serializers.BooleanField(required=False, default=False)
    items = QuotationItemWriteSerializer(many=True, required=False)

    def validate(self, attrs):
        quotation = self.context.get("quotation")
        quote_date = attrs.get(
            "quote_date", getattr(quotation, "quote_date", None)
        )
        expire_date = attrs.get(
            "expire_date", getattr(quotation, "expire_date", None)
        )
        if quote_date and expire_date and expire_date < quote_date:
            raise serializers.ValidationError(
                {"expire_date": "Expiry date cannot be before quote date."}
            )
        return attrs


class QuotationGenerateSerializer(serializers.Serializer):
    operator_email = serializers.CharField(required=False, allow_null=True)
    notes = serializers.CharField(
        required=False, default="Generated quotation"
    )


class AuditEventSerializer(serializers.ModelSerializer):
    """Read-only representation of a Quote Desk audit event."""

    ip_address = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()

    def get_ip_address(self, obj: AuditEvent) -> str | None:
        request = self.context.get("request")
        if _can_view_sensitive_evidence(getattr(request, "user", None)):
            return str(obj.ip_address) if obj.ip_address else None
        return _mask_ip(obj.ip_address)

    def get_target_label(self, obj: AuditEvent) -> str:
        """Resolve a missing historical target to its quotation number."""
        if obj.target_label:
            return obj.target_label
        quotation_id = obj.quotation_id_snapshot
        if not quotation_id and obj.target_type == "quotation":
            quotation_id = obj.target_id
        document_id = obj.document_id_snapshot
        if not document_id and obj.target_type == "document":
            document_id = obj.target_id
        cache = self.context.setdefault("audit_target_label_cache", {})
        cache_key = (quotation_id or "", document_id or "")
        if cache_key not in cache:
            label = ""
            if quotation_id:
                label = (
                    Quotation.objects.filter(pk=quotation_id)
                    .values_list("quote_no", flat=True)
                    .first()
                    or ""
                )
            elif document_id:
                label = (
                    DocumentAsset.objects.filter(pk=document_id)
                    .values_list("quotation__quote_no", flat=True)
                    .first()
                    or ""
                )
            cache[cache_key] = label
        return cache[cache_key]

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_name",
            "actor_email",
            "actor_name",
            "actor_type",
            "actor_role_snapshot",
            "module",
            "action",
            "result",
            "reason_code",
            "risk_level",
            "target_type",
            "target_id",
            "target_label",
            "summary",
            "before_summary",
            "after_summary",
            "changes",
            "metadata",
            "request_id",
            "trace_id",
            "workspace_id",
            "quotation_id_snapshot",
            "document_id_snapshot",
            "storage_connection_id",
            "source_organization_id",
            "target_organization_id",
            "sync_job_id",
            "error_code",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields


def _can_view_sensitive_evidence(user) -> bool:
    """Return whether a user may inspect unmasked security evidence."""
    return can_manage_security_alerts(user)


def _mask_ip(value) -> str | None:
    """Mask the host portion of an IP address for general viewers."""
    if not value:
        return None
    text = str(value)
    if "." in text:
        parts = text.split(".")
        return ".".join([*parts[:3], "*"])
    groups = text.split(":")
    return ":".join(groups[:3]) + "::*"


def _device_label(user_agent: str) -> str:
    """Return a concise browser and operating-system label."""
    if not user_agent:
        return "Not available"
    browser = "Browser"
    for pattern, label in (
        (r"Edg/(\d+)", "Edge"),
        (r"Chrome/(\d+)", "Chrome"),
        (r"Firefox/(\d+)", "Firefox"),
        (r"Version/(\d+).+Safari/", "Safari"),
    ):
        match = re.search(pattern, user_agent)
        if match:
            browser = f"{label} {match.group(1)}"
            break
    if "Mac OS X" in user_agent:
        operating_system = "macOS"
    elif "Windows" in user_agent:
        operating_system = "Windows"
    elif "Android" in user_agent:
        operating_system = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        operating_system = "iOS"
    elif "Linux" in user_agent:
        operating_system = "Linux"
    else:
        operating_system = "Unknown OS"
    return f"{browser} · {operating_system}"


class SecurityAlertEvidenceSerializer(serializers.ModelSerializer):
    """Minimal audit evidence shown in a security alert timeline."""

    ip_address = serializers.SerializerMethodField()

    def get_ip_address(self, obj: AuditEvent) -> str | None:
        request = self.context.get("request")
        if _can_view_sensitive_evidence(getattr(request, "user", None)):
            return str(obj.ip_address) if obj.ip_address else None
        return _mask_ip(obj.ip_address)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "action",
            "module",
            "target_id",
            "target_label",
            "request_id",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields


class SecurityAlertSerializer(serializers.ModelSerializer):
    """List representation of a Quote Desk security alert."""

    alert_number = serializers.SerializerMethodField()
    source_ip = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    evidence_count = serializers.IntegerField(
        source="evidence_events.count",
        read_only=True,
    )

    def get_alert_number(self, obj: SecurityAlert) -> str:
        year = obj.created_at.year
        return f"SA-{year}-{obj.id:05d}"

    def get_source_ip(self, obj: SecurityAlert) -> str | None:
        request = self.context.get("request")
        if _can_view_sensitive_evidence(getattr(request, "user", None)):
            return str(obj.source_ip) if obj.source_ip else None
        return _mask_ip(obj.source_ip)

    def get_device(self, obj: SecurityAlert) -> str:
        request = self.context.get("request")
        if not _can_view_sensitive_evidence(
            getattr(request, "user", None)
        ):
            return ""
        return _device_label(obj.subject_user_agent)

    class Meta:
        model = SecurityAlert
        fields = [
            "id",
            "alert_number",
            "rule",
            "severity",
            "status",
            "title",
            "reason",
            "recommendation",
            "runbook",
            "owner",
            "threshold",
            "window_minutes",
            "subject_email",
            "subject_name",
            "source_ip",
            "device",
            "trigger_count",
            "evidence_count",
            "first_detected_at",
            "last_detected_at",
            "acknowledged_at",
            "resolved_at",
            "resolution",
            "resolution_note",
            "notify_affected_user",
        ]
        read_only_fields = fields


class SecurityAlertDetailSerializer(SecurityAlertSerializer):
    """Security alert including its immutable evidence timeline."""

    evidence = SecurityAlertEvidenceSerializer(
        source="evidence_events",
        many=True,
        read_only=True,
    )

    class Meta(SecurityAlertSerializer.Meta):
        fields = [*SecurityAlertSerializer.Meta.fields, "evidence"]


class SecurityAlertResolutionSerializer(serializers.Serializer):
    """Validate one administrative alert workflow action."""

    action = serializers.ChoiceField(choices=["acknowledge", "resolve"])
    resolution = serializers.ChoiceField(
        choices=SecurityAlert.RESOLUTION_CHOICES,
        required=False,
        allow_blank=True,
    )
    resolution_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=4000,
    )
    notify_affected_user = serializers.BooleanField(
        required=False,
        default=False,
    )

    def validate(self, attrs):
        if attrs["action"] != "resolve":
            return attrs
        if not attrs.get("resolution"):
            raise serializers.ValidationError(
                {"resolution": "Select a resolution."}
            )
        if not attrs.get("resolution_note", "").strip():
            raise serializers.ValidationError(
                {"resolution_note": "Add a resolution note."}
            )
        return attrs


class DocumentAssetSerializer(serializers.ModelSerializer):
    feishu_file_token = serializers.SerializerMethodField()
    feishu_url = serializers.SerializerMethodField()
    remote_access_available = serializers.SerializerMethodField()

    def get_feishu_file_token(self, obj: DocumentAsset) -> None:
        return None

    def get_feishu_url(self, obj: DocumentAsset) -> str | None:
        if obj.source != "feishu":
            return None
        return trusted_feishu_file_url(obj)

    def get_remote_access_available(self, obj: DocumentAsset) -> bool:
        if obj.source != "feishu":
            return bool(remote_document_reference(obj).token)
        return trusted_feishu_file_url(obj) is not None

    class Meta:
        model = DocumentAsset
        fields = [
            "id",
            "quotation_id",
            "doc_type",
            "file_name",
            "mime_type",
            "size_bytes",
            "source",
            "feishu_file_token",
            "feishu_url",
            "feishu_folder_path",
            "remote_access_available",
            "created_by_email",
            "created_at",
        ]
