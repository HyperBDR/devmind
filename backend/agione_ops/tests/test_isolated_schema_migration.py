"""Bridge old recorded migration histories using only private in-memory DBs."""

from copy import deepcopy
from importlib import import_module
from unittest.mock import Mock

import pytest
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

bridge = import_module("agione_ops.migrations.0002_isolated_workspace_schema")
TABLES = {table for _, table in bridge.MODEL_TABLES}


@pytest.fixture
def private_schema_connection(django_db_blocker):
    """A separate literal :memory: alias can never address the user's DB."""

    alias = "agione_schema_bridge_memory"
    assert alias not in connections.databases
    config = deepcopy(connections.databases["default"])
    config.update(
        {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
            "AUTOCOMMIT": True,
            "ATOMIC_REQUESTS": False,
        }
    )
    connections.databases[alias] = config
    with django_db_blocker.unblock():
        connection = connections[alias]
        assert connection.settings_dict["NAME"] == ":memory:"
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([("agione_ops", "0001_initial")])
            yield connection
        finally:
            connection.close()
            del connections[alias]
            connections.databases.pop(alias)


def historical_state(connection):
    """Use migration models, not runtime managers or domain imports."""

    executor = MigrationExecutor(connection)
    return executor.loader.project_state([("agione_ops", "0001_initial")]).apps


def tables(connection):
    with connection.cursor() as cursor:
        return set(connection.introspection.table_names(cursor))


def make_legacy_marker(connection):
    """Simulate unrelated previous AGIOne data without inspecting real data."""

    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE TABLE agione_ops_connection "
            "(id integer PRIMARY KEY, note text NOT NULL)"
        )
        cursor.execute(
            "INSERT INTO agione_ops_connection (id, note) VALUES (%s, %s)",
            [1, "synthetic legacy data must survive"],
        )
        cursor.execute(
            "CREATE TABLE agione_ops_syncrun "
            "(id integer PRIMARY KEY, note text NOT NULL)"
        )
        cursor.execute(
            "INSERT INTO agione_ops_syncrun (id, note) VALUES (%s, %s)",
            [1, "synthetic old task"],
        )


def assert_legacy_markers(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT note FROM agione_ops_connection WHERE id = 1")
        assert cursor.fetchone() == ("synthetic legacy data must survive",)
        cursor.execute("SELECT note FROM agione_ops_syncrun WHERE id = 1")
        assert cursor.fetchone() == ("synthetic old task",)


def test_old_recorded_initial_history_adds_only_new_namespace(
    private_schema_connection,
):
    """Keep the recorder at 0001, but simulate the unrelated old table set."""

    connection = private_schema_connection
    apps = historical_state(connection)
    with connection.schema_editor() as editor:
        for name, _ in reversed(bridge.MODEL_TABLES):
            editor.delete_model(apps.get_model("agione_ops", name))
    assert not tables(connection).intersection(TABLES)
    make_legacy_marker(connection)
    before = tables(connection)
    executor = MigrationExecutor(connection)
    assert ("agione_ops", "0001_initial") in executor.loader.applied_migrations
    executor.migrate([("agione_ops", "0002_isolated_workspace_schema")])
    assert tables(connection) == before | TABLES
    assert_legacy_markers(connection)
    for model_name, table in bridge.MODEL_TABLES:
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(
                    cursor,
                    table,
                )
            }
        model = apps.get_model("agione_ops", model_name)
        assert {
            field.column for field in model._meta.local_concrete_fields
        } <= columns


def test_complete_fresh_namespace_is_verified_without_any_create(
    private_schema_connection,
):
    """Fresh 0001 already created the tables, so the bridge must be a no-op."""

    connection = private_schema_connection
    apps = historical_state(connection)
    make_legacy_marker(connection)
    before = tables(connection)
    with connection.schema_editor() as editor:
        editor.create_model = Mock(
            side_effect=AssertionError("Unexpected DDL")
        )
        bridge.ensure_isolated_schema(apps, editor)
        editor.create_model.assert_not_called()
    assert tables(connection) == before
    assert_legacy_markers(connection)


def test_partial_namespace_fails_closed_without_repair(
    private_schema_connection,
):
    connection = private_schema_connection
    apps = historical_state(connection)
    make_legacy_marker(connection)
    with connection.schema_editor() as editor:
        editor.delete_model(apps.get_model("agione_ops", "VersionCall"))
    before = tables(connection)
    with connection.schema_editor() as editor:
        editor.create_model = Mock(
            side_effect=AssertionError("Unexpected DDL")
        )
        with pytest.raises(RuntimeError, match="Partial isolated"):
            bridge.ensure_isolated_schema(apps, editor)
        editor.create_model.assert_not_called()
    assert tables(connection) == before
    assert_legacy_markers(connection)


def test_complete_but_incompatible_namespace_is_not_adopted(
    private_schema_connection,
):
    connection = private_schema_connection
    apps = historical_state(connection)
    model = apps.get_model("agione_ops", "VersionCall")
    with connection.schema_editor() as editor:
        editor.delete_model(model)
        editor.execute(
            "CREATE TABLE devmind_agione_version_call "
            "(id integer PRIMARY KEY)"
        )
    before = tables(connection)
    with connection.schema_editor() as editor:
        editor.create_model = Mock(
            side_effect=AssertionError("Unexpected DDL")
        )
        with pytest.raises(RuntimeError, match="incompatible columns"):
            bridge.ensure_isolated_schema(apps, editor)
        editor.create_model.assert_not_called()
    assert tables(connection) == before


def test_all_explicit_names_are_in_the_new_namespace(
    private_schema_connection,
):
    apps = historical_state(private_schema_connection)
    for name, table in bridge.MODEL_TABLES:
        model = apps.get_model("agione_ops", name)
        assert model._meta.db_table == table
        assert table.startswith("devmind_agione_")
        for item in [*model._meta.constraints, *model._meta.indexes]:
            assert item.name.startswith("dm_agione_")


def test_reverse_bridge_is_a_noop():
    from django.db import migrations

    operation = bridge.Migration.operations[0]
    assert operation.reverse_code is migrations.RunPython.noop
