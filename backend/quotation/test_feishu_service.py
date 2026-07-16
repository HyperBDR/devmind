from django.test import SimpleTestCase

from quotation.services.feishu_service import (
    chunk_file_tokens,
    classify_batch_query_results,
    normalize_bookmarks,
    suggest_unique_file_name,
)


class FeishuServiceTests(SimpleTestCase):
    def test_suggest_unique_file_name_preserves_extension(self):
        existing = {"Quote.xlsx", "Quote (1).xlsx"}

        assert (
            suggest_unique_file_name("Quote.xlsx", existing)
            == "Quote (2).xlsx"
        )

    def test_normalize_bookmarks_deduplicates_and_ignores_invalid_items(self):
        raw = [
            {"token": "folder-a", "name": "Sales"},
            {"token": "folder-a", "name": "Duplicate"},
            {"token": "folder-b", "name": ""},
            {"name": "Missing token"},
            "invalid",
        ]

        assert normalize_bookmarks(raw) == [
            {"token": "folder-a", "name": "Sales", "type": "folder"},
            {"token": "folder-b", "name": "folder-b", "type": "folder"},
        ]

    def test_chunk_file_tokens_uses_requested_batch_size(self):
        assert chunk_file_tokens(["a", "b", "c"], size=2) == [
            ["a", "b"],
            ["c"],
        ]

    def test_classify_batch_query_results_marks_known_missing_tokens(self):
        existing, missing = classify_batch_query_results(
            [{"doc_token": "alive"}],
            [{"token": "deleted", "code": 1061004}],
            ["alive", "deleted", "unreported"],
        )

        assert existing == {"alive"}
        assert missing == {"deleted", "unreported"}

    def test_classify_batch_query_results_keeps_unknown_failures_visible(self):
        existing, missing = classify_batch_query_results(
            [],
            [{"token": "temporarily-unavailable", "code": 999999}],
        )

        assert existing == {"temporarily-unavailable"}
        assert missing == set()
