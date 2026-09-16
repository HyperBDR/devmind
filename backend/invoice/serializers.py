import re
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from invoice.models import (
    Invoice,
    InvoiceDocumentPurpose,
    InvoiceItem,
    InvoiceNumberingMode,
    InvoiceSourceType,
    InvoiceStatus,
)
from invoice.services.documents import latest_downloadable_document
from invoice.services.financials import calculate_invoice_amounts
from invoice.services.numbering import (
    get_next_invoice_revision_number,
    reserve_next_invoice_number,
)
from invoice.services.pdf_renderer import (
    InvoicePdfRenderError,
    validate_signature_data_url,
)


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "line_no",
            "product_code",
            "product_name",
            "description",
            "quantity",
            "unit_price",
            "discount_amount",
            "net_amount",
            "tax_rate",
            "tax_amount",
            "total_amount",
        ]
        read_only_fields = [
            "id",
            "discount_amount",
            "net_amount",
            "tax_rate",
            "tax_amount",
            "total_amount",
        ]

    def validate_line_no(self, value):
        if value < 1:
            raise serializers.ValidationError("Must be at least 1.")
        return value

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Must be greater than 0.")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Must be at least 0.")
        return value


class InvoiceListQuerySerializer(serializers.Serializer):
    """Validate Invoice list filters."""

    search = serializers.CharField(
        allow_blank=True,
        default="",
        max_length=255,
        required=False,
        trim_whitespace=True,
    )
    customer = serializers.CharField(max_length=255, required=False)
    invoice_contact = serializers.CharField(
        max_length=120,
        required=False,
    )
    invoice_contact_email = serializers.CharField(
        max_length=254,
        allow_blank=True,
        required=False,
    )
    region = serializers.CharField(max_length=120, required=False)
    sales_owner = serializers.CharField(max_length=255, required=False)
    status = serializers.ChoiceField(
        choices=InvoiceStatus.choices,
        required=False,
    )
    source_type = serializers.ChoiceField(
        choices=InvoiceSourceType.choices,
        required=False,
    )
    currency = serializers.CharField(max_length=3, required=False)
    invoice_from = serializers.DateField(required=False)
    invoice_to = serializers.DateField(required=False)
    page = serializers.IntegerField(default=1, min_value=1, required=False)
    page_size = serializers.ChoiceField(
        choices=(10, 20, 50),
        default=10,
        required=False,
    )

    def validate(self, attrs):
        invoice_from = attrs.get("invoice_from")
        invoice_to = attrs.get("invoice_to")
        if invoice_from and invoice_to and invoice_from > invoice_to:
            raise serializers.ValidationError(
                {"invoice_to": "must be on or after invoice_from"}
            )
        return attrs


