from pathlib import Path

import pytest

from ai_assistant.contracts import AssistantCapability, AssistantTool
from ai_assistant.skills import SkillCatalog, load_skills


def _tool(name: str) -> AssistantTool:
    return AssistantTool(
        name=name,
        description=name,
        schema={},
        handler=lambda context, arguments: arguments,
    )


def _write_skill(
    root: Path,
    *,
    name: str = "data_ops.cash_collection_risk",
    tools: tuple[str, ...] = ("data_ops_query_records",),
) -> Path:
    skill_dir = root / "cash-collection-risk"
    skill_dir.mkdir()
    tool_lines = "\n".join(f"  - {tool}" for tool in tools)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "description: Find collection risks.",
                "tools:",
                tool_lines,
                "version: '1'",
                "---",
                "",
                "# Collection risk",
                "",
                "Group outstanding amounts by currency.",
            ]
        ),
        encoding="utf-8",
    )
    return skill_dir


def _capability(root: Path) -> AssistantCapability:
    return AssistantCapability(
        app_key="data_ops",
        display_name="Data Ops Assistant",
        required_feature="data_ops",
        instructions="Use Data Ops tools only.",
        tools=(_tool("data_ops_query_records"),),
        skill_dirs=(root,),
    )


def test_load_skills_parses_body_into_memory(tmp_path):
    skill_dir = _write_skill(tmp_path)

    skills = load_skills(_capability(tmp_path))
    (skill_dir / "SKILL.md").write_text("changed", encoding="utf-8")

    assert skills[0].key == "data_ops.cash_collection_risk"
    assert "Group outstanding amounts" in skills[0].instructions
    assert skills[0].allowed_tools == ("data_ops_query_records",)


def test_load_skills_rejects_another_app_namespace(tmp_path):
    _write_skill(tmp_path, name="cloud_billing.cash_collection_risk")

    with pytest.raises(ValueError, match="must use namespace data_ops"):
        load_skills(_capability(tmp_path))


def test_load_skills_rejects_unknown_tool(tmp_path):
    _write_skill(tmp_path, tools=("cloud_billing_query_costs",))

    with pytest.raises(ValueError, match="unknown tools"):
        load_skills(_capability(tmp_path))


def test_catalog_is_partitioned_by_app(tmp_path):
    _write_skill(tmp_path)
    catalog = SkillCatalog()

    catalog.initialize((_capability(tmp_path),))

    assert tuple(catalog.for_app("data_ops")) == (
        "data_ops.cash_collection_risk",
    )
    assert catalog.for_app("cloud_billing") == {}
