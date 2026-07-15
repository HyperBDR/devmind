from ai_assistant.skills import load_skills
from data_ops.assistant import get_assistant_capability


def test_data_ops_registers_tools_and_local_skills():
    capability = get_assistant_capability()

    assert capability.app_key == "data_ops"
    assert capability.required_feature == "data_ops"
    assert {
        tool.name for tool in capability.tools
    } == {
        "data_ops_get_schema",
        "data_ops_query_records",
        "data_ops_aggregate",
    }

    skills = load_skills(capability)

    assert {
        skill.key for skill in skills
    } >= {
        "data_ops.business_health_scan",
        "data_ops.cash_collection_risk",
        "data_ops.data_quality_guard",
    }


def test_data_ops_capability_exposes_existing_profile():
    capability = get_assistant_capability()

    profile = capability.profile_loader()

    assert profile["capabilities"]
    assert profile["question_groups"]
    assert profile["query_tools"]["tools"]
