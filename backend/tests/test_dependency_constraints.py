from importlib import import_module
from importlib.metadata import requires

from packaging.requirements import Requirement
from packaging.version import Version


def test_litellm_excludes_fastapi_import_regression():
    """Require the LiteLLM release that avoids importing FastAPI for tools."""
    project_requirements = {
        requirement.name: requirement
        for value in requires("backend") or []
        if (requirement := Requirement(value)).marker is None
    }

    litellm = project_requirements.get("litellm")

    assert litellm is not None
    assert Version("1.91.3") in litellm.specifier
    assert Version("1.89.4") not in litellm.specifier

    import_module("litellm.responses.mcp.chat_completions_handler")
