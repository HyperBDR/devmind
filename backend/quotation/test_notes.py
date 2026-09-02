from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from quotation.models import Quotation, QuotationNote


class QuotationNoteAPITests(TestCase):
    """Quotation notes stay scoped to one accessible quotation."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username="note-owner",
            email="note-owner@example.com",
        )
        self.other = User.objects.create_user(
            username="note-other",
            email="note-other@example.com",
        )
        self.admin = User.objects.create_user(
            username="note-admin",
            email="note-admin@example.com",
            is_staff=True,
        )
        self.quotation = self._quotation("Q-NOTE-001")
        self.other_quotation = self._quotation("Q-NOTE-002")
        self.api = APIClient()

    def _quotation(self, quote_no: str) -> Quotation:
        return Quotation.objects.create(
            quote_no=quote_no,
            project_name="Notes project",
            quote_date="2026-09-01",
            expire_date="2026-10-01",
            issuer_contact_name=self.owner.username,
            issuer_contact_email=self.owner.email,
            client_company="Notes customer",
            contact_person="Customer contact",
            email="customer@example.com",
            created_by_email=self.owner.email,
        )

    def notes_url(self, quotation=None) -> str:
        quotation = quotation or self.quotation
        return f"/api/v1/quotation/quotations/{quotation.id}/notes"

    def authenticate(self, user) -> None:
        self.api.force_authenticate(user)

    def test_owner_can_create_and_list_note(self):
        self.authenticate(self.owner)

        created = self.api.post(
            self.notes_url(),
            {"content": "Confirm the customer scope."},
            format="json",
        )
        listed = self.api.get(self.notes_url())

        assert created.status_code == 201
        assert created.data["author_name"] == self.owner.username
        assert created.data["can_edit"] is True
        assert listed.status_code == 200
        assert listed.data["total"] == 1
        assert listed.data["items"][0]["content"] == (
            "Confirm the customer scope."
        )

    def test_notes_are_scoped_to_requested_quotation(self):
        QuotationNote.objects.create(
            quotation=self.other_quotation,
            author=self.owner,
            author_name=self.owner.username,
            author_email=self.owner.email,
            content="A different quote.",
        )
        self.authenticate(self.owner)

        response = self.api.get(self.notes_url())

        assert response.status_code == 200
        assert response.data["items"] == []

    def test_user_without_quote_access_cannot_read_notes(self):
        self.authenticate(self.other)

        response = self.api.get(self.notes_url())

        assert response.status_code == 403

    def test_author_can_update_and_delete_own_note(self):
        note = QuotationNote.objects.create(
            quotation=self.quotation,
            author=self.owner,
            author_name=self.owner.username,
            author_email=self.owner.email,
            content="Original note.",
        )
        detail_url = f"{self.notes_url()}/{note.id}"
        self.authenticate(self.owner)

        updated = self.api.put(
            detail_url,
            {"content": "Updated note."},
            format="json",
        )
        deleted = self.api.delete(detail_url)

        assert updated.status_code == 200
        assert updated.data["content"] == "Updated note."
        assert deleted.status_code == 204
        assert not QuotationNote.objects.filter(pk=note.id).exists()

    def test_non_author_and_admin_cannot_change_another_users_note(self):
        note = QuotationNote.objects.create(
            quotation=self.quotation,
            author=self.owner,
            author_name=self.owner.username,
            author_email=self.owner.email,
            content="Owner note.",
        )
        detail_url = f"{self.notes_url()}/{note.id}"
        self.quotation.issuer_contact_name = self.other.username
        self.quotation.save(update_fields=["issuer_contact_name"])
        self.authenticate(self.other)

        denied = self.api.put(
            detail_url,
            {"content": "Changed by another user."},
            format="json",
        )

        assert denied.status_code == 403
        self.authenticate(self.admin)
        admin_list = self.api.get(self.notes_url())
        admin_update = self.api.put(
            detail_url,
            {"content": "Changed by an administrator."},
            format="json",
        )
        admin_delete = self.api.delete(detail_url)

        assert admin_list.status_code == 200
        assert admin_list.data["items"][0]["can_edit"] is False
        assert admin_update.status_code == 403
        assert admin_delete.status_code == 403
        assert QuotationNote.objects.filter(pk=note.id).exists()

    def test_blank_note_is_rejected(self):
        self.authenticate(self.owner)

        response = self.api.post(
            self.notes_url(),
            {"content": "   "},
            format="json",
        )

        assert response.status_code == 400
