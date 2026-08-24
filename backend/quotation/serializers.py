from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote, urlparse

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from quotation.models import (
    AuditEvent,
    DocumentAsset,
    DocumentParseResult,
    ItemType,
    Quotation,
    QuotationItem,
    QuotationVersion,
    ReplicaSyncStatus,
    UserQuotationCatalog,
)
from quotation.permissions import (
    can_delete_any_quotation_document,
    is_quotation_admin,
    user_display_email,
)
from quotation.services.storage_control import remote_document_reference

MAX_QUOTATION_AMOUNT = Decimal("9999999999999999.99")


def _validate_total_amounts(attrs, quotation: Quotation | None = None) -> None:
    """Reject quotation totals that exceed database decimal precision."""
    items = attrs.get("items")
    if items is None:
        if quotation is None or "vat_rate" not in attrs:
            return
        extended_prices = [
            item.extended_price for item in quotation.items.all()
        ]
    else:
        extended_prices = [item["extended_price"] for item in items]

    subtotal = sum(extended_prices, start=Decimal("0"))
    vat_rate = attrs.get(
        "vat_rate",
        getattr(quotation, "vat_rate", Decimal("0")),
    )
    vat_amount = (subtotal * Decimal(vat_rate) / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if (
        subtotal > MAX_QUOTATION_AMOUNT
        or vat_amount > MAX_QUOTATION_AMOUNT
        or subtotal + vat_amount > MAX_QUOTATION_AMOUNT
    ):
        raise serializers.ValidationError(
            {
                "items": (
                    "Calculated quotation totals exceed the supported "
                    f"amount limit of {MAX_QUOTATION_AMOUNT}."
                )
            }
        )


class DashboardCurrencyQuerySerializer(serializers.Serializer):
    """Validate the currency used by dashboard amount aggregates."""

    currency = serializers.RegexField(
        regex=r"^[A-Z0-9]{3,10}$",
        default="USD",
        required=False,
    )

    date_from = serializers.RegexField(
        regex=r"^\d{4}-\d{2}$",
        allow_blank=True,
        default="",
        required=False,
    )
    date_to = serializers.RegexField(
        regex=r"^\d{4}-\d{2}$",
        allow_blank=True,
        default="",
        required=False,
    )

    def validate(self, attrs):
        """Validate an optional inclusive calendar-month range."""
        for field in ("date_from", "date_to"):
            value = attrs.get(field, "")
            if value:
                try:
                    date.fromisoformat(f"{value}-01")
                except ValueError as exc:
                    raise serializers.ValidationError(
                        {field: "must be a valid calendar month"}
                    ) from exc
        if attrs.get("date_from") and attrs.get("date_to"):
            if attrs["date_from"] > attrs["date_to"]:
                raise serializers.ValidationError(
                    {"date_to": "must not be before date_from"}
                )
        return attrs


class DashboardSummaryQuerySerializer(DashboardCurrencyQuerySerializer):
    """Validate optional currency plus selected calendar month."""

    period = serializers.RegexField(
        regex=r"^\d{4}-(?:0[1-9]|1[0-2])$",
        allow_blank=True,
        default="",
        required=False,
    )

    def validate_period(self, value):
        """Reject year values that cannot form a calendar date."""
        if value:
            try:
                date.fromisoformat(f"{value}-01")
            except ValueError as exc:
                raise serializers.ValidationError(
                    "must be a valid calendar month"
                ) from exc
        return value


class DashboardRecentQuerySerializer(serializers.Serializer):
    """Validate the bounded recent quotation list size."""

    limit = serializers.IntegerField(
        default=5,
        max_value=20,
        min_value=1,
        required=False,
    )


class QuotationListQuerySerializer(serializers.Serializer):
    """Validate quotation list pagination and database filters."""

    search = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=255,
        required=False,
        trim_whitespace=True,
    )
    status = serializers.ChoiceField(
        choices=Quotation._meta.get_field("status").choices,
        required=False,
    )
    product_line = serializers.CharField(
        max_length=40,
        required=False,
    )
    product_line_name = serializers.CharField(
        max_length=120,
        required=False,
    )
    source_type = serializers.ChoiceField(
        choices=Quotation._meta.get_field("source_type").choices,
        required=False,
    )
    currency = serializers.CharField(max_length=12, required=False)
    created_from = serializers.DateField(required=False)
    created_to = serializers.DateField(required=False)
    page = serializers.IntegerField(default=1, min_value=1, required=False)
    page_size = serializers.ChoiceField(
        choices=(10, 20, 50),
        default=10,
        required=False,
    )

    def validate(self, attrs):
        created_from = attrs.get("created_from")
        created_to = attrs.get("created_to")
        if created_from and created_to and created_from > created_to:
            raise serializers.ValidationError(
                {"created_to": "must be on or after created_from"}
            )
        return attrs


