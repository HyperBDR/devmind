from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from invoice.models import (
    Invoice,
    InvoiceDocument,
    InvoiceSourceType,
    InvoiceSyncRun,
    InvoiceStatus,
)
from invoice.permissions import (
    HasInvoiceAccess,
    HasInvoiceImportAccess,
    InvoiceCapability,
    has_invoice_capability,
    invoice_visibility_filter,
)
from invoice.services.analytics import sales_dashboard
from invoice.services.documents import (
    generate_issued_invoice_pdf,
    invoice_storage,
    latest_downloadable_document,
)
from invoice.services.revisions import record_invoice_revision
from invoice.services.feishu_upload import (
    InvoiceFeishuUploadError,
    invoice_feishu_targets,
    upload_invoice_to_feishu,
)
from invoice.services.pdf_renderer import InvoicePdfRenderError
from invoice.serializers import (
    InvoiceFormContextQuerySerializer,
    InvoiceListQuerySerializer,
    InvoiceSerializer,
)
from invoice.tasks import enqueue_invoice_feishu_sync
from quotation.audit import record_audit_event
from quotation.models import AuditEvent
from quotation.services.document_parsing.business_fields import (
    normalize_contact_email,
    normalize_contact_name,
)
from quotation.services.feishu_client import FeishuAPIError


def _record_document_audit(request, invoice, document, action):
    event_names = {
        "download": "invoice.downloaded",
        "generate": "invoice.generated",
    }
    record_audit_event(
        request=request,
        module="invoice",
        action=action,
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type="invoice",
        target_id=invoice.id,
        target_label=invoice.invoice_no,
        document_id=document.id,
        event_name=event_names[action],
        summary=(
            "Generated formal Commercial Invoice PDF."
            if action == "generate"
            else "Downloaded formal Commercial Invoice PDF."
        ),
    )


def _invoice_items_snapshot(invoice):
    return tuple(
        (
            item.line_no,
            item.product_code,
            item.product_name,
            item.description,
            item.quantity,
            item.unit_price,
        )
        for item in invoice.items.all().order_by("line_no", "id")
    )


def _require_capability(request, capability: str, message: str) -> None:
    if not has_invoice_capability(request.user, capability):
        raise PermissionDenied(message)


def _sync_run_data(run: InvoiceSyncRun, *, reused: bool = False) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "discovered_count": run.discovered_count,
        "created_count": run.created_count,
        "reused_count": run.reused_count,
        "skipped_count": run.skipped_count,
        "failed_count": run.failed_count,
        "error_message": run.error_message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
        "reused": reused,
    }


