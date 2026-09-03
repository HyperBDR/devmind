from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase


class QuotationMigrationGraphTests(SimpleTestCase):
    databases = {"default"}

    def test_quotation_migrations_have_one_leaf(self):
        loader = MigrationLoader(connection, ignore_no_migrations=True)

        leaves = loader.graph.leaf_nodes("quotation")

        self.assertEqual(len(leaves), 1, leaves)
