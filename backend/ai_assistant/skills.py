"""Startup-time loading and validation for local assistant skills."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import yaml

from ai_assistant.contracts import (
    AssistantCapability,
    SkillDescriptor,
)


def _parse_skill(skill_dir: Path, app_key: str) -> SkillDescriptor:
    skill_path = skill_dir / "SKILL.md"
    raw = skill_path.read_text(encoding="utf-8")
    frontmatter: dict = {}
    instructions = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid SKILL.md frontmatter: {skill_path}")
        frontmatter = yaml.safe_load(parts[1]) or {}
        instructions = parts[2].strip()

    key = str(frontmatter.get("name") or skill_dir.name).strip()
    expected_prefix = f"{app_key}."
    if not key.startswith(expected_prefix):
        raise ValueError(
            f"Skill {key} must use namespace {app_key}"
        )
    allowed_tools = tuple(
        str(name) for name in frontmatter.get("tools", [])
    )
    references_dir = skill_dir / "references"
    reference_files = ()
    if references_dir.exists():
        reference_files = tuple(
            path
            for path in sorted(references_dir.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts
        )
    return SkillDescriptor(
        key=key,
        app_key=app_key,
        description=str(frontmatter.get("description") or "").strip(),
        instructions=instructions,
        allowed_tools=allowed_tools,
        version=str(frontmatter.get("version") or "1"),
        skill_dir=skill_dir,
        reference_files=reference_files,
        fingerprint=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def load_skills(
    capability: AssistantCapability,
) -> tuple[SkillDescriptor, ...]:
    """Load and validate all local skills for one capability."""

    available_tools = {tool.name for tool in capability.tools}
    skills: list[SkillDescriptor] = []
    seen_keys: set[str] = set()
    for root in capability.skill_dirs:
        if not root.exists():
            continue
        for skill_path in sorted(root.glob("*/SKILL.md")):
            skill = _parse_skill(skill_path.parent, capability.app_key)
            if skill.key in seen_keys:
                raise ValueError(f"Duplicate assistant skill: {skill.key}")
            unknown_tools = set(skill.allowed_tools) - available_tools
            if unknown_tools:
                names = ", ".join(sorted(unknown_tools))
                raise ValueError(
                    f"Skill {skill.key} references unknown tools: {names}"
                )
            seen_keys.add(skill.key)
            skills.append(skill)
    return tuple(skills)


class SkillCatalog:
    """Read-only, process-local catalog initialized at startup."""

    def __init__(self) -> None:
        self._skills_by_app: Mapping[
            str,
            Mapping[str, SkillDescriptor],
        ] = MappingProxyType({})
        self._initialized = False

    def initialize(
        self,
        capabilities: tuple[AssistantCapability, ...],
    ) -> None:
        """Load all skill files once and freeze the result."""

        if self._initialized:
            return
        loaded = {}
        for capability in capabilities:
            loaded[capability.app_key] = MappingProxyType(
                {
                    skill.key: skill
                    for skill in load_skills(capability)
                }
            )
        self._skills_by_app = MappingProxyType(loaded)
        self._initialized = True

    def for_app(self, app_key: str) -> Mapping[str, SkillDescriptor]:
        """Return the isolated catalog for one app."""

        return self._skills_by_app.get(app_key, MappingProxyType({}))

    def reset(self) -> None:
        """Clear startup state for isolated tests."""

        self._skills_by_app = MappingProxyType({})
        self._initialized = False


skill_catalog = SkillCatalog()
