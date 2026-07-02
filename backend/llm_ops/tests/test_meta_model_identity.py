from django.test import SimpleTestCase

from llm_ops.constants import canonical_meta_model_identity


class MetaModelIdentityTests(SimpleTestCase):
    def test_supplier_namespace_is_removed_from_meta_model_name(self):
        identity = canonical_meta_model_identity(
            "siliconflow/deepseek-v3.1-terminus",
            "siliconflow/deepseek-v3.1-terminus",
        )

        self.assertEqual(identity["code"], "deepseek-v3.1-terminus")
        self.assertEqual(identity["name"], "deepseek-v3.1-terminus")
        self.assertIn(
            "siliconflow/deepseek-v3.1-terminus",
            identity["aliases"],
        )