class InvoiceFormContextQuerySerializer(serializers.Serializer):
    """Validate parsed Invoice history pagination."""

    page = serializers.IntegerField(default=1, min_value=1, required=False)
    page_size = serializers.ChoiceField(
        choices=(20, 50),
        default=50,
        required=False,
    )


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, required=False)
    created_by_email = serializers.SerializerMethodField()
    pdf_available = serializers.SerializerMethodField()
    feishu_url = serializers.SerializerMethodField()
    issuer_signature = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=settings.INVOICE_MAX_SIGNATURE_LENGTH,
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_no",
            "revision_no",
            "document_kind",
            "numbering_mode",
            "product_line",
            "invoice_date",
            "due_date",
            "status",
            "source_type",
            "currency",
            "seller_name",
            "seller_tax_id",
            "seller_address",
            "seller_website",
            "seller_email",
            "customer_name",
            "customer_tax_id",
            "customer_address",
            "customer_contact_person",
            "customer_contact_email",
            "customer_contact_phone",
            "contact_person",
            "contact_email",
            "purchase_order_no",
            "payment_terms",
            "region",
            "sales_owner",
            "tax_rate",
            "subtotal_amount",
            "tax_amount",
            "total_amount",
            "notes",
            "additional_notes",
            "remarks",
            "bank_account_name",
            "bank_name",
            "bank_address",
            "bank_account_number",
            "bank_code",
            "bank_branch_code",
            "bank_swift_code",
            "remittance_instruction",
            "signatory_name",
            "signatory_title",
            "issuer_signature",
            "pdf_available",
            "feishu_url",
            "created_by_email",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = [
            "id",
            "revision_no",
            "document_kind",
            "source_type",
            "subtotal_amount",
            "tax_amount",
            "total_amount",
            "pdf_available",
            "feishu_url",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "invoice_no": {
                "allow_blank": True,
                "required": False,
            },
            "invoice_date": {
                "allow_null": False,
                "required": True,
            },
            "customer_name": {
                "allow_blank": False,
                "required": True,
            },
        }

    def get_created_by_email(self, invoice):
        user = invoice.created_by
        return (user.email or user.username).lower() if user else ""

    def get_pdf_available(self, invoice):
        return latest_downloadable_document(invoice) is not None

    def get_feishu_url(self, invoice):
        documents = [
            document
            for document in invoice.documents.all()
            if document.feishu_url
            and document.purpose
            in {
                InvoiceDocumentPurpose.ISSUED,
                InvoiceDocumentPurpose.SOURCE,
            }
        ]
        documents.sort(
            key=lambda document: (
                document.purpose == InvoiceDocumentPurpose.ISSUED,
                document.created_at,
            ),
            reverse=True,
        )
        return documents[0].feishu_url if documents else ""

    def validate_currency(self, value):
        currency = value.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise serializers.ValidationError(
                "Use a three-letter currency code."
            )
        return currency

    def validate_tax_rate(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                "Must be between 0 and 100."
            )
        return value

    def validate_product_line(self, value):
        product_line = value.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,11}", product_line):
            raise serializers.ValidationError(
                "Use 2-12 letters or numbers, starting with a letter."
            )
        return product_line

    def validate_issuer_signature(self, value):
        try:
            return validate_signature_data_url(value)
        except InvoicePdfRenderError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        requested_number = str(
            attrs.get(
                "invoice_no",
                self.instance.invoice_no if self.instance else "",
            )
        ).strip()
        default_mode = (
            self.instance.numbering_mode
            if self.instance
            else (
                InvoiceNumberingMode.CUSTOM
                if requested_number
                else InvoiceNumberingMode.AUTO
            )
        )
        numbering_mode = attrs.get("numbering_mode", default_mode)
        attrs["numbering_mode"] = numbering_mode
        if self.instance is None:
            if numbering_mode == InvoiceNumberingMode.AUTO:
                attrs.pop("invoice_no", None)
            elif not requested_number:
                raise serializers.ValidationError(
                    {"invoice_no": "A custom invoice number is required."}
                )
        else:
            if numbering_mode != self.instance.numbering_mode:
                raise serializers.ValidationError(
                    {
                        "numbering_mode": (
                            "The numbering mode cannot be changed after "
                            "the invoice is created."
                        )
                    }
                )
            if (
                numbering_mode == InvoiceNumberingMode.AUTO
                and requested_number
                and requested_number != self.instance.invoice_no
            ):
                raise serializers.ValidationError(
                    {
                        "invoice_no": (
                            "An automatically assigned invoice number "
                            "cannot be changed."
                        )
                    }
                )
            if numbering_mode == InvoiceNumberingMode.AUTO:
                attrs.pop("invoice_no", None)
        status = attrs.get(
            "status",
            self.instance.status if self.instance else InvoiceStatus.DRAFT,
        )
        items = attrs.get("items")
        if self.instance is None and status not in {
            InvoiceStatus.DRAFT,
            InvoiceStatus.ISSUED,
        }:
            raise serializers.ValidationError(
                {"status": "New invoices must be saved as draft or issued."}
            )
        if (
            self.instance is not None
            and self.instance.status == InvoiceStatus.DRAFT
            and status not in {InvoiceStatus.DRAFT, InvoiceStatus.ISSUED}
        ):
            raise serializers.ValidationError(
                {"status": "Draft invoices can only be saved or issued."}
            )
        if (
            self.instance is not None
            and self.instance.status in {
                InvoiceStatus.ISSUED,
                InvoiceStatus.PAID,
            }
            and status != self.instance.status
        ):
            raise serializers.ValidationError(
                {"status": "Formal invoices cannot change status when edited."}
            )
        if items is not None:
            line_numbers = [item["line_no"] for item in items]
            if len(line_numbers) != len(set(line_numbers)):
                raise serializers.ValidationError(
                    {"items": "Line numbers must be unique."}
                )
        has_items = bool(items)
        if items is None and self.instance is not None:
            has_items = self.instance.items.exists()
        if status == InvoiceStatus.ISSUED and not has_items:
            raise serializers.ValidationError(
                {"items": "An issued invoice requires at least one item."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items", [])
        items, totals = calculate_invoice_amounts(
            items,
            validated_data.get("tax_rate", Decimal("0")),
        )
        validated_data.update(totals)
        if (
            validated_data.get("numbering_mode")
            == InvoiceNumberingMode.AUTO
        ):
            validated_data["invoice_no"] = reserve_next_invoice_number(
                validated_data["invoice_date"],
                validated_data.get("product_line", "BDR"),
            )
        invoice = Invoice.objects.create(
            created_by=self.context["request"].user,
            source_type=InvoiceSourceType.MANUAL,
            **validated_data,
        )
        InvoiceItem.objects.bulk_create(
            [InvoiceItem(invoice=invoice, **item) for item in items]
        )
        return invoice

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        formal_revision = self.context.get("formal_revision", False)
        numbering_scope_changed = (
            instance.numbering_mode == InvoiceNumberingMode.AUTO
            and (
                validated_data.get("invoice_date", instance.invoice_date)
                != instance.invoice_date
                or validated_data.get("product_line", instance.product_line)
                != instance.product_line
            )
        )
        if formal_revision:
            invoice_no, revision_no = get_next_invoice_revision_number(
                instance
            )
            validated_data["invoice_no"] = invoice_no
            validated_data["revision_no"] = revision_no
        elif numbering_scope_changed:
            validated_data["invoice_no"] = reserve_next_invoice_number(
                validated_data.get("invoice_date", instance.invoice_date),
                validated_data.get("product_line", instance.product_line),
            )
        tax_rate_changed = "tax_rate" in validated_data
        tax_rate = validated_data.get("tax_rate", instance.tax_rate)
        if items is None and tax_rate_changed:
            items = [
                {
                    "line_no": item.line_no,
                    "product_code": item.product_code,
                    "product_name": item.product_name,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in instance.items.all()
            ]
        if items is not None:
            items, totals = calculate_invoice_amounts(items, tax_rate)
            validated_data.update(totals)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            InvoiceItem.objects.bulk_create(
                [InvoiceItem(invoice=instance, **item) for item in items]
            )
        return instance


class InvoiceParseResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    status = serializers.CharField()
    parser_name = serializers.CharField()
    parser_version = serializers.CharField()
    confidence = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
    )
    normalized = serializers.JSONField(source="normalized_json")
    field_confidence = serializers.JSONField(source="field_confidence_json")
    validation_errors = serializers.JSONField(
        source="validation_errors_json"
    )
    validation_warnings = serializers.JSONField(
        source="validation_warnings_json"
    )
