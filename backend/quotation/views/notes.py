from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.access import can_access_quotation, forbidden_response
from quotation.audit import quotation_audit_label, set_request_audit_target
from quotation.models import Quotation, QuotationNote
from quotation.permissions import user_display_email
from quotation.serializers import (
    QuotationNoteSerializer,
    QuotationNoteWriteSerializer,
)


def _quotation_or_response(user, quotation_id: str):
    quotation = Quotation.objects.filter(pk=quotation_id).first()
    if quotation is None:
        return None, Response(
            {"detail": "quotation not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not can_access_quotation(user, quotation):
        return None, forbidden_response()
    return quotation, None


def _author_name(user) -> str:
    return user.get_full_name().strip() or user.username or user.email


class QuotationNoteListCreateView(APIView):
    """List or create internal notes for one accessible quotation."""

    permission_classes = [IsAuthenticated]

    def get(self, request, quotation_id: str):
        quotation, denied = _quotation_or_response(
            request.user,
            quotation_id,
        )
        if denied:
            return denied
        notes = quotation.notes.select_related("author").all()
        serializer = QuotationNoteSerializer(
            notes,
            many=True,
            context={"request": request},
        )
        return Response({"items": serializer.data, "total": notes.count()})

    def post(self, request, quotation_id: str):
        quotation, denied = _quotation_or_response(
            request.user,
            quotation_id,
        )
        if denied:
            return denied
        serializer = QuotationNoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = QuotationNote.objects.create(
            quotation=quotation,
            author=request.user,
            author_name=_author_name(request.user),
            author_email=user_display_email(request.user),
            content=serializer.validated_data["content"],
        )
        set_request_audit_target(
            request,
            target_id=quotation.id,
            target_label=quotation_audit_label(quotation),
        )
        return Response(
            QuotationNoteSerializer(
                note,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class QuotationNoteDetailView(APIView):
    """Update or delete a note owned by the current user."""

    permission_classes = [IsAuthenticated]

    def get_note(self, quotation_id: str, note_id: str) -> QuotationNote:
        return get_object_or_404(
            QuotationNote.objects.select_related("quotation", "author"),
            pk=note_id,
            quotation_id=quotation_id,
        )

    def ensure_access(self, request, note: QuotationNote):
        if not can_access_quotation(request.user, note.quotation):
            return forbidden_response()
        if note.author_id != request.user.id:
            return Response(
                {"detail": "only the author can change this note"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def put(self, request, quotation_id: str, note_id: str):
        note = self.get_note(quotation_id, note_id)
        denied = self.ensure_access(request, note)
        if denied:
            return denied
        serializer = QuotationNoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note.content = serializer.validated_data["content"]
        note.save(update_fields=["content", "updated_at"])
        set_request_audit_target(
            request,
            target_id=note.quotation_id,
            target_label=quotation_audit_label(note.quotation),
        )
        return Response(
            QuotationNoteSerializer(
                note,
                context={"request": request},
            ).data
        )

    def delete(self, request, quotation_id: str, note_id: str):
        note = self.get_note(quotation_id, note_id)
        denied = self.ensure_access(request, note)
        if denied:
            return denied
        set_request_audit_target(
            request,
            target_id=note.quotation_id,
            target_label=quotation_audit_label(note.quotation),
        )
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
