from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from rest_framework import serializers

from quotation.models import (
    DocumentAsset,
    Quotation,
    QuotationItem,
    QuotationVersion,
    UserQuotationCatalog,
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
    return f"{base_url}/file/{token}"


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
                and document.feishu_file_token
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
            latest = (
                qs.exclude(feishu_file_token__isnull=True)
                .exclude(feishu_file_token="")
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
            "file_token": latest.feishu_file_token,
            "url": latest.feishu_url
            or build_feishu_file_url(latest.feishu_file_token),
            "path": latest.file_name,
            "uploaded_at": latest.created_at,
        }

    def get_feishu_file_token(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        return latest.feishu_file_token if latest else None

    def get_feishu_url(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        if not latest:
            return None
        return latest.feishu_url or build_feishu_file_url(
            latest.feishu_file_token
        )

    def get_feishu_path(self, obj: Quotation) -> str | None:
        latest = self._latest_feishu_upload(obj)
        return latest.file_name if latest else None

    def get_feishu_uploaded_at(self, obj: Quotation):
        latest = self._latest_feishu_upload(obj)
        return latest.created_at if latest else None

    def get_feishu_excel_file_token(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "excel").get("file_token")

    def get_feishu_excel_url(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "excel").get("url")

    def get_feishu_excel_path(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "excel").get("path")

    def get_feishu_excel_uploaded_at(self, obj: Quotation):
        return self._feishu_asset_data(obj, "excel").get("uploaded_at")

    def get_feishu_pdf_file_token(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "pdf").get("file_token")

    def get_feishu_pdf_url(self, obj: Quotation) -> str | None:
        return self._feishu_asset_data(obj, "pdf").get("url")

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
            "feishu_path",
            "feishu_uploaded_at",
            "feishu_excel_file_token",
            "feishu_excel_url",
            "feishu_excel_path",
            "feishu_excel_uploaded_at",
            "feishu_pdf_file_token",
            "feishu_pdf_url",
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


class DocumentAssetSerializer(serializers.ModelSerializer):
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
            "created_by_email",
            "created_at",
        ]