class QuotationFormContextQuerySerializer(serializers.Serializer):
    """Validate paginated parsed quotation history requests."""

    page = serializers.IntegerField(default=1, min_value=1, required=False)
    page_size = serializers.ChoiceField(
        choices=(20, 50, 100),
        default=20,
        required=False,
    )


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


class QuotationItemListSerializer(serializers.ListSerializer):
    """Validate bounded line-item collections before persistence."""

    def validate(self, attrs):
        """Reject oversized collections and duplicate line numbers."""
        if len(attrs) > settings.QUOTATION_MAX_ITEMS:
            raise serializers.ValidationError(
                "Ensure this list has no more than "
                f"{settings.QUOTATION_MAX_ITEMS} items."
            )
        line_numbers = [item["line_no"] for item in attrs]
        if len(line_numbers) != len(set(line_numbers)):
            raise serializers.ValidationError("Each line_no must be unique.")
        return attrs


class QuotationItemWriteSerializer(serializers.Serializer):
    line_no = serializers.IntegerField(
        min_value=1,
        max_value=2147483647,
    )
    type = serializers.ChoiceField(choices=ItemType.choices)
    item_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=QuotationItem._meta.get_field("item_id").max_length,
    )
    name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=QuotationItem._meta.get_field("name").max_length,
    )
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=settings.QUOTATION_MAX_ITEM_DESCRIPTION_LENGTH,
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

    class Meta:
        list_serializer_class = QuotationItemListSerializer

    def validate(self, attrs):
        list_price = attrs.get("list_price", Decimal("0"))
        discount = attrs.get("discount_percent", Decimal("0"))
        qty = attrs.get("qty", Decimal("1"))
        net_unit_price = (
            list_price * (Decimal("1") - discount / Decimal("100"))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        attrs["net_unit_price"] = net_unit_price
        extended_price = net_unit_price * qty
        if extended_price > MAX_QUOTATION_AMOUNT:
            raise serializers.ValidationError(
                {
                    "extended_price": (
                        "Ensure this value is less than or equal to "
                        f"{MAX_QUOTATION_AMOUNT}."
                    )
                }
            )
        attrs["extended_price"] = extended_price.quantize(
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


class QuotationListDocumentSerializer(serializers.Serializer):
    """Serialize the original document behind an imported quotation."""

    id = serializers.CharField(read_only=True)
    doc_type = serializers.ChoiceField(
        choices=("excel", "pdf"),
        read_only=True,
    )
    file_name = serializers.CharField(read_only=True)
    version_no = serializers.IntegerField(read_only=True)


class QuotationListVersionSerializer(serializers.Serializer):
    """Serialize a revision without returning its full snapshot."""

    version_no = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class QuotationListSerializer(serializers.ModelSerializer):
    """Serialize only fields required by the paginated list."""

    display_quote_no = serializers.SerializerMethodField()
    item_count = serializers.IntegerField(read_only=True)
    latest_excel_document_id = serializers.CharField(
        allow_null=True,
        read_only=True,
    )
    latest_pdf_document_id = serializers.CharField(
        allow_null=True,
        read_only=True,
    )
    source_document_type = serializers.CharField(
        allow_null=True,
        read_only=True,
    )
    source_document = QuotationListDocumentSerializer(
        allow_null=True,
        read_only=True,
    )
    available_versions = QuotationListVersionSerializer(
        many=True,
        read_only=True,
    )

    def get_display_quote_no(self, obj: Quotation) -> str:
        return obj.source_quote_no or obj.quote_no

    class Meta:
        model = Quotation
        fields = [
            "id",
            "quote_no",
            "display_quote_no",
            "project_name",
            "client_company",
            "contact_person",
            "quote_date",
            "created_at",
            "currency",
            "grand_total",
            "status",
            "source_type",
            "source_document_type",
            "source_document",
            "available_versions",
            "product_line",
            "product_line_name",
            "issuer_contact_name",
            "item_count",
            "latest_excel_document_id",
            "latest_pdf_document_id",
        ]
        read_only_fields = fields


class QuotationFormContextSerializer(serializers.ModelSerializer):
    """Serialize lightweight history fields used by the create form."""

    display_quote_no = serializers.SerializerMethodField()

    def get_display_quote_no(self, obj: Quotation) -> str:
        return obj.source_quote_no or obj.quote_no

    class Meta:
        model = Quotation
        fields = [
            "id",
            "quote_no",
            "display_quote_no",
            "project_name",
            "client_company",
            "contact_person",
            "email",
            "product_line",
            "product_line_name",
            "billing_company",
            "billing_contact",
            "billing_email",
            "currency",
            "tax_label",
            "issuer_contact_name",
            "issuer_contact_email",
            "created_by_email",
            "created_at",
        ]
        read_only_fields = fields


class QuotationLineItemHistorySerializer(serializers.Serializer):
    """Serialize parsed line-item history used by the create form."""

    type = serializers.CharField()
    description = serializers.CharField()
    list_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
    )
    currency = serializers.CharField()


class QuotationSerializer(serializers.ModelSerializer):
    display_quote_no = serializers.SerializerMethodField()
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
    source_document_type = serializers.SerializerMethodField()

    def get_display_quote_no(self, obj: Quotation) -> str:
        return obj.source_quote_no or obj.quote_no

    def get_source_document_type(self, obj: Quotation) -> str | None:
        if obj.source_type != "document_import":
            return None

        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get(
            "documents"
        )
        if prefetched is not None:
            imported = [
                document
                for document in prefetched
                if document.source == "feishu"
                and document.doc_type in {"excel", "pdf"}
            ]
            latest = max(
                imported,
                key=lambda document: document.created_at,
                default=None,
            )
        else:
            latest = (
                obj.documents.filter(
                    source="feishu",
                    doc_type__in=["excel", "pdf"],
                )
                .order_by("-created_at")
                .first()
            )
        return latest.doc_type if latest else None

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
                if remote_document_reference(document).token
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
            qs = obj.documents.all()
            if doc_type:
                qs = qs.filter(doc_type=doc_type)
            remote_reference_filter = (
                Q(feishu_file_token__isnull=False) & ~Q(feishu_file_token="")
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
            "display_quote_no",
            "source_quote_no",
            "status",
            "version_current",
            "source_type",
            "source_document_type",
            "product_line",
            "product_line_name",
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
    numbering_mode = serializers.ChoiceField(
        choices=("auto", "custom"),
        required=False,
        default="custom",
    )
    quote_no = serializers.CharField(
        max_length=Quotation._meta.get_field("quote_no").max_length,
    )
    product_line = serializers.CharField(
        allow_blank=True,
        required=False,
        default="BDR",
        max_length=Quotation._meta.get_field("product_line").max_length,
    )
    product_line_name = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        max_length=Quotation._meta.get_field("product_line_name").max_length,
    )
    project_name = serializers.CharField(
        max_length=Quotation._meta.get_field("project_name").max_length,
    )
    currency = serializers.ChoiceField(
        choices=settings.QUOTATION_ALLOWED_CURRENCIES,
        required=False,
        default="USD",
    )
    payment_term_option = serializers.ChoiceField(
        choices=("CIA", "NET 30", "NET 45", "NET 60", "Mixed", "Others"),
        required=False,
        default="CIA",
    )
    payment_terms = serializers.CharField(
        max_length=Quotation._meta.get_field("payment_terms").max_length,
    )
    quote_date = serializers.DateField()
    expire_date = serializers.DateField()
    tax_label = serializers.CharField(
        required=False,
        default="VAT",
        max_length=Quotation._meta.get_field("tax_label").max_length,
    )
    vat_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        default=Decimal("0"),
    )
    remarks_disclaimer = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=settings.QUOTATION_MAX_REMARKS_LENGTH,
    )
    issuer_company_name = serializers.CharField(
        required=False,
        default="OnePro Cloud Limited",
        max_length=Quotation._meta.get_field("issuer_company_name").max_length,
    )
    issuer_contact_name = serializers.CharField(
        allow_blank=True,
        max_length=Quotation._meta.get_field("issuer_contact_name").max_length,
    )
    issuer_contact_email = serializers.EmailField(
        allow_blank=True,
        max_length=Quotation._meta.get_field(
            "issuer_contact_email"
        ).max_length,
    )
    issuer_contact_title = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=Quotation._meta.get_field(
            "issuer_contact_title"
        ).max_length,
    )
    issuer_signature = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=settings.QUOTATION_MAX_SIGNATURE_LENGTH,
    )
    client_company = serializers.CharField(
        max_length=Quotation._meta.get_field("client_company").max_length,
    )
    contact_person = serializers.CharField(
        allow_blank=True,
        max_length=Quotation._meta.get_field("contact_person").max_length,
    )
    email = serializers.EmailField(
        allow_blank=True,
        max_length=Quotation._meta.get_field("email").max_length,
    )
    billing_company = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=Quotation._meta.get_field("billing_company").max_length,
    )
    billing_contact = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=Quotation._meta.get_field("billing_contact").max_length,
    )
    billing_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        default="",
        max_length=Quotation._meta.get_field("billing_email").max_length,
    )
    created_by_email = serializers.EmailField(
        required=False,
        allow_null=True,
        max_length=Quotation._meta.get_field("created_by_email").max_length,
    )
    items = QuotationItemWriteSerializer(many=True, required=False)

    def validate(self, attrs):
        if not self.context.get("document_import"):
            for field in (
                "contact_person",
                "email",
                "issuer_contact_name",
                "issuer_contact_email",
            ):
                if not attrs.get(field, "").strip():
                    raise serializers.ValidationError(
                        {field: "This field may not be blank."}
                    )
        if attrs["expire_date"] < attrs["quote_date"]:
            raise serializers.ValidationError(
                {"expire_date": "Expiry date cannot be before quote date."}
            )
        _validate_total_amounts(attrs)
        return attrs


