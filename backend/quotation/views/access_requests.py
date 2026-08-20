from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import can_access_document
from quotation.audit import record_audit_event
from quotation.models import (
    AuditEvent,
    QuotationAccessRequest,
    QuotationAccessRequestStatus,
    QuotationAccessRequestType,
)
from quotation.permissions import is_quotation_platform_admin
from quotation.services.permission_service import (
    access_request_target_values,
    approve_access_request,
    close_access_request,
    document_rows,
    reject_access_request,
    safe_folder_rows,
)

DECISION_SUMMARIES = {
    "approve": "Access request approved.",
    "reject": "Access request rejected.",
    "revoke": "Access request revoked.",
    "expire": "Access request expired.",
}


def _request_row(access_request: QuotationAccessRequest, user) -> dict:
    is_admin = is_quotation_platform_admin(user)
    document_name_allowed = bool(
        access_request.document
        and (is_admin or can_access_document(user, access_request.document))
    )
    if access_request.request_type == QuotationAccessRequestType.DOCUMENT_VIEW:
        target_id = access_request.document_id_snapshot
        target_name = (
            access_request.document_name
            if document_name_allowed
            else "Specific document"
        )
    else:
        target_id = access_request.folder_token
        target_name = access_request.folder_name
    status = access_request.status
    if (
        status == QuotationAccessRequestStatus.APPROVED
        and access_request.expires_at
        and access_request.expires_at <= timezone.now()
    ):
        status = QuotationAccessRequestStatus.EXPIRED
    return {
        "id": access_request.id,
        "applicant_id": access_request.applicant_id,
        "applicant": (
            access_request.applicant.get_full_name()
            or access_request.applicant.username
        ),
        "request_type": access_request.request_type,
        "target_id": target_id,
        "target_name": target_name,
        "reason": access_request.reason,
        "status": status,
        "reviewer": (
            access_request.reviewed_by.get_full_name()
            or access_request.reviewed_by.username
            if access_request.reviewed_by
            else ""
        ),
        "review_note": access_request.review_note,
        "expires_at": access_request.expires_at,
        "created_at": access_request.created_at,
        "updated_at": access_request.updated_at,
        "reviewed_at": access_request.reviewed_at,
        "revoked_at": access_request.revoked_at,
        "expired_at": access_request.expired_at,
    }


def _record_permission_grant(
    request,
    access_request: QuotationAccessRequest,
    permission,
    created: bool,
) -> None:
    is_upload = (
        access_request.request_type == QuotationAccessRequestType.FOLDER_UPLOAD
    )
    record_audit_event(
        request=request,
        module="permissions",
        action="grant_upload" if is_upload else "grant_view",
        result=AuditEvent.RESULT_SUCCEEDED,
        target_type=(
            "folder_upload_permission" if is_upload else "view_permission"
        ),
        target_id=str(permission.id),
        target_label=(
            access_request.folder_name or access_request.document_name
        ),
        summary="Granted access through an approved request.",
        changes={"created": created},
    )


class QuotationAccessRequestView(APIView):
    """List and submit quotation access requests."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        is_admin = is_quotation_platform_admin(request.user)
        requests = QuotationAccessRequest.objects.select_related(
            "applicant",
            "document",
            "reviewed_by",
        )
        if not is_admin:
            requests = requests.filter(applicant=request.user)
        return Response(
            {
                "is_admin": is_admin,
                "folders": safe_folder_rows(),
                "documents": document_rows() if is_admin else [],
                "requests": [
                    _request_row(access_request, request.user)
                    for access_request in requests
                ],
            }
        )

    def post(self, request):
        request_type = str(request.data.get("request_type") or "").strip()
        target_id = str(request.data.get("target_id") or "").strip()
        reason = str(request.data.get("reason") or "").strip()
        if request_type not in QuotationAccessRequestType.values:
            raise ValidationError(
                {"request_type": "Unsupported access request type."}
            )
        if not target_id:
            raise ValidationError({"target_id": "A target is required."})
        if not reason:
            raise ValidationError({"reason": "A reason is required."})
        if len(reason) > 2000:
            raise ValidationError(
                {"reason": "Reason must not exceed 2000 characters."}
            )

        values = access_request_target_values(request_type, target_id)
        duplicate_filters = {
            "applicant": request.user,
            "request_type": request_type,
            "status": QuotationAccessRequestStatus.PENDING,
        }
        if request_type == QuotationAccessRequestType.DOCUMENT_VIEW:
            duplicate_filters["document_id_snapshot"] = values[
                "document_id_snapshot"
            ]
        else:
            duplicate_filters["folder_token"] = values["folder_token"]
        if QuotationAccessRequest.objects.filter(**duplicate_filters).exists():
            self._duplicate_request()
        try:
            with transaction.atomic():
                access_request = QuotationAccessRequest.objects.create(
                    applicant=request.user,
                    request_type=request_type,
                    reason=reason,
                    **values,
                )
        except IntegrityError:
            self._duplicate_request()
        record_audit_event(
            request=request,
            module="access_requests",
            action="submit",
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="access_request",
            target_id=str(access_request.id),
            target_label=access_request.folder_name or "Specific document",
            summary="Submitted a quotation access request.",
        )
        return Response(
            _request_row(access_request, request.user),
            status=201,
        )

    @staticmethod
    def _duplicate_request() -> None:
        raise ValidationError(
            {"detail": "An equivalent access request is already pending."}
        )


class QuotationAccessRequestDecisionView(APIView):
    """Apply an administrator decision to one access request."""

    permission_classes = [IsAuthenticated]

    def post(self, request, request_id: int):
        if not is_quotation_platform_admin(request.user):
            raise PermissionDenied(
                "Only quotation platform administrators can review requests."
            )
        action = str(request.data.get("action") or "").strip()
        if action not in DECISION_SUMMARIES:
            raise ValidationError({"action": "Unsupported decision action."})
        review_note = str(request.data.get("review_note") or "").strip()
        if len(review_note) > 2000:
            raise ValidationError({"review_note": "Review note is too long."})
        with transaction.atomic():
            access_request = (
                QuotationAccessRequest.objects.select_for_update(of=("self",))
                .select_related(
                    "applicant",
                    "document",
                    "reviewed_by",
                    "view_permission",
                    "upload_permission",
                )
                .filter(pk=request_id)
                .first()
            )
            if access_request is None:
                raise ValidationError("Access request not found.")
            if action == "approve":
                created, permission = approve_access_request(
                    access_request,
                    request.user,
                    request.data.get("expires_at"),
                )
            elif action == "reject":
                reject_access_request(access_request, request.user)
                created, permission = False, None
            else:
                close_access_request(
                    access_request,
                    request.user,
                    action,
                )
                created, permission = False, None
            access_request.review_note = review_note
            access_request.save(update_fields=["review_note", "updated_at"])
        if permission is not None:
            _record_permission_grant(
                request,
                access_request,
                permission,
                created,
            )
        record_audit_event(
            request=request,
            module="access_requests",
            action=action,
            result=AuditEvent.RESULT_SUCCEEDED,
            target_type="access_request",
            target_id=str(access_request.id),
            target_label=access_request.folder_name or "Specific document",
            summary=DECISION_SUMMARIES[action],
        )
        return Response(_request_row(access_request, request.user))
