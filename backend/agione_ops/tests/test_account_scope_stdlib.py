"""Verify account classification without persisting email addresses."""
import unittest

from agione_ops.native_account_scope import classify_account, include_external


class AccountScopeTest(unittest.TestCase):
    def test_verified_email_and_identity(self):
        identity = {"userId": "2", "tenantId": "1", "email": "a@ONEPROCLOUD.COM"}
        self.assertEqual(classify_account(identity, "1", "2"), "internal")
        for domain in ("oneprocloud.test", "oneprocloud.cn", "onepro.cloud"):
            self.assertEqual(classify_account({**identity, "email": "a@" + domain}, "1", "2"), "internal")
        self.assertEqual(classify_account({**identity, "email": "a@example.org"}, "1", "2"), "external")

    def test_unknown_remains_visible_in_external_scope(self):
        self.assertTrue(include_external("external"))
        self.assertTrue(include_external("unknown"))
        self.assertFalse(include_external("internal"))

    def test_missing_invalid_or_mismatched_identity_is_unknown(self):
        for identity in (None, {}, {"userId": "2", "tenantId": "1", "email": ""},
                         {"userId": "2", "tenantId": "1", "email": "bad@"},
                         {"userId": "2", "tenantId": "9", "email": "a@example.org"},
                         {"userId": "3", "tenantId": "1", "email": "a@example.org"}):
            self.assertEqual(classify_account(identity, "1", "2"), "unknown")

    def test_classifies_each_tenant_user_and_filters_internal(self):
        from agione_ops.native_account_scope import classify_rows, external_rows

        rows = [
            {"customer_id": "1", "user_id": "2", "subject_type": "USER"},
            {"customer_id": "1", "user_id": "2", "subject_type": "USER"},
            {"customer_id": "3", "user_id": "2", "subject_type": "USER"},
            {"customer_id": "1", "user_id": "4", "subject_type": "PROJECT"},
        ]
        calls = []

        def lookup(uid):
            calls.append(uid)
            return {"userId": uid, "tenantId": "1", "email": "a@onepro.cloud"}

        types = classify_rows(rows, lookup)
        self.assertEqual(types, {"1:2": "internal", "3:2": "unknown"})
        self.assertEqual(calls, ["2"])
        self.assertEqual(external_rows(rows, types), rows[2:])
        self.assertEqual(external_rows(rows, {}), rows)
        self.assertNotIn("a@", str(types))

    def test_transient_unknown_does_not_erase_known_internal(self):
        from agione_ops.native_account_scope import merge_account_types
        old = {"1:2": "internal", "1:3": "external"}
        self.assertEqual(
            merge_account_types(old, {"1:2": "unknown", "1:3": "internal"}),
            {"1:2": "internal", "1:3": "internal"},
        )

    def test_finance_tenant_filter_uses_only_admin_email(self):
        from agione_ops.native_account_scope import external_finance_directory
        rows = [
            {"tenantId": "1", "adminEmail": "X@oneprocloud.cn"},
            {"tenantId": "2", "adminEmail": "customer@example.com"},
            {"tenantId": "3", "adminEmail": None},
            {"tenantId": "4", "adminEmail": "invalid"},
        ]
        self.assertEqual(external_finance_directory(rows), {"2", "3", "4"})