class QuotationUpdateSerializer(serializers.Serializer):
    quote_no = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("quote_no").max_length,
    )
    project_name = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("project_name").max_length,
    )
    product_line = serializers.CharField(
        allow_blank=True,
        required=False,
        max_length=Quotation._meta.get_field("product_line").max_length,
    )
    product_line_name = serializers.CharField(
        allow_blank=True,
        required=False,
        max_length=Quotation._meta.get_field("product_line_name").max_length,
    )
    currency = serializers.ChoiceField(
        choices=settings.QUOTATION_ALLOWED_CURRENCIES,
        required=False,
    )
    payment_term_option = serializers.ChoiceField(
        choices=("CIA", "NET 30", "NET 45", "NET 60", "Mixed", "Others"),
        required=False,
    )
    payment_terms = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("payment_terms").max_length,
    )
    quote_date = serializers.DateField(required=False)
    expire_date = serializers.DateField(required=False)
    tax_label = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("tax_label").max_length,
    )
    vat_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
    )
    remarks_disclaimer = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=settings.QUOTATION_MAX_REMARKS_LENGTH,
    )
    issuer_company_name = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("issuer_company_name").max_length,
    )
    issuer_contact_name = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("issuer_contact_name").max_length,
    )
    issuer_contact_email = serializers.EmailField(
        required=False,
        max_length=Quotation._meta.get_field(
            "issuer_contact_email"
        ).max_length,
    )
    issuer_contact_title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Quotation._meta.get_field(
            "issuer_contact_title"
        ).max_length,
    )
    issuer_signature = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=settings.QUOTATION_MAX_SIGNATURE_LENGTH,
    )
    client_company = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("client_company").max_length,
    )
    contact_person = serializers.CharField(
        required=False,
        max_length=Quotation._meta.get_field("contact_person").max_length,
    )
    email = serializers.EmailField(
        required=False,
        max_length=Quotation._meta.get_field("email").max_length,
    )
    billing_company = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Quotation._meta.get_field("billing_company").max_length,
    )
    billing_contact = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=Quotation._meta.get_field("billing_contact").max_length,
    )
    billing_email = serializers.EmailField(
        required=False,
        allow_blank=True,
        max_length=Quotation._meta.get_field("billing_email").max_length,
    )
    status = serializers.ChoiceField(
        choices=Quotation._meta.get_field("status").choices,
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
        _validate_total_amounts(attrs, quotation)
        return attrs


class QuotationGenerateSerializer(serializers.Serializer):
    operator_email = serializers.CharField(required=False, allow_null=True)
    notes = serializers.CharField(
        required=False, default="Generated quotation"
    )


class AuditEventSerializer(serializers.ModelSerializer):
    """Read-only representation of a Quote Desk audit event."""

    ip_address = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()

    def _terminal_sync_event(self, obj: AuditEvent) -> AuditEvent | None:
        """Return the terminal event paired with a sync request."""
        if (
            obj.event_name != "storage.archive_sync_requested"
            or not obj.sync_job_id
        ):
            return None
        cache = self.context.setdefault("audit_terminal_sync_cache", {})
        if obj.sync_job_id not in cache:
            cache[obj.sync_job_id] = (
                AuditEvent.objects.filter(sync_job_id=obj.sync_job_id)
                .exclude(pk=obj.pk)
                .filter(
                    event_name__in=[
                        "storage.archive_sync_succeeded",
                        "storage.archive_sync_partially_succeeded",
                        "storage.archive_sync_failed",
                    ]
                )
                .order_by("-created_at", "-id")
                .first()
            )
        return cache[obj.sync_job_id]

    def get_ip_address(self, obj: AuditEvent) -> str | None:
        request = self.context.get("request")
        if _can_view_sensitive_evidence(getattr(request, "user", None)):
            return str(obj.ip_address) if obj.ip_address else None
        return _mask_ip(obj.ip_address)

    def get_metadata(self, obj: AuditEvent) -> dict:
        """Include the final counters when serializing a sync request."""
        metadata = dict(obj.metadata or {})
        terminal = self._terminal_sync_event(obj)
        if terminal and isinstance(terminal.metadata, dict):
            metadata.update(terminal.metadata)
        return metadata

    def get_target_label(self, obj: AuditEvent) -> str:
        """Resolve a missing historical target to its quotation number."""
        if obj.target_label:
            return obj.target_label
        terminal = self._terminal_sync_event(obj)
        if terminal and terminal.target_label:
            return terminal.target_label
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
    """Return whether a user may inspect unmasked audit evidence."""
    return is_quotation_admin(user)


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


class DocumentAssetSerializer(serializers.ModelSerializer):
    feishu_file_token = serializers.SerializerMethodField()
    feishu_url = serializers.SerializerMethodField()
    remote_access_available = serializers.SerializerMethodField()
    parse_result_id = serializers.SerializerMethodField()
    parse_status = serializers.SerializerMethodField()
    parse_confidence = serializers.SerializerMethodField()
    parsed_quotation_id = serializers.SerializerMethodField()
    parsed_quote_no = serializers.SerializerMethodField()
    can_archive = serializers.SerializerMethodField()
    can_restore = serializers.SerializerMethodField()

    def _latest_parse_result(
        self, obj: DocumentAsset
    ) -> DocumentParseResult | None:
        if hasattr(obj, "_latest_parse_result_for_serializer"):
            return obj._latest_parse_result_for_serializer
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get(
            "parse_results"
        )
        if prefetched is not None:
            result = max(
                prefetched,
                key=lambda item: (item.created_at, item.id),
                default=None,
            )
        else:
            result = obj.parse_results.order_by("-created_at", "-id").first()
        obj._latest_parse_result_for_serializer = result
        return result

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

    def get_parse_result_id(self, obj: DocumentAsset) -> str | None:
        result = self._latest_parse_result(obj)
        return result.id if result else None

    def get_parse_status(self, obj: DocumentAsset) -> str:
        result = self._latest_parse_result(obj)
        return result.status if result else "unparsed"

    def get_parse_confidence(self, obj: DocumentAsset):
        result = self._latest_parse_result(obj)
        return result.confidence if result else None

    def get_parsed_quotation_id(self, obj: DocumentAsset) -> str | None:
        result = self._latest_parse_result(obj)
        return result.quotation_id if result else None

    def get_parsed_quote_no(self, obj: DocumentAsset) -> str | None:
        result = self._latest_parse_result(obj)
        if result:
            quote_no = str(
                result.normalized_json.get("quote_no") or ""
            ).strip()
            if quote_no:
                return quote_no
        quotation = obj.quotation
        if quotation is None:
            return None
        return quotation.source_quote_no or quotation.quote_no

    def get_can_archive(self, obj: DocumentAsset) -> bool:
        return (
            obj.lifecycle_state == "active"
            and not obj.legal_hold_at
            and self._can_manage_lifecycle(obj)
        )

    def _can_manage_lifecycle(self, obj: DocumentAsset) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        owner = (obj.created_by_email or "").lower()
        if owner and owner == user_display_email(request.user):
            return True
        if not hasattr(self, "_can_delete_any_document"):
            self._can_delete_any_document = (
                can_delete_any_quotation_document(request.user)
            )
        return self._can_delete_any_document

    def get_can_restore(self, obj: DocumentAsset) -> bool:
        request = self.context.get("request")
        if (
            request is None
            or obj.lifecycle_state != "archived"
            or (
                obj.purge_after is not None
                and obj.purge_after <= timezone.now()
            )
        ):
            return False
        return self._can_manage_lifecycle(obj)

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
            "parse_result_id",
            "parse_status",
            "parse_confidence",
            "parsed_quotation_id",
            "parsed_quote_no",
            "created_by_email",
            "lifecycle_state",
            "archived_at",
            "purge_after",
            "legal_hold_at",
            "can_archive",
            "can_restore",
            "created_at",
        ]


class DocumentParseResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentParseResult
        fields = [
            "id",
            "asset_id",
            "sync_job_id",
            "quotation_id",
            "status",
            "parser_name",
            "parser_version",
            "content_hash",
            "normalized_json",
            "source_totals_json",
            "field_confidence_json",
            "validation_errors_json",
            "validation_warnings_json",
            "confidence",
            "created_by_email",
            "confirmed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