class InvoiceListCreateView(APIView):
    permission_classes = [HasInvoiceAccess]

    def get(self, request):
        query_serializer = InvoiceListQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        page = filters["page"]
        page_size = int(filters["page_size"])
        queryset = (
            Invoice.objects.select_related("created_by")
            .prefetch_related("items", "documents")
            .order_by("-invoice_date", "-created_at", "-id")
        )
        queryset = queryset.filter(invoice_visibility_filter(request.user))
        contact_facets = {}
        for contact in queryset.filter(contact_person__gt="").values(
            "contact_person",
            "contact_email",
        ):
            name = normalize_contact_name(contact["contact_person"])
            if not name:
                continue
            email = normalize_contact_email(contact["contact_email"])
            contact_facets.setdefault(name, set()).add(email)
        facets = {
            "currencies": list(
                queryset.exclude(currency="")
                .values_list("currency", flat=True)
                .order_by("currency")
                .distinct()[:100]
            ),
            "sales_owners": list(
                queryset.exclude(sales_owner="")
                .values_list("sales_owner", flat=True)
                .order_by("sales_owner")
                .distinct()[:100]
            ),
            "invoice_contacts": [
                {
                    "name": name,
                    "email": next(iter(emails)) if len(emails) == 1 else "",
                }
                for name, emails in sorted(contact_facets.items())
            ][:100],
        }
        search = filters.get("search")
        if search:
            queryset = queryset.filter(
                Q(invoice_no__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(contact_person__icontains=search)
                | Q(contact_email__icontains=search)
                | Q(customer_address__icontains=search)
                | Q(purchase_order_no__icontains=search)
                | Q(region__icontains=search)
                | Q(sales_owner__icontains=search)
                | Q(items__product_name__icontains=search)
            ).distinct()
        for field in (
            "customer_name",
            "region",
            "sales_owner",
            "status",
            "source_type",
            "currency",
        ):
            filter_key = "customer" if field == "customer_name" else field
            value = filters.get(filter_key)
            if value:
                queryset = queryset.filter(**{field: value})
        if filters.get("invoice_contact"):
            queryset = queryset.filter(
                contact_person=filters["invoice_contact"],
            )
        if filters.get("invoice_contact_email"):
            queryset = queryset.filter(
                contact_email=filters["invoice_contact_email"],
            )
        if filters.get("invoice_from"):
            queryset = queryset.filter(
                invoice_date__gte=filters["invoice_from"]
            )
        if filters.get("invoice_to"):
            queryset = queryset.filter(
                invoice_date__lte=filters["invoice_to"]
            )
        total = queryset.count()
        page_start = (page - 1) * page_size
        items = queryset[page_start : page_start + page_size]
        total_pages = (total + page_size - 1) // page_size
        return Response(
            {
                "items": InvoiceSerializer(items, many=True).data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "facets": facets,
            }
        )

    def post(self, request):
        _require_capability(
            request,
            InvoiceCapability.EDIT,
            "Invoice edit permission is required.",
        )
        if request.data.get("status") == InvoiceStatus.ISSUED:
            _require_capability(
                request,
                InvoiceCapability.ISSUE,
                "Invoice issue permission is required.",
            )
        serializer = InvoiceSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        copy_from_id = str(
            serializer.validated_data.pop("copy_from_id", "") or ""
        )
        copy_source = None
        if copy_from_id:
            copy_source = (
                Invoice.objects.filter(
                    invoice_visibility_filter(request.user),
                    pk=copy_from_id,
                    source_type=InvoiceSourceType.MANUAL,
                )
                .only("id")
                .first()
            )
            if copy_source is None:
                return Response(
                    {"copy_from_id": "Invoice cannot be copied."},
                    status=409,
                )
        generated_document = None
        try:
            with transaction.atomic():
                invoice = serializer.save()
                if invoice.status == InvoiceStatus.ISSUED:
                    generated_document = generate_issued_invoice_pdf(
                        invoice,
                        actor=request.user,
                    )
        except IntegrityError:
            return Response(
                {"invoice_no": "This invoice number already exists."},
                status=400,
            )
        except InvoicePdfRenderError as exc:
            return Response({"detail": str(exc)}, status=400)
        if generated_document is not None and not copy_source:
            _record_document_audit(
                request,
                invoice,
                generated_document,
                "generate",
            )
        if copy_source:
            record_audit_event(
                request=request,
                module="invoice",
                action="copy",
                result=AuditEvent.RESULT_SUCCEEDED,
                target_type="invoice",
                target_id=invoice.id,
                target_label=invoice.invoice_no,
                event_name="invoice.copied",
                metadata={"copy_from_id": copy_source.id},
            )
        return Response(InvoiceSerializer(invoice).data, status=201)


class InvoiceDetailView(APIView):
    permission_classes = [HasInvoiceAccess]

    def get_object(self, request, invoice_id):
        return get_object_or_404(
            Invoice.objects.select_related("created_by").prefetch_related(
                "items", "documents"
            ).filter(invoice_visibility_filter(request.user)),
            pk=invoice_id,
        )

    def get(self, request, invoice_id):
        invoice = self.get_object(request, invoice_id)
        return Response(InvoiceSerializer(invoice).data)

    def patch(self, request, invoice_id):
        _require_capability(
            request,
            InvoiceCapability.EDIT,
            "Invoice edit permission is required.",
        )
        if request.data.get("status") == InvoiceStatus.ISSUED:
            _require_capability(
                request,
                InvoiceCapability.ISSUE,
                "Invoice issue permission is required.",
            )
        invoice = self.get_object(request, invoice_id)
        if invoice.status not in {
            InvoiceStatus.DRAFT,
            InvoiceStatus.ISSUED,
            InvoiceStatus.PAID,
        }:
            return Response(
                {"detail": "This invoice status cannot be edited."},
                status=400,
            )
        content_keys = set(request.data) - {"status", "revision_reason"}
        formal_revision = (
            invoice.status in {InvoiceStatus.ISSUED, InvoiceStatus.PAID}
            and bool(content_keys)
        )
        serializer = InvoiceSerializer(
            invoice,
            data=request.data,
            partial=True,
            context={
                "request": request,
                "formal_revision": formal_revision,
            },
        )
        serializer.is_valid(raise_exception=True)
        requested_fields = sorted(
            str(field)
            for field in request.data
            if field != "revision_reason"
        )
        generated_document = None
        try:
            with transaction.atomic():
                invoice = Invoice.objects.select_for_update().prefetch_related(
                    "items", "documents"
                ).get(pk=invoice.id)
                before_values = {
                    field: getattr(invoice, field)
                    for field in requested_fields
                    if field != "items"
                }
                before_items = (
                    _invoice_items_snapshot(invoice)
                    if "items" in requested_fields
                    else None
                )
                if formal_revision:
                    record_invoice_revision(
                        invoice,
                        changed_by=request.user,
                        reason=str(request.data.get("revision_reason") or ""),
                    )
                    serializer.instance = invoice
                invoice = serializer.save()
                changed_fields = [
                    field
                    for field in requested_fields
                    if (
                        _invoice_items_snapshot(invoice) != before_items
                        if field == "items"
                        else getattr(invoice, field) != before_values[field]
                    )
                ]
                if (
                    invoice.status
                    in {InvoiceStatus.ISSUED, InvoiceStatus.PAID}
                    and (
                        formal_revision
                        or invoice.status == InvoiceStatus.ISSUED
                    )
                ):
                    generated_document = generate_issued_invoice_pdf(
                        invoice,
                        actor=request.user,
                    )
        except IntegrityError:
            return Response(
                {"invoice_no": "This invoice number already exists."},
                status=400,
            )
        except InvoicePdfRenderError as exc:
            return Response({"detail": str(exc)}, status=400)
        if generated_document is not None:
            _record_document_audit(
                request,
                invoice,
                generated_document,
                "generate",
            )
            invoice = self.get_object(request, invoice.id)
        if changed_fields:
            record_audit_event(
                request=request,
                module="invoice",
                action="update",
                result=AuditEvent.RESULT_SUCCEEDED,
                target_type="invoice",
                target_id=invoice.id,
                target_label=invoice.invoice_no,
                event_name="invoice.updated",
                changes={"fields": changed_fields},
            )
        return Response(InvoiceSerializer(invoice).data)

    def delete(self, request, invoice_id):
        _require_capability(
            request,
            InvoiceCapability.EDIT,
            "Invoice edit permission is required.",
        )
        invoice = self.get_object(request, invoice_id)
        if invoice.source_type != InvoiceSourceType.MANUAL:
            return Response(
                {"detail": "Only invoices created here can be deleted."},
                status=409,
            )
        documents = list(invoice.documents.all())
        storage_keys = [document.storage_key for document in documents]
        with transaction.atomic():
            InvoiceDocument.objects.filter(invoice=invoice).delete()
            invoice.delete()

            def cleanup_local_files():
                storage = invoice_storage()
                for storage_key in storage_keys:
                    try:
                        storage.delete(storage_key)
                    except (OSError, ValueError):
                        continue

            transaction.on_commit(cleanup_local_files, robust=True)
        record_audit_event(
            request=request,
            module="invoice",
            action="delete",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="invoice",
            target_id=invoice_id,
            target_label=invoice.invoice_no,
            event_name="invoice.deleted",
            summary="Deleted a locally created invoice.",
        )
        return Response(status=204)


class InvoiceFeishuUploadView(APIView):
    permission_classes = [HasInvoiceAccess]

    def get(self, request, invoice_id):
        _require_capability(
            request,
            InvoiceCapability.ISSUE,
            "Invoice issue permission is required to view Feishu folders.",
        )
        get_object_or_404(
            Invoice.objects.filter(invoice_visibility_filter(request.user)),
            pk=invoice_id,
        )
        try:
            return Response(
                invoice_feishu_targets(
                    request.query_params.get("folder_token", ""),
                    actor=request.user,
                )
            )
        except (InvoiceFeishuUploadError, FeishuAPIError) as exc:
            return Response({"detail": str(exc)}, status=400)

    def post(self, request, invoice_id):
        _require_capability(
            request,
            InvoiceCapability.ISSUE,
            "Invoice issue permission is required to upload to Feishu.",
        )
        invoice = get_object_or_404(
            Invoice.objects.prefetch_related("items", "documents").filter(
                invoice_visibility_filter(request.user)
            ),
            pk=invoice_id,
        )
        try:
            document, reused = upload_invoice_to_feishu(
                invoice,
                actor=request.user,
                folder_token=str(request.data.get("folder_token") or ""),
            )
        except InvoiceFeishuUploadError as exc:
            return Response({"detail": str(exc)}, status=400)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        invoice = Invoice.objects.prefetch_related(
            "items", "documents"
        ).filter(invoice_visibility_filter(request.user)).get(pk=invoice.id)
        record_audit_event(
            request=request,
            module="feishu",
            action="upload",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="invoice",
            target_id=invoice.id,
            target_label=invoice.invoice_no,
            document_id=document.id,
            event_name="invoice.uploaded_to_feishu",
            summary=(
                "Reused the existing Feishu invoice file."
                if reused
                else "Uploaded the invoice PDF to Feishu."
            ),
        )
        return Response(InvoiceSerializer(invoice).data)


class InvoiceFormContextView(APIView):
    """Return parsed Invoice history used by the create form."""

    permission_classes = [HasInvoiceAccess]

    def get(self, request):
        query_serializer = InvoiceFormContextQuerySerializer(
            data=request.query_params,
        )
        query_serializer.is_valid(raise_exception=True)
        page = query_serializer.validated_data["page"]
        page_size = int(query_serializer.validated_data["page_size"])
        queryset = (
            Invoice.objects.exclude(source_type=InvoiceSourceType.MANUAL)
            .select_related("created_by")
            .prefetch_related("items", "documents")
            .order_by("-invoice_date", "-created_at", "-id")
        )
        queryset = queryset.filter(invoice_visibility_filter(request.user))
        total = queryset.count()
        page_start = (page - 1) * page_size
        items = queryset[page_start : page_start + page_size]
        return Response(
            {
                "items": InvoiceSerializer(items, many=True).data,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            }
        )


class InvoiceFeishuSyncView(APIView):
    permission_classes = [HasInvoiceImportAccess]

    def get(self, request):
        run = InvoiceSyncRun.objects.first()
        return Response(_sync_run_data(run) if run else None)

    def post(self, request):
        from invoice.services.feishu_sync import configured_folder_token

        try:
            configured_folder_token()
            run, reused = enqueue_invoice_feishu_sync(actor=request.user)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception:
            return Response(
                {"detail": "Invoice synchronization could not be queued."},
                status=503,
            )
        return Response(
            _sync_run_data(run, reused=reused),
            status=200 if reused else 202,
        )


class InvoicePdfView(APIView):
    permission_classes = [HasInvoiceAccess]

    def get_object(self, request, invoice_id):
        return get_object_or_404(
            Invoice.objects.prefetch_related("items", "documents").filter(
                invoice_visibility_filter(request.user)
            ),
            pk=invoice_id,
        )

    def get(self, request, invoice_id):
        invoice = self.get_object(request, invoice_id)
        document = latest_downloadable_document(invoice)
        if document is None:
            return Response(
                {"detail": "generated invoice PDF not found"},
                status=404,
            )
        path = invoice_storage().resolve(document.storage_key)
        if not path.is_file():
            return Response(
                {"detail": "generated invoice PDF is missing"},
                status=404,
            )
        _record_document_audit(
            request,
            invoice,
            document,
            "download",
        )
        return FileResponse(
            path.open("rb"),
            as_attachment=True,
            filename=document.file_name,
            content_type="application/pdf",
        )


class InvoiceSalesDashboardView(APIView):
    permission_classes = [HasInvoiceAccess]

    def get(self, request):
        granularity = request.query_params.get("granularity", "month")
        currency = request.query_params.get("currency") or None
        comparison_years = request.query_params.get("comparison_years", "2")
        start_date = request.query_params.get("start_date") or None
        end_date = request.query_params.get("end_date") or None
        try:
            data = sales_dashboard(
                currency=currency,
                user=request.user,
                granularity=granularity,
                comparison_years=int(comparison_years),
                start_date=date.fromisoformat(start_date)
                if start_date else None,
                end_date=date.fromisoformat(end_date)
                if end_date else None,
            )
        except (TypeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(data)
