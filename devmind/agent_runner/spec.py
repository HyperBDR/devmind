"""Skill specification and loading helpers for AgentRunner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool


def _iter_skill_files(skill_dir: Path):
    """Yield all files under ``skill_dir`` recursively, excluding ``__pycache__``."""
    for path in skill_dir.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            yield path


@dataclass
class SkillSpec:
    """
    Specification for a skill sub-agent.

    Loaded from the YAML frontmatter of a skill's SKILL.md::

        ---
        name: my-skill
        description: Does X and Y...
        model: openai:gpt-4o
        tools: [http_request, json_parser]
        ---

    The `system_prompt` field (optional) overrides the default generated prompt.
    """

    name: str
    description: str
    model: str | BaseChatModel = "openai:gpt-4o"
    tools: List[str] = field(default_factory=list)
    system_prompt: str = ""

    # Internal fields populated by load_from_skill_dir().
    _skill_dir: Optional[Path] = field(default=None, repr=False)
    _extra_tools: List[BaseTool] = field(default_factory=list, repr=False)

    @classmethod
    def load_from_skill_dir(cls, skill_dir: Path, extra_tools: List[BaseTool] | None = None) -> "SkillSpec":
        """
        Load a SkillSpec from the YAML frontmatter of ``skill_dir/SKILL.md``.

        The ``tools`` field in frontmatter is currently treated as a documentation
        hint only — the actual tool instances are passed at registration time
        via ``AgentRunner.register_skill()``.
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in skill directory: {skill_dir}")

        raw = skill_md.read_text(encoding="utf-8")
        if raw.startswith("---"):
            end = raw.index("---", 3)
            frontmatter = yaml.safe_load(raw[3:end])
        else:
            frontmatter = {}

        return cls(
            name=str(frontmatter.get("name", skill_dir.name)),
            description=str(frontmatter.get("description", "")),
            model=str(frontmatter.get("model", "openai:gpt-4o")),
            tools=[str(tool_name) for tool_name in frontmatter.get("tools", [])],
            system_prompt=str(frontmatter.get("system_prompt", "")),
            _skill_dir=skill_dir,
            _extra_tools=extra_tools or [],
        )
